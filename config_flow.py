from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries, exceptions
from homeassistant.core import callback, HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import config_validation

from .agur_client import AgurClient
from .const import DOMAIN, CONF_USERNAME, CONF_PASSWORD, VERSION, CONF_CONTRACT_IDS

SESSION_TOKEN = "session"
AUTH_TOKEN = "auth"
_LOGGER: logging.Logger = logging.getLogger(__package__)


async def get_agur_tokens(hass: HomeAssistant, username: str, password: str) -> dict[str, str]:
    try:
        tokens = {}

        client = AgurClient()
        response = await hass.async_add_executor_job(client.init)
        tokens[SESSION_TOKEN] = response["token"]
        client = AgurClient(session_token=tokens[SESSION_TOKEN])
        response = await hass.async_add_executor_job(client.login, username, password)
        tokens[AUTH_TOKEN] = response["tokenAuthentique"]

        return tokens
    except Exception as ex:
        raise AuthError(ex)


async def get_agur_contract_options(hass: HomeAssistant, session_token: str, auth_token: str):
    try:
        client = AgurClient(session_token=session_token, auth_token=auth_token)
        return {c.id: f"Contract {c.id} ({c.address})" for c in await hass.async_add_executor_job(client.get_contracts)}
    except Exception as ex:
        raise ContractError(ex)


class AgurConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Agur."""

    VERSION = VERSION

    def __init__(self):
        """Initialize."""
        self.login_schema = vol.Schema(
            {
                vol.Required(CONF_USERNAME): str,
                vol.Required(CONF_PASSWORD): str
            }
        )
        self.contract_schema = vol.Schema(
            {
                vol.Required(CONF_CONTRACT_IDS): str,
            }
        )

        self._username: str | None = None
        self._password: str | None = None
        self._session_token: str | None = None
        self._auth_token: str | None = None
        self._available_contracts: list[dict[str, Any]] = []
        self._contract_ids: str | None = None

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Handle a login flow, initialized by the user."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=self.login_schema
            )

        self._username = user_input[CONF_USERNAME]
        self._password = user_input[CONF_PASSWORD]

        self._async_abort_entries_match({CONF_USERNAME: user_input[CONF_USERNAME]})

        return await self._async_agur_login(step_id="user")

    async def async_step_contract(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Handle a contract selection flow."""
        available_contracts = await get_agur_contract_options(
            hass=self.hass,
            session_token=self._session_token,
            auth_token=self._auth_token
        )
        # client = AgurClient(session_token=self._session_token, auth_token=self._auth_token)
        # available_contracts = {c.id: f"Contract {c.id} ({c.address})" for c in
        #                        await self.hass.async_add_executor_job(client.get_contracts)}
        default_contracts = list(available_contracts.keys())

        self.contract_schema = vol.Schema(
            {
                vol.Required(CONF_CONTRACT_IDS, default=default_contracts): config_validation.multi_select(
                    available_contracts)
            }
        )

        if user_input is None:
            return self.async_show_form(
                step_id="contract", data_schema=self.contract_schema
            )

        self._contract_ids = user_input[CONF_CONTRACT_IDS]

        return await self._async_agur_contract()

    async def _async_agur_login(self, step_id: str) -> FlowResult:
        """Handle login with Agur."""
        errors = {}

        try:
            tokens = await get_agur_tokens(hass=self.hass, username=self._username, password=self._password)
            self._session_token = tokens[SESSION_TOKEN]
            self._auth_token = tokens[AUTH_TOKEN]
            # client = AgurClient()
            # response = await self.hass.async_add_executor_job(client.init)
            # self._session_token = response["token"]
            # client = AgurClient(session_token=self._session_token)
            # response = await self.hass.async_add_executor_job(client.login, self._username, self._password)
            # self._auth_token = response["tokenAuthentique"]

        except Exception as ex:
            _LOGGER.error(ex)
            errors = {"base": "auth"}

        if errors:
            return self.async_show_form(
                step_id=step_id, data_schema=self.login_schema, errors=errors
            )

        return await self.async_step_contract()

    async def _async_agur_contract(self) -> FlowResult:
        """Handle Agur contract selection."""
        try:
            return await self._async_create_entry()

        except Exception as ex:
            _LOGGER.error(ex)
            return self.async_show_form(
                step_id="contract",
                data_schema=self.contract_schema,
                errors={"base": "contract"}
            )

    async def _async_create_entry(self) -> FlowResult:
        """Create the config entry."""
        config_data = {
            CONF_USERNAME: self._username,
            CONF_PASSWORD: self._password,
        }
        config_option = {
            CONF_CONTRACT_IDS: self._contract_ids,
        }
        existing_entry = await self.async_set_unique_id(self._username)

        if existing_entry:
            self.hass.config_entries.async_update_entry(
                existing_entry, data=config_data, options=config_option
            )
            # Reload the Abode config entry otherwise devices will remain unavailable
            self.hass.async_create_task(
                self.hass.config_entries.async_reload(existing_entry.entry_id)
            )

            return self.async_abort(reason="reauth_successful")

        return self.async_create_entry(
            title=f"Account - {self._username}", data=config_data, options=config_option
        )

    @staticmethod
    @callback
    def async_get_options_flow(
            config_entry: config_entries.ConfigEntry,
    ) -> AgurOptionFlow:
        """Get the options flow for this handler."""
        return AgurOptionFlow(config_entry)


class AgurOptionFlow(config_entries.OptionsFlow):
    """Handle an option flow for Agur."""

    def __init__(
            self,
            config_entry: config_entries.ConfigEntry
    ) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
            self,
            user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""

        errors = {}
        available_contracts = []
        default_contracts = self.config_entry.options.get(CONF_CONTRACT_IDS, [])

        # We want to save here
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        try:
            username = self.config_entry.data.get(CONF_USERNAME, None)
            password = self.config_entry.data.get(CONF_PASSWORD, None)
            if username is None:
                raise ConfigError("Cannot retrieve the username from the config entry")
            if password is None:
                raise ConfigError("Cannot retrieve the password from the config entry")

            tokens = await get_agur_tokens(
                hass=self.hass,
                username=username,
                password=password
            )
            available_contracts = await get_agur_contract_options(
                hass=self.hass,
                session_token=tokens[SESSION_TOKEN],
                auth_token=tokens[AUTH_TOKEN]
            )
        except ConfigError as ex:
            _LOGGER.error(ex)
            errors = {"base": "config"}
        except AuthError as ex:
            _LOGGER.error(ex)
            errors = {"base": "auth"}
        except ContractError as ex:
            _LOGGER.error(ex)
            errors = {"base": "contracts"}
        except Exception as ex:
            _LOGGER.error(ex)
            errors = {"base": "unknown"}

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_CONTRACT_IDS,
                        default=default_contracts,
                    ): config_validation.multi_select(available_contracts),
                }
            ),
            errors=errors,
        )


class ConfigError(exceptions.HomeAssistantError):
    """Error to indicate an issue the config entry."""


class AuthError(exceptions.HomeAssistantError):
    """Error to indicate an issue with the authentication."""


class ContractError(exceptions.HomeAssistantError):
    """Error to indicate an issue with the fetching of contracts."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import config_validation

from .agur_client import AgurClient
from .const import DOMAIN, CONF_USERNAME, CONF_PASSWORD, VERSION, CONF_CONTRACT_IDS, DEFAULT_NAME

_LOGGER: logging.Logger = logging.getLogger(__package__)


class AgurConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
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
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=self.login_schema
            )

        self._username = user_input[CONF_USERNAME]
        self._password = user_input[CONF_PASSWORD]

        return await self._async_agur_login(step_id="user")

    async def async_step_contract(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Handle a contract selection flow."""

        client = AgurClient(session_token=self._session_token, auth_token=self._auth_token)
        available_contracts = {c.id: f"Contract {c.id} ({c.address})" for c in
                               await self.hass.async_add_executor_job(client.get_contracts)}
        default_contracts = list(available_contracts.keys())

        # TODO: Support selection of multiple contracts
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
            client = AgurClient()
            response = await self.hass.async_add_executor_job(client.init)
            self._session_token = response["token"]
            client = AgurClient(session_token=self._session_token)
            response = await self.hass.async_add_executor_job(client.login, self._username, self._password)
            self._auth_token = response["tokenAuthentique"]

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
            CONF_CONTRACT_IDS: self._contract_ids,
        }
        existing_entry = await self.async_set_unique_id(self._username)

        if existing_entry:
            self.hass.config_entries.async_update_entry(
                existing_entry, data=config_data
            )
            # Reload the Abode config entry otherwise devices will remain unavailable
            self.hass.async_create_task(
                self.hass.config_entries.async_reload(existing_entry.entry_id)
            )

            return self.async_abort(reason="reauth_successful")

        return self.async_create_entry(
            title=DEFAULT_NAME, data=config_data
        )

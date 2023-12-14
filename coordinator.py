from __future__ import annotations

import logging
from datetime import timedelta, datetime

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from requests import HTTPError

from .agur_client import AgurClient
from .const import DOMAIN

_LOGGER: logging.Logger = logging.getLogger(__name__)
# TODO: This should be configurable?
SCAN_INTERVAL = timedelta(days=1)


class AgurDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching data from the API."""

    def __init__(
            self,
            hass: HomeAssistant,
            username: str,
            password: str,
            contract_ids: list[str]
    ) -> None:
        """Initialize."""
        self.platforms = []
        self.expiration_date: datetime | None = None
        self.session_token: datetime | None = None
        self.auth_token: str | None = None
        self.username = username
        self.password = password
        self.contract_ids = contract_ids

        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=SCAN_INTERVAL)

    async def _async_update_data(self):
        """Update data via library."""
        # If we do not have any session token (first time)
        if self.session_token is None or self.expiration_date is None:
            _LOGGER.debug("First sync: fetching session token")
            await self._async_get_session_token()

        # If the session token is expired, retrieve one
        if datetime.now().replace(tzinfo=self.expiration_date.tzinfo) > self.expiration_date:
            _LOGGER.debug("Session token expired: fetching a new one")
            await self._async_get_session_token()

        try:
            # If we do not have any auth token (first time)
            if self.auth_token is None:
                _LOGGER.debug("First sync: fetching auth token")
                await self._async_get_auth_token()

            data = {}
            for contract_id in self.contract_ids:
                _LOGGER.debug(f"Fetching data for contract '{contract_id}'")
                data[contract_id] = await self._async_get_data(contract_id=contract_id)
                _LOGGER.debug(f"Data fetched for contract '{contract_id}': {data[contract_id]}")

            return data

        except HTTPError as exception:
            if exception.response.status_code == 401:
                raise ConfigEntryAuthFailed(f"Invalid credentials for Agur account {self.username}")
            raise exception
        except Exception as exception:
            raise UpdateFailed(f"Error communicating with API: {exception}")

    async def _async_get_session_token(self):
        client = AgurClient()
        response = await self.hass.async_add_executor_job(client.init)
        self.session_token = response["token"]
        self.expiration_date = datetime.fromisoformat(response["expirationDate"])

    async def _async_get_auth_token(self):
        client = AgurClient(session_token=self.session_token)
        response = await self.hass.async_add_executor_job(client.login, self.username, self.password)
        self.auth_token = response["tokenAuthentique"]

    async def _async_get_data(self, contract_id):
        client = AgurClient(session_token=self.session_token, auth_token=self.auth_token)
        response = await self.hass.async_add_executor_job(client.get_data, contract_id)
        return response[0]["valeurIndex"]

from __future__ import annotations

import asyncio
import logging
from datetime import timedelta, datetime

from homeassistant.components.recorder import get_instance
from homeassistant.components.recorder.models import StatisticData, StatisticMetaData
from homeassistant.components.recorder.statistics import get_last_statistics, async_add_external_statistics
from homeassistant.const import UnitOfVolume
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from requests import HTTPError

from .agur_client import AgurClient, AgurContract, AgurDataPoint
from .const import DOMAIN

_LOGGER: logging.Logger = logging.getLogger(__name__)
# TODO: This should be configurable?
SCAN_INTERVAL = timedelta(days=1)


class AgurDataUpdateCoordinatorData:
    data_points: list[AgurDataPoint]
    contract: AgurContract

    def __init__(self, data_points: list[AgurDataPoint], contract: AgurContract):
        self.data_points = data_points
        self.contract = contract

    @property
    def latest_data_point(self) -> AgurDataPoint | None:
        return self.data_points[0] if len(self.data_points) > 0 else None


class AgurDataUpdateCoordinator(DataUpdateCoordinator[dict[str, AgurDataUpdateCoordinatorData]]):
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

    async def _async_update_data(self) -> dict[str, AgurDataUpdateCoordinatorData]:
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

            data: dict[str, AgurDataUpdateCoordinatorData] = {}
            for contract_id in self.contract_ids:
                _LOGGER.debug(f"Fetching details and history for contract '{contract_id}'")
                results = await asyncio.gather(
                    self._async_get_data_points(contract_id=contract_id),
                    self._async_get_contract(contract_id=contract_id)
                )
                data[contract_id] = AgurDataUpdateCoordinatorData(data_points=results[0], contract=results[1])

                # TODO: Make this configurable with a config_entry.option
                # TODO: This should not be within the coordinator. Possibly in the __init__.py or in sensors.py
                await self._insert_statistics(coordinator_data=data[contract_id])

            return data

        except HTTPError as exception:
            if exception.response.status_code == 401:
                raise ConfigEntryAuthFailed(f"Invalid credentials for Agur account {self.username}")
            raise exception
        except Exception as exception:
            raise UpdateFailed(f"Error communicating with API: {exception}")

    async def _async_get_session_token(self) -> None:
        client = AgurClient()
        response = await self.hass.async_add_executor_job(client.init)
        self.session_token = response["token"]
        self.expiration_date = datetime.fromisoformat(response["expirationDate"])

    async def _async_get_auth_token(self) -> None:
        client = AgurClient(session_token=self.session_token)
        response = await self.hass.async_add_executor_job(client.login, self.username, self.password)
        self.auth_token = response["tokenAuthentique"]

    async def _async_get_data_points(self, contract_id) -> list[AgurDataPoint]:
        client = AgurClient(session_token=self.session_token, auth_token=self.auth_token)
        return await self.hass.async_add_executor_job(client.get_data, contract_id)

    async def _async_get_contract(self, contract_id) -> AgurContract:
        client = AgurClient(session_token=self.session_token, auth_token=self.auth_token)
        return await self.hass.async_add_executor_job(client.get_contract, contract_id)

    async def _insert_statistics(self, coordinator_data: AgurDataUpdateCoordinatorData):
        # I've decided to insert statics without a backing of a sensor. Few integrations in core use the same principal
        # For example:
        # - https://github.com/home-assistant/core/blob/dev/homeassistant/components/tibber/sensor.py#L594-L690
        # - https://github.com/home-assistant/core/blob/dev/homeassistant/components/opower/coordinator.py#L89-L188
        #
        # Another solution would be to use a sensor for this using the following library:
        # https://github.com/ldotlopez/ha-historical-sensor

        statistic_id = f"{DOMAIN}:water_consumption_{coordinator_data.contract.id}"
        daily_indexes_data = coordinator_data.data_points
        last_stats = await get_instance(self.hass).async_add_executor_job(
            get_last_statistics,
            self.hass,
            1,
            statistic_id,
            True,
            set("sum")
        )

        if not last_stats:
            # If the statistic does not exist, it means we are importing it for the first time, i.e. we import the
            # entire set of `daily_index_data`
            min_start = None
        else:
            # Otherwise, we want to reimport the last 30 days of data, just in case there are some corrections that
            # need to be done
            # `daily_index_data[0]` is the most recent data point, so we get that date and subtract 30 days.
            min_start = daily_indexes_data[0].date - timedelta(days=30)

        statistics = []

        for index, daily_index_data in enumerate(list(reversed(daily_indexes_data))):
            _start = daily_index_data.date
            if min_start is not None and _start <= min_start:
                continue

            _state = daily_index_data.value - daily_indexes_data[index - 1].value if index > 0 else 0
            _sum = daily_index_data.value

            statistics.append(
                StatisticData(
                    start=_start,
                    state=_state,
                    sum=_sum,
                )
            )

        unit = UnitOfVolume.LITERS
        metadata = StatisticMetaData(
            has_mean=False,
            has_sum=True,
            name=f"Water consumption",
            source=DOMAIN,
            statistic_id=statistic_id,
            unit_of_measurement=unit,
        )
        async_add_external_statistics(self.hass, metadata, statistics)

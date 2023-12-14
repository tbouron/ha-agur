"""Sensor platform for {{cookiecutter.friendly_name}}."""
from __future__ import annotations

import logging

from homeassistant.components.sensor import SensorEntity, SensorStateClass, SensorDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfVolume
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, DEFAULT_NAME
from .const import SENSOR_PLATFORM
from .coordinator import AgurDataUpdateCoordinator

_LOGGER: logging.Logger = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities: AddEntitiesCallback):
    """Add Agur sensors from a config_entry."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    entities = []
    for contract_id in coordinator.contract_ids:
        _LOGGER.debug(f"Add sensor for Agur contract {contract_id}")
        entities.append(WaterSensor(coordinator=coordinator, contract_id=contract_id, unique_id=config_entry.entry_id))
    async_add_entities(entities, True)


class WaterSensor(CoordinatorEntity[AgurDataUpdateCoordinator], SensorEntity):
    """Agur water Sensor class."""
    _attr_name = "Last water index"
    _attr_icon = "mdi:counter"
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_device_class = SensorDeviceClass.WATER
    _attr_native_unit_of_measurement = UnitOfVolume.LITERS

    def __init__(self, coordinator: AgurDataUpdateCoordinator, unique_id: str, contract_id: str) -> None:
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(coordinator=coordinator)
        self.entity_id = f"{SENSOR_PLATFORM}.{DOMAIN}_water_index_{contract_id}"
        self._attr_unique_id = unique_id
        self._contract_id = contract_id
        self._attr_extra_state_attributes = {
            "last_read": self.coordinator.data[contract_id].latest_data_point.date,
            "contract_id": contract_id,
            "contract_address": self.coordinator.data[contract_id].contract.address,
            "contract_owner": self.coordinator.data[contract_id].contract.owner,
            "meter_serial_number": self.coordinator.data[contract_id].contract.meter_serial_number,
        }
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.data[contract_id].contract.meter_id)},
            default_manufacturer=DEFAULT_NAME,
            default_name="Water meter",
            model=self.coordinator.data[contract_id].contract.meter_serial_number
        )

    @property
    def native_value(self) -> float:
        """Return the state of the sensor."""
        return self.coordinator.data[self._contract_id].latest_data_point.value

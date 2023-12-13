"""Sensor platform for {{cookiecutter.friendly_name}}."""
from __future__ import annotations

import logging

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DEFAULT_NAME
from .const import DOMAIN
from .const import SENSOR_PLATFORM
from .const import SENSOR_WATER_DEVICE_CLASS
from .const import SENSOR_WATER_ICON
from .const import SENSOR_WATER_STATE_CLASS_TOTAL_INCREASING
from .const import SENSOR_WATER_UNIT
from .coordinator import AgurDataUpdateCoordinator

_LOGGER: logging.Logger = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities: AddEntitiesCallback):
    """Add Agur sensors from a config_entry."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    entities = []
    for contract_id in coordinator.contract_ids:
        _LOGGER.info(f"Add sensor for Agur contract {contract_id}")
        entities.append(WaterSensor(coordinator=coordinator, contract_id=contract_id))
    async_add_entities(entities, True)


class WaterSensor(CoordinatorEntity[AgurDataUpdateCoordinator], SensorEntity):
    """Agur water Sensor class."""
    _attr_name = "Water index"
    _attr_icon = SENSOR_WATER_ICON
    _attr_state_class = SENSOR_WATER_STATE_CLASS_TOTAL_INCREASING
    _attr_device_class = SENSOR_WATER_DEVICE_CLASS
    _attr_native_unit_of_measurement = SENSOR_WATER_UNIT

    def __init__(self, coordinator: AgurDataUpdateCoordinator, contract_id: str) -> None:
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(coordinator=coordinator)
        self.entity_id = f"{SENSOR_PLATFORM}.{DOMAIN}_water_index_{contract_id}"
        self._contract_id = contract_id
        self._attr_extra_state_attributes = {
            "contract_id": contract_id
        }
        self._attr_device_info = DeviceInfo(
            name=DEFAULT_NAME,
            identifiers={(DOMAIN, contract_id)},
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def native_value(self) -> float:
        """Return the state of the sensor."""
        return self.coordinator.data[self._contract_id]

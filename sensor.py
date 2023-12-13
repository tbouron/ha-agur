"""Sensor platform for {{cookiecutter.friendly_name}}."""
import logging

from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .const import SENSOR_PLATFORM
from .const import SENSOR_WATER_DEVICE_CLASS
from .const import SENSOR_WATER_ICON
from .const import SENSOR_WATER_STATE_CLASS_TOTAL_INCREASING
from .const import SENSOR_WATER_UNIT
from .coordinator import AgurDataUpdateCoordinator

_LOGGER: logging.Logger = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Setup sensor platform."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    _LOGGER.info(f"Set sensors with coordinator: {int(coordinator.data)}")
    async_add_entities([
        WaterSensor(coordinator)
    ])


class WaterSensor(CoordinatorEntity[AgurDataUpdateCoordinator], SensorEntity):
    """Water Sensor class."""
    _attr_name = f"{DOMAIN}_water_{SENSOR_PLATFORM}"
    _attr_icon = SENSOR_WATER_ICON
    _attr_state_class = SENSOR_WATER_STATE_CLASS_TOTAL_INCREASING
    _attr_device_class = SENSOR_WATER_DEVICE_CLASS
    _attr_native_unit_of_measurement = SENSOR_WATER_UNIT

    def __init__(self, coordinator: AgurDataUpdateCoordinator):
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(coordinator=coordinator)

    @property
    def native_value(self) -> float:
        """Return the state of the sensor."""
        return self.coordinator.data

# Base component constants
from typing import Final

DOMAIN: Final = "agur"
DEFAULT_NAME: Final = "Agur"
VERSION = 1

# Configuration and options constants
CONF_ENABLED = "enabled"
CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_CONTRACT_IDS = "contract_ids"

# Other constants
SENSOR_PLATFORM = "sensor"
PLATFORMS = [SENSOR_PLATFORM]

STARTUP_MESSAGE = f"""
---------------------------------------------------------------------
{DEFAULT_NAME} integration
Custom integration to fetch water data from Agur: https://ael.agur.fr

Domain: {DOMAIN}
Version: {VERSION}
---------------------------------------------------------------------
"""

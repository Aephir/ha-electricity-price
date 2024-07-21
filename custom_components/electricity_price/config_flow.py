import logging
from typing import Any, Dict, Optional
from pyeloverblik import Eloverblik

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
import voluptuous as vol

from .const import (
    CONF_PRICE_SENSOR,
    DOMAIN,
    CONF_ELOVERBLIK_TOKEN,
    CONF_METERING_POINT,
)

_LOGGER = logging.getLogger(__name__)

SENSOR_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_PRICE_SENSOR): cv.entity_id,
    }
)

ELOVERBLIK_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_ELOVERBLIK_TOKEN): cv.string,
        vol.Optional(CONF_METERING_POINT): cv.string,
    }
)


async def async_validate_sensor(sensor: str, hass: HomeAssistant) -> None:
    """Validates a Home Assistant Nordpool sensor.
    https://github.com/custom-components/nordpool
    Raises a ValueError if the path is invalid.
    :param sensor:
    :type hass: object
    """
    try:
        sensor.split(".")[1]
    except IndexError:
        raise IndexError

    price_state = hass.states.get(sensor)
    nordpool_attribute_keys = price_state.attributes.keys()
    check_attributes = [
        "current_price",
        "raw_today",
        "unit",
    ]
    if not all([i in nordpool_attribute_keys for i in check_attributes]):
        raise ValueError


async def validate_eloverblik(token, metering_point):
    """Try to log in and get the metering point at https://api.eloverblik.dk/CustomerApi/
    Raises ValueError if it can't (typically meaning either token or metering point is wrong)."""
    client = Eloverblik(token)
    data = client.get_latest(metering_point)

    if not int(data.status) == 200:
        raise ValueError


class ElectricityPriceConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Electricity price config flow."""

    data: Optional[Dict[str, Any]]

    async def async_step_user(self, user_input: Optional[Dict[str, Any]] = None):
        """Handle the initial step."""
        errors: Dict[str, str] = {}
        device_unique_id = "total_electricity_price_per_hour"
        await self.async_set_unique_id(device_unique_id)
        self._abort_if_unique_id_configured()
        if user_input is not None:
            try:
                await async_validate_sensor(user_input[CONF_PRICE_SENSOR], self.hass)
            except ValueError:
                errors["base"] = "auth"
            if not errors:
                # Input is valid, set data.
                self.data = user_input
                # Return the form of the next step.
                return await self.async_step_eloverblik()

        return self.async_show_form(
            step_id="user", data_schema=SENSOR_SCHEMA, errors=errors
        )

    async def async_step_eloverblik(self, user_input: Optional[Dict[str, Any]] = None):
        """Second step in config flow to validate Eloverblik credentials."""
        errors: Dict[str, str] = {}
        if user_input is not None:
            try:
                await validate_eloverblik(user_input[CONF_ELOVERBLIK_TOKEN], user_input[CONF_METERING_POINT])
            except ValueError:
                errors["base"] = "invalid_eloverblik"
            if not errors:
                # Input is valid, set data.
                self.data[CONF_ELOVERBLIK_TOKEN] = user_input[CONF_ELOVERBLIK_TOKEN]
                self.data[CONF_METERING_POINT] = user_input[CONF_METERING_POINT]
                return self.async_create_entry(title="Total Electricity Price", data=self.data)

        return self.async_show_form(
            step_id="eloverblik", data_schema=ELOVERBLIK_SCHEMA, errors=errors
        )

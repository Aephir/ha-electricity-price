import logging
from typing import Any, Dict, Optional
from pyeloverblik import Eloverblik

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from datetime import datetime, timedelta
from functools import partial

from .const import (
    CONF_PRICE_SENSOR,
    DOMAIN,
    CONF_ELOVERBLIK_TOKEN,
    CONF_METERING_POINT,
)

_LOGGER = logging.getLogger(__name__)

SENSOR_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_PRICE_SENSOR, description={"suggested_value": ""}): str,
    }
)

ELOVERBLIK_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_ELOVERBLIK_TOKEN, description={"suggested_value": ""}): str,
        vol.Optional(CONF_METERING_POINT, description={"suggested_value": ""}): str,
    }
)


async def async_validate_sensor(sensor: str, hass: HomeAssistant) -> None:
    """Validates a Home Assistant Nordpool sensor.
    https://github.com/custom-components/nordpool
    Raises a ValueError if the path is invalid.
    :param sensor:
    :type hass: object
    """
    _LOGGER.debug("Validating sensor: %s", sensor)
    try:
        price_state = hass.states.get(sensor)
        if not price_state:
            raise ValueError("Sensor does not exist")
        attributes = price_state.attributes
        required_keys = ["current_price", "raw_today", "unit"]
        if not all(key in attributes for key in required_keys):
            raise ValueError("Sensor attributes invalid")
    except Exception as e:
        _LOGGER.error("Sensor validation failed: %s", e)
        raise

async def validate_eloverblik(hass: HomeAssistant, token: str, metering_point: str) -> None:
    """Try to log in and get the metering point at https://api.eloverblik.dk/CustomerApi/
    Raises ValueError if it can't (typically meaning either token or metering point is wrong)."""
    _LOGGER.debug("Validating Eloverblik with token: %s, metering_point: %s", token, metering_point)

    def validate():
        """Blocking function for validation."""
        client = Eloverblik(token)
        # Corrected to remove unsupported parameters
        data = client.get_latest(metering_point)

        if int(data.status) != 200:
            raise ValueError("Invalid API response")
        return data

    try:
        # Run the blocking operation in a thread pool
        await hass.async_add_executor_job(validate)
    except Exception as e:
        _LOGGER.error("Eloverblik validation failed: %s", e)
        raise


class ElectricityPriceConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Electricity price config flow."""

    data: Optional[Dict[str, Any]]

    async def async_step_user(self, user_input: Optional[Dict[str, Any]] = None):
        """Handle the initial step."""
        _LOGGER.debug("Starting async_step_user")
        errors: Dict[str, str] = {}
        await self.async_set_unique_id("total_electricity_price_per_hour")
        self._abort_if_unique_id_configured()
        if user_input:
            _LOGGER.debug("User input: %s", user_input)
            try:
                await async_validate_sensor(user_input[CONF_PRICE_SENSOR], self.hass)
            except ValueError:
                errors["base"] = "invalid_price_sensor"
            if self.hass.states.get(user_input[CONF_PRICE_SENSOR]) is None:
                errors["base"] = "sensor_not_found"
                return self.async_show_form(
                    step_id="user",
                    data_schema=vol.Schema({
                        vol.Required(CONF_PRICE_SENSOR): str,
                    }),
                    errors=errors,
                )

            if not errors:
                self.data = user_input
                return await self.async_step_eloverblik()
            self._config[CONF_PRICE_SENSOR] = user_input[CONF_PRICE_SENSOR]

        return self.async_show_form(
            step_id="user",
            data_schema=SENSOR_SCHEMA,
            errors=errors,
        )

    async def async_step_eloverblik(self, user_input: Optional[Dict[str, Any]] = None):
        """Second step in config flow to validate Eloverblik credentials."""
        _LOGGER.debug("Starting async_step_eloverblik")
        errors: Dict[str, str] = {}
        if user_input:
            _LOGGER.debug("User input for eloverblik: %s", user_input)
            try:
                await validate_eloverblik(
                    self.hass,
                    user_input[CONF_ELOVERBLIK_TOKEN],
                    user_input[CONF_METERING_POINT],
                )
            except ValueError:
                errors["base"] = "invalid_eloverblik"
            if not errors:
                self.data.update(user_input)
                return self.async_create_entry(title="Electricity Price", data=self.data)

        return self.async_show_form(
            step_id="eloverblik", data_schema=ELOVERBLIK_SCHEMA, errors=errors
        )

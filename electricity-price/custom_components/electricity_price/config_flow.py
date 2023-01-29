from copy import deepcopy
import logging
from typing import Any, Dict, Optional

from gidgethub import BadRequest
from gidgethub.aiohttp import GitHubAPI
from homeassistant import config_entries, core
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_NAME, CONF_PATH, CONF_URL
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_registry import (
    async_entries_for_config_entry,
    async_get_registry,
)
import voluptuous as vol

from .const import (
    CONF_TAX,
    CONF_CHARGE,
    CONF_PRICE_SENSOR,
    DOMAIN,
    NAME,
    ENTITY_ID,
    CONF_TRANSPORT_FEE,
    CONF_START_DATE,
    CONF_END_DATE,
    CONF_START_TIME,
    CONF_END_TIME,
    CONF_TRANSPORT_FEE_LOW_DATES_LOW_LOAD,
    CONF_TRANSPORT_FEE_LOW_DATES_HIGH_LOAD,
    CONF_TRANSPORT_FEE_LOW_DATES_PEAK_LOAD,
    CONF_TRANSPORT_FEE_HIGH_DATES_LOW_LOAD,
    CONF_TRANSPORT_FEE_HIGH_DATES_HIGH_LOAD,
    CONF_TRANSPORT_FEE_HIGH_DATES_PEAK_LOAD,
    CONF_HIGH_FEE_DATES,
    CONF_LOW_FEE_DATES,
    CONF_LOW_LOAD_TIMES,
    CONF_HIGH_LOAD_TIMES,
    CONF_PEAK_LOAD_TIMES,
)
import helpers

_LOGGER = logging.getLogger(__name__)

SENSOR_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_PRICE_SENSOR): cv.entity_id,
    }
)

FIXED_CHARGE_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_CHARGE): helpers.number,
        vol.Optional(CONF_TAX): helpers.percentage,
    }
)

VARIABLE_CHARGE_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_TRANSPORT_FEE_LOW_DATES_LOW_LOAD): helpers.number,
        vol.Optional(CONF_TRANSPORT_FEE_LOW_DATES_HIGH_LOAD): helpers.number,
        vol.Optional(CONF_TRANSPORT_FEE_LOW_DATES_PEAK_LOAD): helpers.number,
        vol.Optional(CONF_TRANSPORT_FEE_HIGH_DATES_LOW_LOAD): helpers.number,
        vol.Optional(CONF_TRANSPORT_FEE_HIGH_DATES_HIGH_LOAD): helpers.number,
        vol.Optional(CONF_TRANSPORT_FEE_HIGH_DATES_PEAK_LOAD): helpers.number,
        # vol.Optional("add_another"): cv.boolean,
    }
)

DATE_RANGE_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_HIGH_FEE_DATES): cv.string,
        vol.Optional(CONF_LOW_FEE_DATES): cv.string,
    }
)

TIME_RANGE_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_LOW_LOAD_TIMES): cv.string,
        vol.Optional(CONF_HIGH_LOAD_TIMES): cv.string,
        vol.Optional(CONF_PEAK_LOAD_TIMES): cv.string,
    }
)


async def async_validate_sensor(sensor: str, user_input: str, hass: core.HassJob) -> None:
    """Validates a Home Assistant Nordpool sensor.
    https://github.com/custom-components/nordpool
    Raises a ValueError if the path is invalid.
    """
    try:
        sensor.split(".")[1]
    except IndexError:
        raise IndexError
    nordpool_attribute_keys = hass.states.get(user_input[CONF_PRICE_SENSOR]).attributes.keys()
    check_attributes = [
        "current_price",
        "raw_today",
        "unit",
    ]
    if not all([i in nordpool_attribute_keys for i in check_attributes]):
        raise ValueError


async def async_validate_cost(cost: str) -> None:  # , hass: core.HassJob
    """Validates that a number is given
     Raises a ValueError if not.
    """
    try:
        float(cost)
    except ValueError:
        raise ValueError


async def async_validate_range(time_range: str) -> None:
    """Validate that the date ranges are the correct format.
    Date format should be either (with or without whitespaces):
        `YYYYMMDD - YYYYMMDD`, `YYMMDD - YYMMDD`
        `MMDD - MMDD`
        `MM-MM`
        `month - month` (e.g. `october - april`
        `mon - mon` (e.g. ´oct - apr`)
    Time format should be either (with or without whitespaces, either comma or semicolon separated for more than one):
        `HH:MM - HH:MM`, `HH:MM - HH:MM; HH:MM - HH:MM`
        `HH - HH`, `HH - HH; HH - HH`
    Raises ValueError if not.
    """
    try:
        range_list = time_range.split("-")
        if len(range_list) <= 1:
            raise ValueError
    except:
        raise ValueError


class ElectricityPriceConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Github Custom config flow."""

    data: Optional[Dict[str, Any]]

    async def async_step_user(self, user_input: Optional[Dict[str, Any]] = None):
        """Invoked when a user initiates a flow via the user interface.
        Does the name have to be "async_step_user" to be invoked automatically?
        """
        errors: Dict[str, str] = {}
        if user_input is not None:
            try:
                await async_validate_sensor(user_input[CONF_PRICE_SENSOR], self.hass)
            except ValueError:
                errors["base"] = "auth"
            if not errors:
                # Input is valid, set data.
                self.data = user_input
                # Return the form of the next step.
                return await self.async_step_fixed_charge()

        return self.async_show_form(
            step_id="sensor", data_schema=SENSOR_SCHEMA, errors=errors
        )

    async def async_step_fixed_charge(self, user_input: Optional[Dict[str, Any]] = None):
        """Second step in config flow to add fixed charge and tax"""
        errors: Dict[str, str] = {}
        if user_input is not None:
            try:
                await async_validate_cost(user_input[CONF_TAX])
                await async_validate_cost(user_input[CONF_CHARGE])
            except ValueError:
                errors["base"] = "invalid_number"
            if not errors:
                # Input is valid, set data.
                self.data[CONF_TAX] = user_input[CONF_TAX]
                self.data[CONF_CHARGE] = user_input[CONF_CHARGE]
                return await self.async_variable_charge()

        return self.async_show_form(
            step_id="fixed_charge", data_schema=FIXED_CHARGE_SCHEMA, errors=errors
        )

    async def async_variable_charge(self, user_input: Optional[Dict[str, Any]] = None):
        """Third step in config flow to add variable charges.
        The best current way to have fewer differentiated fees is to simply write the same for two or more.
        TODO: Make each of these as separate step, so you can check whether to add more.
        """

        errors: Dict[str, str] = {}
        if user_input is not None:
            try:
                await async_validate_cost(user_input[CONF_TRANSPORT_FEE_LOW_DATES_LOW_LOAD])
                await async_validate_cost(user_input[CONF_TRANSPORT_FEE_LOW_DATES_HIGH_LOAD])
                await async_validate_cost(user_input[CONF_TRANSPORT_FEE_LOW_DATES_PEAK_LOAD])
                await async_validate_cost(user_input[CONF_TRANSPORT_FEE_HIGH_DATES_LOW_LOAD])
                await async_validate_cost(user_input[CONF_TRANSPORT_FEE_HIGH_DATES_HIGH_LOAD])
                await async_validate_cost(user_input[CONF_TRANSPORT_FEE_HIGH_DATES_PEAK_LOAD])
            except ValueError:
                errors["base"] = "invalid_number"

            if not errors:
                # Input is valid, set data.
                self.data[CONF_TRANSPORT_FEE_LOW_DATES_LOW_LOAD] = user_input[CONF_TRANSPORT_FEE_LOW_DATES_LOW_LOAD]
                self.data[CONF_TRANSPORT_FEE_LOW_DATES_HIGH_LOAD] = user_input[CONF_TRANSPORT_FEE_LOW_DATES_HIGH_LOAD]
                self.data[CONF_TRANSPORT_FEE_LOW_DATES_PEAK_LOAD] = user_input[CONF_TRANSPORT_FEE_LOW_DATES_PEAK_LOAD]
                self.data[CONF_TRANSPORT_FEE_HIGH_DATES_LOW_LOAD] = user_input[CONF_TRANSPORT_FEE_HIGH_DATES_LOW_LOAD]
                self.data[CONF_TRANSPORT_FEE_HIGH_DATES_HIGH_LOAD] = user_input[CONF_TRANSPORT_FEE_HIGH_DATES_HIGH_LOAD]
                self.data[CONF_TRANSPORT_FEE_HIGH_DATES_PEAK_LOAD] = user_input[CONF_TRANSPORT_FEE_HIGH_DATES_PEAK_LOAD]
                return await self.async_variable_dates()
                # If user ticked the box show this form again so they can add an
                # time period .
                # if user_input.get("add_another", False):
                #     return await self.async_step_repo()

        return self.async_show_form(
            step_id="variable_charge", data_schema=VARIABLE_CHARGE_SCHEMA, errors=errors
        )

    async def async_variable_dates(self, user_input: Optional[Dict[str, Any]] = None):
        """This is the forth config flow to add dates for high and low fee ranges.
        This should be added in a format as:
            `YYYYMMDD - YYYYMMDD`, `YYMMDD-YYMMDD`, `MMDD-MMDD`
            `Month - Month` (e.g. `October - April`)
            `mon - mon` (e.g. `Oct - Apr`)
        """

        errors: Dict[str, str] = {}
        if user_input is not None:

            try:
                await async_validate_range(user_input[CONF_HIGH_FEE_DATES])
                await async_validate_range(user_input[CONF_LOW_FEE_DATES])
            except ValueError:
                errors["base"] = "invalid_date_range"

            if not errors:
                self.data[CONF_HIGH_FEE_DATES] = user_input[CONF_HIGH_FEE_DATES]
                self.data[CONF_LOW_FEE_DATES] = user_input[CONF_LOW_FEE_DATES]
                return await self.async_variable_times()

        return self.async_show_form(
            step_id="variable_charge", data_schema=DATE_RANGE_SCHEMA, errors=errors
        )

    async def async_variable_times(self, user_input: Optional[Dict[str, Any]] = None):

        errors: Dict[str, str] = {}
        if user_input is not None:

            try:
                await async_validate_range(user_input[CONF_LOW_LOAD_TIMES])
                await async_validate_range(user_input[CONF_HIGH_LOAD_TIMES])
                await async_validate_range(user_input[CONF_PEAK_LOAD_TIMES])
            except ValueError:
                errors["base"] = "invalid_time_range"

            if not errors:
                self.data[CONF_LOW_LOAD_TIMES] = user_input[CONF_LOW_LOAD_TIMES]
                self.data[CONF_HIGH_LOAD_TIMES] = user_input[CONF_HIGH_LOAD_TIMES]
                self.data[CONF_PEAK_LOAD_TIMES] = user_input[CONF_PEAK_LOAD_TIMES]
                return self.async_create_entry(title="Total Electricity Price", data=self.data)

        return self.async_show_form(
            step_id="variable_charge", data_schema=DATE_RANGE_SCHEMA, errors=errors
        )


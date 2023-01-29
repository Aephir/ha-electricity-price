from __future__ import annotations

import logging
from typing import Any
from datetime import datetime, timedelta
from homeassistant import config_entries, core
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    ATTR_NAME,
    CONF_NAME,
    CONF_PATH,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.typing import (
    ConfigType,
    DiscoveryInfoType,
    HomeAssistantType,
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
    ATTR_TODAY,
    ATTR_TOMORROW,
    ATTR_TOTAL_TODAY,
    ATTR_TOTAL_TOMORROW,
    ATTR_CURRENCY,
    ATTR_COUNTRY,
    ATTR_REGION,
    ATTR_CURRENT_PRICE,
    ATTR_CURRENT_RAW_PRICE,
    ATTR_CURRENT_TRANSPORT_FEES,
    ATTR_CURRENT_TAX,
    ATTR_CURRENT_ELECTRICITY_FEE,
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
    CONST_MONTHS,
)
import helpers

_LOGGER = logging.getLogger(__name__)
# Time between updating data from GitHub
SCAN_INTERVAL = timedelta(minutes=10)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_PRICE_SENSOR): cv.entity_id,
        vol.Optional(CONF_TAX): helpers.percentage,
        vol.Optional(CONF_CHARGE): helpers.number,
        vol.Optional(CONF_TRANSPORT_FEE): helpers.number,
        vol.Optional(CONF_START_DATE): cv.date,
        vol.Optional(CONF_END_DATE): cv.date,
        vol.Optional(CONF_START_TIME): cv.time,
        vol.Optional(CONF_END_TIME): cv.time,
    }
)


async def async_setup_entry(
    hass: core.HomeAssistant,
    config_entry: config_entries.ConfigEntry,
    async_add_entities,
) -> None:
    """Setup sensors from a config entry created in the integrations UI."""
    config = hass.data[DOMAIN][config_entry.entry_id]
    # Update our config to include new repos and remove those that have been removed.
    if config_entry.options:
        config.async_update()
    # session = async_get_clientsession(hass)
    raw_sensor = config[CONF_PRICE_SENSOR]
    sensors = [PriceSensor(raw_sensor, config)]
    async_add_entities(sensors, update_before_add=True)


def setup_platform(  # async def async_setup_platform
    hass: HomeAssistantType,
    config: ConfigType,
    async_add_entities: Callable,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the sensor platform."""
    raw_sensor = config[CONF_PRICE_SENSOR]
    sensors = [PriceSensor(raw_sensor, config)]
    async_add_entities(sensors, update_before_add=True)


class PriceSensor(Entity):

    def __init__(self, raw_sensor: str, config):
        super().__init__()
        self.raw_sensor = raw_sensor
        self.variable_cost: dict[str, list[float]] = {}
        self.attrs: dict[str, Any] = {CONF_NAME: NAME}
        self._name = ENTITY_ID
        self._state = None
        self._available = True
        self._attr_unique_id = NAME
        self.config = config

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        return self._name

    @property
    def unique_id(self) -> str:
        """Return the unique ID of the sensor."""
        return self._attr_unique_id

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._available

    @property
    def state(self) -> str | None:
        return self._state

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return self.attrs

    async def async_update(self) -> None:  # async def async_update(

        # From https://github.com/jonasbkarlsson/ev_smart_charging/blob/main/custom_components/ev_smart_charging/helpers/config_flow.py
        price_state = hass.states.get(user_input[CONF_PRICE_SENSOR])
        attributes = price_state.attributes
        entry: RegistryEntry = entities.get(user_input[CONF_PRICE_SENSOR])

        # self.attrs[]
        format_of_date = self.format_of_dates()



    # Set ATTR_XXX To what they currently are.
    # State should be current total price, "today", "tomorrow", "total_ttoday" and "total_tomorrow" should be like nordpool


    def format_of_dates(self) -> str:
        """This assesses whether it is currently the date range for high or low fees
        This should be added in a format as:
            `YYYYMMDD - YYYYMMDD`, `YYMMDD-YYMMDD`, `MMDD-MMDD`, `MM-MM`
            `month - month` (e.g. `october - april`)
            `mon - mon` (e.g. `oct - apr`)
        """
        now = datetime.now()
        high_fee_dates_input = self.config[CONF_HIGH_FEE_DATES].replace(" ", "")
        high_fee_date_list = high_fee_dates_input.split(";")
        test_date_format = high_fee_dates_input
        format_of_date = ""
        if len(high_fee_date_list) > 1:
            test_date_format = high_fee_date_list[0]
        test_date_format_split = test_date_format.split("-")[0]
        try:
            int(test_date_format_split)
            if len(test_date_format_split) == 8:
                format_of_date = "%Y%m%d" # "YYYYMMDD"
            elif len(test_date_format_split) == 6:
                format_of_date = "%y%m%d"  # "yYMMDD"
            elif len(test_date_format_split) == 4:
                format_of_date = "%m%d"  # "MMDD"
            elif len(test_date_format_split) == 2:
                format_of_date = "%m"  # "MM"
        except ValueError:
            if len(test_date_format_split) != 3: # To take into account "may" could be full month or 3 letter abbrev.
                format_of_date = "%B"  # "month"
            else:
                if len(test_date_format.split("-")[1]) == 3:
                    format_of_date = "%b"  # "mon"
                else:
                    format_of_date = "%B"  # "month"

        return format_of_date


    def high_or_low_date_range(self, format_of_date: str) -> bool:

        high_fee_dates = self.config[CONF_HIGH_FEE_DATES].replace(" ", "")
        high_fee_dates = [i for i in high_fee_dates.split(";")]
        low_fee_dates = self.config[CONF_LOW_FEE_DATES].replace(" ", "")
        low_fee_dates = [i for i in low_fee_dates.split(";")]
        now = datetime.now()
        year = now.strpftime("%Y")
        month = now.strpftime("%m")
        date = now.strpftime("%d")

        for i in range(len(high_fee_dates)):
            if format_of_date in ["%B", "%b"]:
                start = datetime.strptime(high_fee_dates.split("-")[0].capitalize(), format_of_date)
                end = datetime.strptime(high_fee_dates.split("-")[1].capitalize(), format_of_date)
            elif format_of_date == "%Y%m%d":
                start = datetime.strptime(high_fee_dates.split("-")[0], format_of_date)
                end = datetime.strptime(high_fee_dates.split("-")[1], format_of_date)
            elif format_of_date == "%y%m%d":
                start = datetime.strptime(year + high_fee_dates.split("-")[0][2:], "%Y%m%d")
                end = datetime.strptime(year + high_fee_dates.split("-")[1][2:], "%Y%m%d")
            elif format_of_date == "%m%d":
                start = datetime.strptime(year + high_fee_dates.split("-")[0], "%Y%m%d")
                end = datetime.strptime(year + high_fee_dates.split("-")[1], "%Y%m%d")
            elif format_of_date == "%m":
                start = datetime.strptime(year + high_fee_dates.split("-")[0], "%Y%m")
                end = datetime.strptime(year + high_fee_dates.split("-")[1], "%Y%m")


    async def async_fee_to_use_next_two_days(self) -> dict[str, list[float]]:
        """
        fees_by_datetime = [
            {CONF_START_DATE:
            },
        ]

        """

        config = self.config
        date_format = "%m-%d"
        time_format = "%H:%M"
        high_fee_period = config[CONF_HIGH_FEE_DATES]

        # Get dicts of (keys) CONF_START_DATE, CONF_END_DATE, CONF_START_TIME, CONF_END_TIME
        # Each list item is one fee that is valid at a specified date and time range.
        fees_by_datetime: list[dict[str, Any]] = [val for key, val in config.items() if "transport_fee" in key]
        number_of_different_fees = len(fees_by_datetime)

            # Vinter = Oktober - Marts
            # Sommer = April - September
            # Lav last = 00:00 - 06:00; Høj last = 06:00 - 17:00 og 21:00 - 24:00, Spidslast = 17:00 - 21:00# for i in range(number_of_different_fees):

        # Find out if we are in summer or winter date range
        high_fee = 0.0
        start_date = ""
        end_date = ""
        for i in range(number_of_different_fees):
            fee = fees_by_datetime[i][CONF_TRANSPORT_FEE]
            for key, val in fees_by_datetime[i].items():
                if CONF_START_DATE in key:
                    start_date = fees_by_datetime[i][key]
                if CONF_END_DATE in key:
                    end_date = fees_by_datetime[i][key]
                if fee > high_fee:
                        if fees_by_datetime[i][key]



        hass.states.get(user_input[CONF_CHARGE])
        fees = [hass.states.get(user_input.keys())]
        CONF_TRANSPORT_FEE,
        CONF_START_DATE,
        CONF_END_DATE,
        CONF_START_TIME,
        CONF_END_TIME,

        today = [

        ]
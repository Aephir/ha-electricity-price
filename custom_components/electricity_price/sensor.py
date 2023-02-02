from __future__ import annotations

import logging
from typing import Any
from datetime import datetime, timedelta
from homeassistant import config_entries, core
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_NAME,
    ATTR_ICON
)
# from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback
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
    ATTR_CURRENCY,
    ATTR_COUNTRY,
    ATTR_REGION,
    ATTR_STATE_CLASS,
    ATTR_LAST_UPDATED,
    CONF_TRANSPORT_FEE_LOW_DATES_LOW_LOAD,
    CONF_TRANSPORT_FEE_LOW_DATES_HIGH_LOAD,
    CONF_TRANSPORT_FEE_LOW_DATES_PEAK_LOAD,
    CONF_TRANSPORT_FEE_HIGH_DATES_LOW_LOAD,
    CONF_TRANSPORT_FEE_HIGH_DATES_HIGH_LOAD,
    CONF_TRANSPORT_FEE_HIGH_DATES_PEAK_LOAD,
    CONF_HIGH_FEE_DATES,
    CONF_LOW_LOAD_TIMES,
    CONF_HIGH_LOAD_TIMES,
    CONF_PEAK_LOAD_TIMES,
    CONST_HOURS,
)
from .validation_helpers import number_validation, percentage_validation

_LOGGER = logging.getLogger(__name__)
# Time between updating data from GitHub
SCAN_INTERVAL = timedelta(minutes=10)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_PRICE_SENSOR): cv.entity_id,
        vol.Optional(CONF_TAX): cv.string,  # percentage_validation,
        vol.Optional(CONF_CHARGE): cv.string,  # number_validation,
        vol.Optional(CONF_TRANSPORT_FEE): cv.string,  # number_validation,
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


def setup_platform(
    hass: HomeAssistantType,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the sensor platform."""
    raw_sensor = config[CONF_PRICE_SENSOR]
    sensors = [PriceSensor(raw_sensor, config)]
    add_entities(sensors, update_before_add=True)


def format_time_slots(time_slot: str) -> list[str]:
    """Format the input to usable datetime objects to compare
    This should be added in a format as:
        `HH:MM - HH:MM`, `HH:MM - HH:MM; HH:MM - HH:MM`
        `HH - HH`, `HH - HH; HH - HH`
    """
    input_times: list[str] = time_slot.split("-")
    hour_list: list[str] = [i.split(":")[0] for i in input_times]
    hour_list = ["0" + i if len(i) == 1 else i for i in hour_list]

    return hour_list


def last_updated() -> str:
    """Returns a string in the format of YYY-MM-DDTHH:MM:SS+HH:MM showing when the sensor was updated"""
    return datetime.strftime(datetime.now(), "%Y-%m-%dT%H:%M:%S") + "+01:00"


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

    async def async_update(self) -> None:
        """Updates the sensor"""

        price_state = self.config[CONF_PRICE_SENSOR]
        attributes = price_state.attributes
        tax = 1 + (float(self.config[CONF_TAX])/100)
        flat_fee = float(self.config[CONF_CHARGE])
        total_today: list[float] = []
        total_tomorrow: list[float] = []

        format_of_date: str = self.determine_format_of_dates()
        high_fee_date_range: list[bool] = self.high_or_low_date_range(format_of_date)
        today_fees, tomorrow_fees, now_price = self.get_time_slots(high_fee_date_range)

        if attributes["today"]:
            try:
                total_today = [
                    round((float(attributes["today"][i]) + today_fees[i] + flat_fee) * tax, 2) for i in range(24)
                ]
            except IndexError:
                total_today = 24 * [0.0]
        if attributes["tomorrow"]:
            try:
                total_tomorrow = [
                    round((float(attributes["tomorrow"][i]) + today_fees[i] + flat_fee) * tax, 2) for i in range(24)
                ]
            except IndexError:
                total_tomorrow = []

        self.attrs[ATTR_TODAY] = total_today
        self.attrs[ATTR_TOMORROW] = total_tomorrow
        self.attrs[ATTR_CURRENCY] = attributes[ATTR_CURRENCY]
        self.attrs[ATTR_COUNTRY] = attributes[ATTR_COUNTRY]
        self.attrs[ATTR_REGION] = attributes[ATTR_REGION]
        self.attrs[ATTR_STATE_CLASS] = attributes[ATTR_STATE_CLASS]
        self.attrs[ATTR_LAST_UPDATED] = last_updated()
        self.attrs[ATTR_ICON] = "mdi:flash"

        self._state = now_price

    def determine_format_of_dates(self) -> str:
        """This assesses whether it is currently the date range for high or low fees
        This should be added in a format as:
            `YYYYMMDD - YYYYMMDD`, `YYMMDD-YYMMDD`, `MMDD-MMDD`, `MM-MM`
            `month - month` (e.g. `october - april`)
            `mon - mon` (e.g. `oct - apr`)
        """
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
                format_of_date = "%Y%m%d"  # "YYYYMMDD"
            elif len(test_date_format_split) == 6:
                format_of_date = "%y%m%d"  # "yYMMDD"
            elif len(test_date_format_split) == 4:
                format_of_date = "%m%d"  # "MMDD"
            elif len(test_date_format_split) == 2:
                format_of_date = "%m"  # "MM"
        except ValueError:
            if len(test_date_format_split) != 3:  # To take into account "may" could be full month or 3 letter abbrev.
                format_of_date = "%B"  # "month"
            else:
                if len(test_date_format.split("-")[1]) == 3:
                    format_of_date = "%b"  # "mon"
                else:
                    format_of_date = "%B"  # "month"

        return format_of_date

    def high_or_low_date_range(self, format_of_date: str) -> list[bool]:
        """Determine whether we are in the high charge date range (typically winter)
        or low charge date range (typically summer).
        Takes into account numerous ways that this information could be input during setup.
        Only uses "high fee dates", and assumes that re remaining are "low fee dates".
        :return list[bool]
        """
        high_fee_date_range = [False, False]
        high_fee_dates = self.config[CONF_HIGH_FEE_DATES].replace(" ", "")
        high_fee_dates = [i for i in high_fee_dates.split(";")]
        # low_fee_dates = self.config[CONF_LOW_FEE_DATES].replace(" ", "")
        # low_fee_dates = [i for i in low_fee_dates.split(";")]
        today = datetime.now()
        # tomorrow = today + timedelta(days=1)
        year_today = datetime.strftime(today, "%Y")
        # month_today = datetime.strftime(today, "%m")
        # date_today = datetime.strftime(today, "%d")
        # year_tomorrow = datetime.strftime(tomorrow, "%Y")
        # month_tomorrow = datetime.strftime(tomorrow, "%m")
        # date_tomorrow = datetime.strftime(tomorrow, "%d")
        start_dates: list[datetime] = []
        end_dates: list[datetime] = []

        for i in range(len(high_fee_dates)):
            if format_of_date in ["%B", "%b"]:
                start = datetime.strptime(high_fee_dates[i].split("-")[0].capitalize(), format_of_date)
                end = datetime.strptime(high_fee_dates[i].split("-")[1].capitalize(), format_of_date)
            elif format_of_date == "%Y%m%d":
                start = datetime.strptime(high_fee_dates[i].split("-")[0], format_of_date)
                end = datetime.strptime(high_fee_dates[i].split("-")[1], format_of_date)
            elif format_of_date == "%y%m%d":
                start = datetime.strptime(year_today + high_fee_dates[i].split("-")[0][2:], "%Y%m%d")
                end = datetime.strptime(year_today + high_fee_dates[i].split("-")[1][2:], "%Y%m%d")
            elif format_of_date == "%m%d":
                start = datetime.strptime(year_today + high_fee_dates[i].split("-")[0], "%Y%m%d")
                end = datetime.strptime(year_today + high_fee_dates[i].split("-")[1], "%Y%m%d")
            else:  # format_of_date == "%m":
                start = datetime.strptime(year_today + high_fee_dates[i].split("-")[0], "%Y%m")
                end = datetime.strptime(year_today + high_fee_dates[i].split("-")[1], "%Y%m")
            start_dates.append(start)
            end_dates.append(end)

        for i in range(len(start_dates)):
            if start_dates[i] < today < end_dates[i]:
                high_fee_date_range[0] = True

        for i in range(len(start_dates)):
            if start_dates[i] < today < end_dates[i]:
                high_fee_date_range[1] = True

        return high_fee_date_range

    def get_time_slots(self, high_fee_date_range: list[bool]) -> tuple[list[float], list[float], float]:
        """Determine the time slots for different fees for today and tomorrow"""

        # Get all input time ranges, trim whitespaces and split them into a list (to account for several time ranges).
        low_transport_hours: list[str] = [i for i in self.config[CONF_LOW_LOAD_TIMES].replace(" ", "").split(";")]
        high_transport_hours: list[str] = [i for i in self.config[CONF_HIGH_LOAD_TIMES].replace(" ", "").split(";")]
        peak_transport_hours: list[str] = [i for i in self.config[CONF_PEAK_LOAD_TIMES].replace(" ", "").split(";")]

        # A list of all time ranges given as a list of two hours in 24h format (start and finish times)
        low_transport_hours: list[list[str]] = [format_time_slots(i) for i in low_transport_hours]
        high_transport_hours: list[list[str]] = [format_time_slots(i) for i in high_transport_hours]
        peak_transport_hours: list[list[str]] = [format_time_slots(i) for i in peak_transport_hours]

        # Get the low, high, and peak fees for today and tomorrow, based on the `high_fee_date_range`
        if high_fee_date_range[0]:
            today_low_fee: float = float(self.config[CONF_TRANSPORT_FEE_HIGH_DATES_LOW_LOAD])
            today_high_fee: float = float(self.config[CONF_TRANSPORT_FEE_HIGH_DATES_HIGH_LOAD])
            today_peak_fee: float = float(self.config[CONF_TRANSPORT_FEE_HIGH_DATES_PEAK_LOAD])
        else:
            today_low_fee: float = float(self.config[CONF_TRANSPORT_FEE_LOW_DATES_LOW_LOAD])
            today_high_fee: float = float(self.config[CONF_TRANSPORT_FEE_LOW_DATES_HIGH_LOAD])
            today_peak_fee: float = float(self.config[CONF_TRANSPORT_FEE_LOW_DATES_PEAK_LOAD])

        if high_fee_date_range[1]:
            tomorrow_low_fee: float = float(self.config[CONF_TRANSPORT_FEE_HIGH_DATES_LOW_LOAD])
            tomorrow_high_fee: float = float(self.config[CONF_TRANSPORT_FEE_HIGH_DATES_HIGH_LOAD])
            tomorrow_peak_fee: float = float(self.config[CONF_TRANSPORT_FEE_HIGH_DATES_PEAK_LOAD])
        else:
            tomorrow_low_fee: float = float(self.config[CONF_TRANSPORT_FEE_LOW_DATES_LOW_LOAD])
            tomorrow_high_fee: float = float(self.config[CONF_TRANSPORT_FEE_LOW_DATES_HIGH_LOAD])
            tomorrow_peak_fee: float = float(self.config[CONF_TRANSPORT_FEE_LOW_DATES_PEAK_LOAD])

        # Create list for the 24 hours of the day today or tomorrow with the fees to add for each hour.
        today_fees: list[float] = [
            today_low_fee if any(
                [
                    int(low_transport_hours[i][0]) < int(CONST_HOURS[i]) < int(low_transport_hours[i][1]) for i in
                    range(len(low_transport_hours))
                ]
            ) else
            today_high_fee if any(
                [
                    int(high_transport_hours[i][0]) < int(CONST_HOURS[i]) < int(high_transport_hours[i][1]) for i in
                    range(len(high_transport_hours))
                ]
            ) else
            today_peak_fee if any(
                [
                    int(peak_transport_hours[i][0]) < int(CONST_HOURS[i]) < int(peak_transport_hours[i][1]) for i in
                    range(len(peak_transport_hours))
                ]
            ) else
            0.0 for j in range(24)
        ]
        tomorrow_fees: list[float] = [
            tomorrow_low_fee if any(
                [
                    int(low_transport_hours[i][0]) < int(CONST_HOURS[i]) < int(low_transport_hours[i][1]) for i in
                    range(len(low_transport_hours))
                ]
            ) else
            tomorrow_high_fee if any(
                [
                    int(high_transport_hours[i][0]) < int(CONST_HOURS[i]) < int(high_transport_hours[i][1]) for i in
                    range(len(high_transport_hours))
                ]
            ) else
            tomorrow_peak_fee if any(
                [
                    int(peak_transport_hours[i][0]) < int(CONST_HOURS[i]) < int(peak_transport_hours[i][1]) for i in
                    range(len(peak_transport_hours))
                ]
            ) else
            0.0 for j in range(24)
        ]

        now_hour = int(datetime.strftime(datetime.now(), "%H"))
        now_fee = today_fees[now_hour] + float(self.config[ATTR_TODAY][now_hour])

        return today_fees, tomorrow_fees, now_fee

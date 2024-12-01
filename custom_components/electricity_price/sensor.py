from __future__ import annotations

from pyeloverblik import Eloverblik
import json
import asyncio
import logging
from typing import Any
from datetime import datetime, timedelta
from pytz import timezone
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
from homeassistant.helpers.event import async_track_state_change
from homeassistant.helpers.typing import (
    ConfigType,
    DiscoveryInfoType,
    HomeAssistantType,
)
from homeassistant.util.dt import get_time_zone
from homeassistant.helpers.debounce import Debouncer
from homeassistant.core import callback
import voluptuous as vol
from functools import partial

from .const import (
    CONF_PRICE_SENSOR,
    DOMAIN,
    NAME,
    ENTITY_ID,
    ATTR_TODAY,
    ATTR_TOMORROW,
    ATTR_RAW_TODAY,
    ATTR_RAW_TOMORROW,
    ATTR_CURRENCY,
    ATTR_COUNTRY,
    ATTR_REGION,
    ATTR_STATE_CLASS,
    ATTR_LAST_UPDATED,
    CONF_ELOVERBLIK_TOKEN,
    CONF_METERING_POINT,
    ATTR_TRANS_NETTARIF,
    ATTR_SYSTEMTARIF,
    ATTR_ELAFGIFT,
    ATTR_HOUR_NETTARIF,
    CONF_DEFAULT_SUMMER_TARIFS,
    CONF_DEFAULT_WINTER_TARIFS,
)

_LOGGER = logging.getLogger(__name__)

# Time between updating data
# I should see if it can subscribe to changes in Nordpool sensor instead.
# https://developers.home-assistant.io/docs/integration_listen_events#tracking-entity-state-changes
# Maybe async_track_state_change ??
SCAN_INTERVAL = timedelta(minutes=10)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_PRICE_SENSOR): cv.entity_id,
        vol.Optional(CONF_ELOVERBLIK_TOKEN): cv.string,
        vol.Optional(CONF_METERING_POINT): cv.string,
    }
)


async def async_setup_entry(
        hass: core.HomeAssistant,
        config_entry: config_entries.ConfigEntry,
        async_add_entities
) -> None:
    """Setup sensors from a config entry created in the integrations UI."""
    config = hass.data[DOMAIN][config_entry.entry_id]
    # Update our config to include new repos and remove those that have been removed.
    if config_entry.options:
        config.async_update()
    # session = async_get_clientsession(hass)
    raw_sensor = config[CONF_PRICE_SENSOR]
    sensors = [PriceSensor(hass, raw_sensor, config)]
    async_add_entities(sensors, update_before_add=True)


def setup_platform(
        hass: HomeAssistantType,
        config: ConfigType,
        add_entities: AddEntitiesCallback,
        discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the sensor platform."""
    raw_sensor = config[CONF_PRICE_SENSOR]
    sensors = [PriceSensor(hass, raw_sensor, config)]
    add_entities(sensors, update_before_add=True)


def last_updated() -> str:
    """Returns a string in the format of YYY-MM-DDTHH:MM:SS+HH:MM showing when the sensor was updated
    :rtype: object
    """
    return datetime.strftime(datetime.now(), "%Y-%m-%dT%H:%M:%S") + "+01:00"


class PriceSensor(Entity):

    def __init__(self, hass: HomeAssistantType, raw_sensor: str, config):
        super().__init__()
        self.hass = hass
        self.raw_sensor = raw_sensor
        self.variable_cost: dict[str, list[float]] = {}
        self.attrs: dict[str, Any] = {CONF_NAME: NAME}
        self._name = NAME
        self._state = None
        self._available = True
        self._attr_unique_id = ENTITY_ID
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

    async def async_added_to_hass(self):
        """Run when the entity is added to Home Assistant."""
        await super().async_added_to_hass()

        self._debouncer = Debouncer(
            self.hass,
            _LOGGER,
            cooldown=0.1,  # 100ms cooldown to batch multiple triggers
            immediate=True,  # Allow an immediate update on the first call
        )

        @callback
        async def async_update_callback(entity_id, old_state, new_state):
            """Update the sensor when the Nordpool sensor updates."""
            if not new_state:
                return

            # Log the change for debugging
            _LOGGER.debug(
                "State or attributes changed for %s: %s -> %s",
                entity_id,
                old_state.attributes if old_state else None,
                new_state.attributes if new_state else None,
            )

            # Schedule the debounced update
            await self._debouncer.async_call()

        # Track state changes for the Nordpool sensor
        self.async_on_remove(
            async_track_state_change(self.hass, self.config[CONF_PRICE_SENSOR], async_update_callback)
        )

    async def async_update(self) -> None:
        """Updates the sensor asynchronously."""
        try:
            tariffs = await self.fetch_tariffs()  # Fetch tariffs via Eloverblik
            total_prices = await self.calculate_total(tariffs)

            # Get the current hour as an index for the state
            current_hour = datetime.now().hour
            self._state = total_prices[ATTR_TODAY][current_hour]  # Use the hourly price

            # Populate attributes
            self.attrs[ATTR_TODAY] = total_prices[ATTR_TODAY]
            self.attrs[ATTR_TOMORROW] = total_prices[ATTR_TOMORROW]
            self.attrs[ATTR_TRANS_NETTARIF] = tariffs.get("transmissions_nettarif", 0)
            self.attrs[ATTR_SYSTEMTARIF] = tariffs.get("systemtarif", 0)
            self.attrs[ATTR_ELAFGIFT] = tariffs.get("elafgift", 0)
            self.attrs[ATTR_CURRENCY] = "DKK"
            self.attrs[ATTR_COUNTRY] = "Denmark"
            self.attrs[ATTR_REGION] = "DK2"
            self.attrs[ATTR_STATE_CLASS] = "total"
            self.attrs[ATTR_LAST_UPDATED] = datetime.now().isoformat()
            self.attrs[ATTR_ICON] = "mdi:flash"

            # Initialize dictionary to hold prices with timestamps
            total_prices_with_times = {}

            # Add start and end timestamps to total_prices
            total_prices_with_times[ATTR_TODAY] = self.add_time_stamps(total_prices[ATTR_TODAY], "today")
            total_prices_with_times[ATTR_TOMORROW] = self.add_time_stamps(total_prices[ATTR_TOMORROW], "tomorrow")

            # Assign processed timestamps to attributes
            self.attrs[ATTR_RAW_TODAY] = total_prices_with_times[ATTR_TODAY]
            self.attrs[ATTR_RAW_TOMORROW] = total_prices_with_times[ATTR_TOMORROW]

            self._available = True
        except Exception as e:
            _LOGGER.error("Unexpected error in async_update: %s", e)
            self._available = False

    def add_time_stamps(self, prices: list, day: str) -> list:
        """Attach timestamps to hourly prices with time zone awareness."""
        # Get Home Assistant's configured time zone
        tz = get_time_zone(self.hass.config.time_zone)
        if not tz:
            raise ValueError("Time zone could not be determined from Home Assistant configuration.")

        base_date = datetime.now(tz)
        if day == "tomorrow":
            base_date += timedelta(days=1)

        return [
            {
                "start": (base_date.replace(hour=i, minute=0, second=0, microsecond=0)).isoformat(),
                "end": (base_date.replace(hour=i, minute=0, second=0, microsecond=0) + timedelta(hours=1)).isoformat(),
                "value": price,
            }
            for i, price in enumerate(prices)
        ]

    async def fetch_tariffs(self) -> dict:
        """Fetch tariffs from Eloverblik."""
        try:
            client = Eloverblik(self.config.get(CONF_ELOVERBLIK_TOKEN))
            tariffs = await self.hass.async_add_executor_job(client.get_tariffs, self.config.get(CONF_METERING_POINT))
            return tariffs.charges  # Extract charges dictionary
        except Exception as e:
            _LOGGER.error("Failed to fetch tariffs: %s", e)
            return {}  # Return an empty dict to avoid crashing

    async def async_get_sensor_data(self):
        """Get sensor data asynchronously."""
        all_fees = {}  # Placeholder for fee calculation logic
        total_prices = await self.calculate_total(all_fees)  # Use await here
        return all_fees, total_prices

    async def async_get_fees(self):
        """Get metering data from the Eloverblik API asynchronously."""
        _token = self.config[CONF_ELOVERBLIK_TOKEN]
        _metering_point = self.config[CONF_METERING_POINT]

        def fetch_metering_data():
            client = Eloverblik(_token)
            data = client.get_latest(_metering_point)
            _LOGGER.debug("Eloverblik response: _status=%s, _metering_data=%s", data._status, data._metering_data)
            if data._status != 200 or not data._metering_data:
                raise ValueError("Invalid or empty response from Eloverblik API")
            return data._metering_data

        try:
            # Fetch metering data asynchronously
            metering_data = await self.hass.async_add_executor_job(fetch_metering_data)

            # Process metering data (e.g., calculate totals, apply fees if needed)
            # Example assumes metering_data represents hourly values in raw format.
            hourly_costs = [value * 10 for value in metering_data]  # Example: Multiply by 10 for DKK/kWh

            return {
                ATTR_TODAY: hourly_costs,  # Adjust logic to split into today/tomorrow if needed
                ATTR_TRANS_NETTARIF: 0,  # Placeholder if fees need to be added
                ATTR_SYSTEMTARIF: 0,  # Placeholder for additional tarif data
                ATTR_ELAFGIFT: 0  # Placeholder for taxes
            }
        except Exception as e:
            _LOGGER.error("Failed to get metering data: %s", e)
            raise

    @staticmethod
    def day_before_summer_or_winter() -> str:
        """Determine if it is the day before tarifs change.
        This happens on March 1st and October 1st."""

        today_month = int(datetime.now().strftime("%m"))
        tomorrow_month = int((datetime.now() + timedelta(days=1)).strftime("%m"))

        transition_to = "none"

        if today_month == 2 and tomorrow_month == 3:
            transition_to = "summer"
        elif today_month == 9 and tomorrow_month == 10:
            transition_to = "winter"

        return transition_to

    async def wait_for_sensor(self, sensor_id, timeout=30):
        """Wait for a sensor to become available."""
        for _ in range(timeout):
            state = self.hass.states.get(sensor_id)
            if state:
                return state
            _LOGGER.warning("Waiting for sensor '%s' to become available", sensor_id)
            await asyncio.sleep(1)
        _LOGGER.error("Sensor '%s' did not become available within %s seconds", sensor_id, timeout)
        return None

    async def calculate_total(self, tariffs):
        """Calculate the total electricity prices, including fees and VAT."""
        sensor_id = self.config.get(CONF_PRICE_SENSOR)
        price_sensor_state = await self.wait_for_sensor(sensor_id)

        if price_sensor_state is None:
            _LOGGER.error("Failed to fetch sensor '%s'. Skipping calculation.", sensor_id)
            return {"today": [0] * 24, "tomorrow": [0] * 24}

        # Extract raw prices from the Nordpool sensor
        raw_today_prices = price_sensor_state.attributes.get(ATTR_TODAY, [0] * 24)
        raw_tomorrow_prices = price_sensor_state.attributes.get(ATTR_TOMORROW, [0] * 24)

        # Fixed fees
        transmission_fee = tariffs.get("transmissions_nettarif", 0)
        system_tariff = tariffs.get("systemtarif", 0)
        electricity_tax = tariffs.get("elafgift", 0)

        # Variable fees (hourly)
        nettarif_c = tariffs.get("nettarif_c", [0] * 24)

        # Calculate total prices with fees and VAT
        total_today = [
            round(
                p + transmission_fee + system_tariff + electricity_tax + nettarif_c[i],
                3,
            )
            for i, p in enumerate(raw_today_prices)
        ]
        total_tomorrow = [
            round(
                p + transmission_fee + system_tariff + electricity_tax + nettarif_c[i],
                3,
            )
            for i, p in enumerate(raw_tomorrow_prices)
        ]

        # Add VAT (25%)
        total_today = [round(price * 1.25, 3) for price in total_today]
        total_tomorrow = [round(price * 1.25, 3) for price in total_tomorrow]

        return {
            ATTR_TODAY: total_today,
            ATTR_TOMORROW: total_tomorrow,
            "total_fees": {
                "fixed": round(transmission_fee + system_tariff + electricity_tax, 3),
                "variable": nettarif_c,
            },
        }

    @staticmethod
    def price_now(total_prices):
        """Get the current price to use as the state"""

        hour_now = int(datetime.now().strftime("%-H"))
        state = total_prices[ATTR_TODAY][hour_now]

        return state

    def parse_total_with_times(self, total_prices) -> dict[str, list[dict[str, Any]]]:
        """Parse total prices for an attribute compatible with nordpool sensor"""

        today_values = total_prices[ATTR_TODAY]
        tomorrow_values = total_prices[ATTR_TOMORROW]

        string_times: list[str] = self.make_time_list()
        today_times: list[str] = string_times[:25]
        total_today = [{"time": today_times[i], "value": today_values[i]} for i in range(24)]
        # total_today = [{"start": today_times[i], "end": today_times[i + 1], "value": today_values[i]} for i in
        #                range(24)]
        if all([len(tomorrow_values) == 24, tomorrow_values is not None,
                len(tomorrow_values) > 0]):  # tomorrow_values[0] is not None]):
            tomorrow_times = string_times[24:]
            total_tomorrow = [{"start": tomorrow_times[i], "end": tomorrow_times[i + 1], "value": tomorrow_values[i]}
                              for i in range(24)]
        else:
            total_tomorrow = []

        total_prices_with_times: dict[str, list[dict[str, Any]]] = {
            ATTR_TODAY: total_today,
            ATTR_TOMORROW: total_tomorrow
        }

        return total_prices_with_times

    @staticmethod
    def make_time_list() -> list[str]:
        """Make strings of times for the attributes "total_today" and "total_tomorrow"."""
        copenhagen_tz = timezone('Europe/Copenhagen')
        format_of_datetime = "%Y-%m-%dT%H:%M:%S%z"
        now = datetime.now(copenhagen_tz)  # Current time in Copenhagen timezone
        today_date = now.date()
        today_midnight = copenhagen_tz.localize(datetime.combine(today_date, datetime.min.time()))
        today_from_midnight = [today_midnight + timedelta(hours=i) for i in range(49)]

        # Format times including the correct offset for Copenhagen considering DST
        string_times = [dt.strftime(format_of_datetime) for dt in today_from_midnight]

        return string_times

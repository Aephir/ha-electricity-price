from __future__ import annotations

import asyncio
import logging
from typing import Any
from datetime import datetime, timedelta
from pytz import timezone

from pyeloverblik import Eloverblik
import voluptuous as vol

from homeassistant import config_entries, core
from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorDeviceClass
from homeassistant.const import CONF_NAME, UnitOfEnergy
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_state_change
from homeassistant.util import dt as dt_util
from homeassistant.helpers.debounce import Debouncer

from .const import (
    CONF_PRICE_SENSOR,
    DOMAIN,
    NAME,
    ENTITY_ID,
    ATTR_STATE_CLASS,
    ATTR_AVERAGE,
    ATTR_UNIT,
    ATTR_TODAY,
    ATTR_TOMORROW,
    ATTR_RAW_TODAY,
    ATTR_RAW_TOMORROW,
    ATTR_CURRENCY,
    ATTR_COUNTRY,
    ATTR_REGION,
    ATTR_LAST_UPDATED,
    CONF_ELOVERBLIK_TOKEN,
    CONF_METERING_POINT,
    ATTR_TRANS_NETTARIF,
    ATTR_SYSTEMTARIF,
    ATTR_ELAFGIFT,
    ATTR_TOMORROW_VALID,
    CURRENCY,
    COUNTRY,
    ICON,
)

_LOGGER = logging.getLogger(__name__)

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
        hass: core.HomeAssistant,
        config: dict[str, Any],
        add_entities: AddEntitiesCallback,
        discovery_info: dict[str, Any] | None = None,
) -> None:
    """Set up the sensor platform."""
    raw_sensor = config[CONF_PRICE_SENSOR]
    sensors = [PriceSensor(hass, raw_sensor, config)]
    add_entities(sensors, update_before_add=True)


class PriceSensor(Entity):

    def __init__(self, hass: core.HomeAssistant, raw_sensor: str, config):
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
    def unit_of_measurement(self) -> str:
        """Return the unit of measurement."""
        return f"{CURRENCY}/kWh"

    @property
    def icon(self) -> str:
        """Return the icon to use in the frontend."""
        return ICON

    @property
    def device_class(self) -> SensorDeviceClass | None:
        """Return the device class of the sensor."""
        return SensorDeviceClass.MONETARY

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

            # Initialize dictionary to hold prices with timestamps
            total_prices_with_times = {}

            # Add start and end timestamps to total_prices
            total_prices_with_times[ATTR_TODAY] = self.add_time_stamps(total_prices[ATTR_TODAY], "today")
            total_prices_with_times[ATTR_TOMORROW] = self.add_time_stamps(total_prices[ATTR_TOMORROW], "tomorrow")

            # Get the current time and set the state based on the current interval
            now = dt_util.now().astimezone()

            matched = False
            for entry in total_prices_with_times[ATTR_TODAY]:
                start = datetime.fromisoformat(entry["start"])
                end = datetime.fromisoformat(entry["end"])
                if start <= now < end:
                    self._state = entry["value"]
                    matched = True
                    break

            if not matched:
                _LOGGER.warning("No matching interval found for now=%s", now)
                self._state = None

            # Determine whether tomorrows prices are available.
            tomorrow_valid = bool(total_prices[ATTR_TOMORROW])  # True if not empty, False otherwise

            # Get region from the price sensor
            price_sensor_state = self.hass.states.get(self.config[CONF_PRICE_SENSOR])
            region = price_sensor_state.attributes.get("region", "DK2") if price_sensor_state else "DK2"

            # Populate attributes
            self.attrs[ATTR_STATE_CLASS] = "total"
            self.attrs[ATTR_UNIT] = "kWh"
            self.attrs[ATTR_CURRENCY] = CURRENCY
            self.attrs[ATTR_COUNTRY] = COUNTRY
            self.attrs[ATTR_REGION] = region
            self.attrs[ATTR_TODAY] = total_prices[ATTR_TODAY]
            self.attrs[ATTR_TOMORROW] = total_prices[ATTR_TOMORROW]
            self.attrs[ATTR_TOMORROW_VALID] = tomorrow_valid
            self.attrs[ATTR_RAW_TODAY] = total_prices_with_times[ATTR_TODAY]
            self.attrs[ATTR_RAW_TOMORROW] = total_prices_with_times[ATTR_TOMORROW]
            self.attrs[ATTR_TRANS_NETTARIF] = tariffs.get("transmissions_nettarif", 0)
            self.attrs[ATTR_SYSTEMTARIF] = tariffs.get("systemtarif", 0)
            self.attrs[ATTR_ELAFGIFT] = tariffs.get("elafgift", 0)
            self.attrs[ATTR_LAST_UPDATED] = datetime.now().isoformat()

            self._available = True

        except Exception as e:
            _LOGGER.error("Unexpected error in async_update: %s", e)
            self._available = False

    def add_time_stamps(self, prices: list, day: str) -> list:
        """Attach timestamps to hourly prices with time zone awareness."""
        # Get Home Assistant's configured time zone
        tz = timezone(self.hass.config.time_zone)

        base_date = datetime.now(tz)
        if day == "tomorrow":
            base_date += timedelta(days=1)

        return [
            {
                "start": (base_date.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(minutes=15 * i)).isoformat(),
                "end": (base_date.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(minutes=15 * (i + 1))).isoformat(),
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

        # Extract raw Nordpool prices (15‑min data)
        raw_today_prices = price_sensor_state.attributes.get("today", [])
        raw_tomorrow_prices = price_sensor_state.attributes.get("tomorrow", [])

        # If these are nested dicts like [{'time': '...', 'value': 0.123}], flatten them
        if raw_today_prices and isinstance(raw_today_prices[0], dict):
            raw_today_prices = [p["value"] for p in raw_today_prices]
        if raw_tomorrow_prices and isinstance(raw_tomorrow_prices[0], dict):
            raw_tomorrow_prices = [p["value"] for p in raw_tomorrow_prices]

        if price_sensor_state is None:
            _LOGGER.error("Failed to fetch sensor '%s'. Skipping calculation.", sensor_id)
            return {"today": [0] * 24, "tomorrow": [0] * 24}

        # Extract raw prices from the Nordpool sensor
        if len(raw_today_prices) not in (96, 100):
            _LOGGER.warning("Unexpected number of raw_today_prices: %d (expected 96 or 100)", len(raw_today_prices))
        if len(raw_tomorrow_prices) not in (0, 96, 100):
            _LOGGER.warning("Unexpected number of raw_tomorrow_prices: %d (expected 0, 96 or 100)", len(raw_tomorrow_prices))

        # Fixed fees
        transmission_fee = tariffs.get("transmissions_nettarif", 0)
        system_tariff = tariffs.get("systemtarif", 0)
        electricity_tax = tariffs.get("elafgift", 0)

        # Variable fees (hourly)
        nettarif_c = tariffs.get("nettarif_c", [0] * 24)

        # Expand nettarif_c to match the total number of intervals
        total_intervals = len(raw_today_prices) + len(raw_tomorrow_prices)
        if len(nettarif_c) == 24:
            nettarif_c = [val for val in nettarif_c for _ in range(4)]
        if len(nettarif_c) < total_intervals:
            _LOGGER.warning("Padding nettarif_c from %d to %d intervals", len(nettarif_c), total_intervals)
            nettarif_c.extend([0] * (total_intervals - len(nettarif_c)))
        elif len(nettarif_c) > total_intervals:
            _LOGGER.warning("Truncating nettarif_c from %d to %d intervals", len(nettarif_c), total_intervals)
            nettarif_c = nettarif_c[:total_intervals]

        # Log lenght of prices
        _LOGGER.warning("raw_today=%d raw_tomorrow=%d nettarif=%d",
                len(raw_today_prices), len(raw_tomorrow_prices), len(nettarif_c))

        # Calculate total prices with fees and VAT
        total_today = []
        for i, p in enumerate(raw_today_prices):
            if i >= len(nettarif_c):
                _LOGGER.error("Index %d out of range for nettarif_c (len=%d)", i, len(nettarif_c))
                break
            total_today.append(round(p + transmission_fee + system_tariff + electricity_tax + nettarif_c[i], 3))

        total_tomorrow = []
        for i, p in enumerate(raw_tomorrow_prices):
            index = i + len(total_today)
            if index >= len(nettarif_c):
                _LOGGER.error("Index %d out of range for nettarif_c (len=%d)", index, len(nettarif_c))
                break
            total_tomorrow.append(round(p + transmission_fee + system_tariff + electricity_tax + nettarif_c[index], 3))

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

from __future__ import annotations

import logging
from typing import Any
from datetime import datetime, timedelta

from homeassistant import config_entries, core
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util
from homeassistant.helpers.debounce import Debouncer

from .const import (
    CONF_PRICE_SENSOR,
    DOMAIN,
    NAME,
    ENTITY_ID,
    ATTR_STATE_CLASS,
    ATTR_UNIT,
    ATTR_TODAY,
    ATTR_TOMORROW,
    ATTR_RAW_TODAY,
    ATTR_RAW_TOMORROW,
    ATTR_CURRENCY,
    ATTR_COUNTRY,
    ATTR_REGION,
    ATTR_LAST_UPDATED,
    ATTR_TRANS_NETTARIF,
    ATTR_SYSTEMTARIF,
    ATTR_ELAFGIFT,
    ATTR_TOMORROW_VALID,
    CURRENCY,
    COUNTRY,
    ICON,
)
from .coordinator import TariffCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
        hass: core.HomeAssistant,
        config_entry: config_entries.ConfigEntry,
        async_add_entities
) -> None:
    """Setup sensors from a config entry created in the integrations UI."""
    config = hass.data[DOMAIN][config_entry.entry_id]
    coordinator: TariffCoordinator = config["coordinator"]
    raw_sensor = config[CONF_PRICE_SENSOR]
    sensors = [PriceSensor(hass, raw_sensor, config, coordinator)]
    async_add_entities(sensors)


class PriceSensor(CoordinatorEntity[TariffCoordinator], Entity):

    def __init__(self, hass: core.HomeAssistant, raw_sensor: str, config, coordinator: TariffCoordinator):
        super().__init__(coordinator)
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
        await super().async_added_to_hass()  # Subscribes to coordinator (tariff) updates

        self._debouncer = Debouncer(
            self.hass,
            _LOGGER,
            cooldown=2,  # Collapse bursts of Nordpool attribute updates
            immediate=True,  # Allow an immediate recompute on the first call
            function=self._async_recompute,
        )

        async def async_update_callback(event) -> None:
            """Recompute the price when the Nordpool sensor updates."""
            new_state = event.data.get("new_state")
            if not new_state:
                return

            _LOGGER.debug("State changed for %s: %s", event.data.get("entity_id"), new_state.attributes)

            # Schedule the debounced recompute
            await self._debouncer.async_call()

        # Track state changes for the Nordpool sensor
        self.async_on_remove(
            async_track_state_change_event(self.hass, self.config[CONF_PRICE_SENSOR], async_update_callback)
        )

        await self._async_recompute()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Recompute the price when the coordinator has fresh tariffs."""
        self.hass.async_create_task(self._async_recompute())

    async def _async_recompute(self) -> None:
        """Recalculate the sensor state from the cached tariffs and the latest Nordpool prices."""
        try:
            tariffs = self.coordinator.data or {}
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
            self.attrs[ATTR_LAST_UPDATED] = dt_util.now().isoformat()

            self._available = True

        except Exception as e:
            _LOGGER.error("Unexpected error while recomputing price: %s", e)
            self._available = False

        self.async_write_ha_state()

    def add_time_stamps(self, prices: list, day: str) -> list:
        """Attach timestamps to hourly prices, using Home Assistant's local time zone."""
        base_date = dt_util.now()
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

    async def calculate_total(self, tariffs):
        """Calculate the total electricity prices, including fees and VAT."""
        sensor_id = self.config.get(CONF_PRICE_SENSOR)
        price_sensor_state = self.hass.states.get(sensor_id)

        if price_sensor_state is None:
            _LOGGER.warning("Sensor '%s' is not available yet. Skipping calculation.", sensor_id)
            return {ATTR_TODAY: [], ATTR_TOMORROW: []}

        # Extract raw Nordpool prices (15‑min data)
        raw_today_prices = price_sensor_state.attributes.get("today", [])
        raw_tomorrow_prices = price_sensor_state.attributes.get("tomorrow", [])

        # If these are nested dicts like [{'time': '...', 'value': 0.123}], flatten them
        if raw_today_prices and isinstance(raw_today_prices[0], dict):
            raw_today_prices = [p["value"] for p in raw_today_prices]
        if raw_tomorrow_prices and isinstance(raw_tomorrow_prices[0], dict):
            raw_tomorrow_prices = [p["value"] for p in raw_tomorrow_prices]

        # Extract raw prices from the Nordpool sensor
        if len(raw_today_prices) not in (96, 100):
            _LOGGER.debug("Unexpected number of raw_today_prices: %d (expected 96 or 100)", len(raw_today_prices))
        if len(raw_tomorrow_prices) not in (0, 96, 100):
            _LOGGER.debug("Unexpected number of raw_tomorrow_prices: %d (expected 0, 96 or 100)", len(raw_tomorrow_prices))

        # Fixed fees
        transmission_fee = tariffs.get("transmissions_nettarif", 0)
        system_tariff = tariffs.get("systemtarif", 0)
        electricity_tax = tariffs.get("elafgift", 0)

        # Variable fees: Eloverblik returns one 24-value hourly profile (nettarif_c)
        # that applies to every day, so map each 15-min interval to its hour of day.
        hourly = list(tariffs.get("nettarif_c") or [0] * 24)
        if len(hourly) != 24:
            _LOGGER.warning("Unexpected nettarif_c length %d (expected 24); missing hours count as 0", len(hourly))
            hourly = (hourly + [0] * 24)[:24]

        def add_fees(prices: list[float]) -> list[float]:
            per_hour = max(1, round(len(prices) / 24)) if prices else 4
            return [
                round(p + transmission_fee + system_tariff + electricity_tax + hourly[min(i // per_hour, 23)], 3)
                for i, p in enumerate(prices)
            ]

        total_today = add_fees(raw_today_prices)
        total_tomorrow = add_fees(raw_tomorrow_prices)

        # Add VAT (25%)
        total_today = [round(price * 1.25, 3) for price in total_today]
        total_tomorrow = [round(price * 1.25, 3) for price in total_tomorrow]

        return {
            ATTR_TODAY: total_today,
            ATTR_TOMORROW: total_tomorrow,
            "total_fees": {
                "fixed": round(transmission_fee + system_tariff + electricity_tax, 3),
                "variable": hourly,
            },
        }

from __future__ import annotations

from pyeloverblik import Eloverblik
import json
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
    ATTR_TODAY,
    ATTR_TOMORROW,
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
from .validation_helpers import number_validation, percentage_validation

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
        """Updates the sensor
        TODO: Make the "Total today" and "Total tomorrow" attributes like Nordpool sensor has for easy ApexChart use"""

        all_fees, total_prices = self.get_sensor_data()

        # Is this how to get attributes from a Home Assistant entity_id (CONF_PRICE_SENSOR)?
        price_state = self.config[CONF_PRICE_SENSOR]
        attributes = price_state.attributes

        self.attrs[ATTR_TODAY] = total_prices[ATTR_TODAY]
        self.attrs[ATTR_TOMORROW] = total_prices[ATTR_TOMORROW]
        self.attrs[ATTR_TRANS_NETTARIF] = all_fees[ATTR_TODAY][ATTR_TRANS_NETTARIF]
        self.attrs[ATTR_SYSTEMTARIF] = all_fees[ATTR_TODAY][ATTR_SYSTEMTARIF]
        self.attrs[ATTR_ELAFGIFT] = all_fees[ATTR_TODAY][ATTR_ELAFGIFT]
        self.attrs[ATTR_CURRENCY] = attributes[ATTR_CURRENCY]
        self.attrs[ATTR_COUNTRY] = attributes[ATTR_COUNTRY]
        self.attrs[ATTR_REGION] = attributes[ATTR_REGION]
        self.attrs[ATTR_STATE_CLASS] = attributes[ATTR_STATE_CLASS]
        self.attrs[ATTR_LAST_UPDATED] = last_updated()
        self.attrs[ATTR_ICON] = "mdi:flash"

        self._state = self.price_now(total_prices)

    def get_sensor_data(self):
        """Create all data for sensor"""

        all_fees = self.get_fees
        total_prices = self.calculate_total(all_fees)
        self._state = self.price_now(total_prices)

        self.attrs[ATTR_TRANS_NETTARIF] = all_fees[ATTR_TRANS_NETTARIF]
        self.attrs[ATTR_SYSTEMTARIF] = all_fees[ATTR_SYSTEMTARIF]
        self.attrs[ATTR_ELAFGIFT] = all_fees[ATTR_ELAFGIFT]
        self.attrs[ATTR_HOUR_NETTARIF] = all_fees[ATTR_HOUR_NETTARIF]

        return all_fees, total_prices

    @property
    def get_fees(self) -> dict[dict[str, str]]:
        """Get fees from the eloverblik API.
        Default to using the ones in the sensor attributes if unavailable.
        TODO: Get both today and tomorrow fees.
        """

        _token = self.config[CONF_ELOVERBLIK_TOKEN]
        _metering_point = self.config[CONF_METERING_POINT]

        client = Eloverblik(_token)
        data = client.get_latest(_metering_point)
        if int(data.status) == 200:
            # {'transmissions_nettarif': 0.058, 'systemtarif': 0.054, 'elafgift': 0.008, 'nettarif_c_time': [0.1837, 0.1837, 0.1837, 0.1837, 0.1837, 0.1837, 0.5511, 0.5511, 0.5511, 0.5511, 0.5511, 0.5511, 0.5511, 0.5511, 0.5511, 0.5511, 0.5511, 1.6533, 1.6533, 1.6533, 1.6533, 0.5511, 0.5511, 0.5511]}
            charges = json.loads(data.charges)
            # Charges are in øre per Wh. Multiply by 1000 and divide by 100 (i.e., multiply by 10) to get DKK/kWh.
            trans_net_tarif = float(charges[ATTR_TRANS_NETTARIF]) * 10
            system_tarif = float(charges[ATTR_SYSTEMTARIF]) * 10
            elafgift = float(charges[ATTR_ELAFGIFT]) * 10
            hour_net_tarif = [float(i) * 10 for i in charges[ATTR_HOUR_NETTARIF]]
        else:
            trans_net_tarif = self.hass.states.get(ENTITY_ID).attribute.get(ATTR_TRANS_NETTARIF)
            system_tarif = self.hass.states.get(ENTITY_ID).attribute.get(ATTR_SYSTEMTARIF)
            elafgift = self.hass.states.get(ENTITY_ID).attribute.get(ATTR_ELAFGIFT)
            hour_net_tarif = self.hass.states.get(ENTITY_ID).attribute.get(ATTR_HOUR_NETTARIF)

            # Is this how to get?? self.hass.states.get(ENTITY_ID).attribute.get("ATTR_TARIFS")
        all_fees_today = {
            ATTR_TRANS_NETTARIF: trans_net_tarif,
            ATTR_SYSTEMTARIF: system_tarif,
            ATTR_ELAFGIFT: elafgift,
            ATTR_HOUR_NETTARIF: hour_net_tarif
        }

        if self.day_before_summer_or_winter() == "summer":
            all_fees_tomorrow = {
                ATTR_TRANS_NETTARIF: CONF_DEFAULT_SUMMER_TARIFS[ATTR_TRANS_NETTARIF],
                ATTR_SYSTEMTARIF: CONF_DEFAULT_SUMMER_TARIFS[ATTR_SYSTEMTARIF],
                ATTR_ELAFGIFT: CONF_DEFAULT_SUMMER_TARIFS[ATTR_ELAFGIFT],
                ATTR_HOUR_NETTARIF: CONF_DEFAULT_SUMMER_TARIFS[ATTR_HOUR_NETTARIF]
            }
        elif self.day_before_summer_or_winter() == "winter":
            all_fees_tomorrow = {
                ATTR_TRANS_NETTARIF: CONF_DEFAULT_WINTER_TARIFS[ATTR_TRANS_NETTARIF],
                ATTR_SYSTEMTARIF: CONF_DEFAULT_WINTER_TARIFS[ATTR_SYSTEMTARIF],
                ATTR_ELAFGIFT: CONF_DEFAULT_WINTER_TARIFS[ATTR_ELAFGIFT],
                ATTR_HOUR_NETTARIF: CONF_DEFAULT_WINTER_TARIFS[ATTR_HOUR_NETTARIF]
            }
        else:
            all_fees_tomorrow = all_fees_today

        all_fees = {
            ATTR_TODAY: all_fees_today,
            ATTR_TOMORROW: all_fees_tomorrow
        }

        return all_fees

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

    def calculate_total(self, all_fees: dict[dict[str, str]]) -> dict[str, list[Any]]:
        """Calculate all valuers for the sensor"""

        raw_today_prices = self.hass.states.get(CONF_PRICE_SENSOR).attribute.get(ATTR_TODAY)
        raw_tomorrow_prices = self.hass.states.get(CONF_PRICE_SENSOR).attribute.get(ATTR_TOMORROW)

        fees_today = [all_fees[ATTR_TODAY][ATTR_HOUR_NETTARIF][i] + all_fees[ATTR_TODAY][ATTR_TRANS_NETTARIF] +
                      all_fees[ATTR_TODAY][ATTR_SYSTEMTARIF] + all_fees[ATTR_TODAY][ATTR_ELAFGIFT] for i in
                      range(len(all_fees[ATTR_TODAY][ATTR_HOUR_NETTARIF]))]

        fees_tomorrow = [all_fees[ATTR_TOMORROW][ATTR_HOUR_NETTARIF][i] + all_fees[ATTR_TOMORROW][ATTR_TRANS_NETTARIF] +
                         all_fees[ATTR_TOMORROW][ATTR_SYSTEMTARIF] + all_fees[ATTR_TOMORROW][ATTR_ELAFGIFT] for i in
                         range(len(all_fees[ATTR_TOMORROW][ATTR_HOUR_NETTARIF]))]

        total_today_prices = [raw_today_prices[i] + fees_today[i] for i in range(len(raw_today_prices))]

        try:
            total_tomorrow_prices = [raw_tomorrow_prices[i] + fees_tomorrow[i] for i in range(len(raw_tomorrow_prices))]
        except TypeError:
            total_tomorrow_prices = []
        except IndexError:
            total_tomorrow_prices = []

        total_prices: dict[str, list[Any]] = {
            ATTR_TODAY: total_today_prices,
            ATTR_TOMORROW: total_tomorrow_prices
        }

        return total_prices

    @staticmethod
    def price_now(total_prices):
        """Get the current price to use as the state"""

        hour_now = int(datetime.now().strftime("%-H"))
        state = total_prices[ATTR_TODAY][hour_now]

        return state

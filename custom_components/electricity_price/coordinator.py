"""Coordinator responsible for periodically fetching Eloverblik tariffs.

Tariffs change rarely (at most a few times a year), so they are fetched on a
long interval and cached, independently of how often the Nordpool price
sensor updates.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from typing import Any

from pyeloverblik import Eloverblik

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

_LOGGER = logging.getLogger(__name__)

TARIFF_UPDATE_INTERVAL = timedelta(hours=6)
ELOVERBLIK_TIMEOUT = 30


class TariffCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Fetches and caches Eloverblik tariffs."""

    def __init__(self, hass: HomeAssistant, token: str, metering_point: str) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name="Eloverblik tariffs",
            update_interval=TARIFF_UPDATE_INTERVAL,
        )
        self._client = Eloverblik(token)
        self._metering_point = metering_point

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch tariffs from Eloverblik."""
        try:
            async with asyncio.timeout(ELOVERBLIK_TIMEOUT):
                tariffs = await self.hass.async_add_executor_job(
                    self._client.get_tariffs, self._metering_point
                )
            return tariffs.charges
        except TimeoutError as err:
            raise UpdateFailed("Timed out fetching Eloverblik tariffs") from err
        except Exception as err:
            raise UpdateFailed(f"Error fetching Eloverblik tariffs: {err}") from err

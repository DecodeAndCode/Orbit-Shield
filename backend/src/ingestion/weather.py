"""NOAA Space Weather Prediction Center data fetcher.

Fetches solar flux (F10.7) and geomagnetic indices (Kp, Ap) from NOAA SWPC
JSON endpoints. No authentication required.

These values affect atmospheric drag on LEO satellites and are inputs to
the space weather drag impact ML model.

API: https://services.swpc.noaa.gov/json/
"""

import logging
from dataclasses import dataclass
from datetime import datetime

import httpx

from src.config import settings

logger = logging.getLogger(__name__)


@dataclass
class SolarFluxRecord:
    """F10.7 cm radio flux measurement."""

    time_tag: datetime
    flux: float  # solar flux units (SFU)


@dataclass
class KpIndexRecord:
    """Planetary Kp geomagnetic index."""

    time_tag: datetime
    kp: float
    kp_fraction: float
    a_running: float


class SpaceWeatherClient:
    """Async client for NOAA SWPC space weather data."""

    def __init__(self, base_url: str | None = None):
        self.base_url = (base_url or settings.noaa_swpc_base_url).rstrip("/")

    async def fetch_f107_flux(self) -> list[SolarFluxRecord]:
        """Fetch recent F10.7 cm solar flux measurements.

        F10.7 is a key input for atmospheric density models (NRLMSISE-00, JB2008).
        """
        url = f"{self.base_url}/json/f107_cm_flux.json"
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url)
            response.raise_for_status()

        records = []
        for item in response.json():
            try:
                records.append(
                    SolarFluxRecord(
                        time_tag=datetime.fromisoformat(item["time_tag"]),
                        flux=float(item["flux"]),
                    )
                )
            except (ValueError, KeyError) as e:
                logger.warning(f"Skipping malformed F10.7 record: {e}")
        return records

    async def fetch_kp_index(self) -> list[KpIndexRecord]:
        """Fetch recent planetary Kp geomagnetic index values.

        Kp ranges 0 (quiet) to 9 (extreme storm). Values >= 5 indicate
        geomagnetic storms that increase atmospheric drag on LEO satellites.
        """
        url = f"{self.base_url}/json/planetary_k_index_1m.json"
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url)
            response.raise_for_status()

        records = []
        for item in response.json():
            try:
                records.append(
                    KpIndexRecord(
                        time_tag=datetime.fromisoformat(item["time_tag"]),
                        kp=float(item["kp"]),
                        kp_fraction=float(item.get("kp_fraction", item["kp"])),
                        a_running=float(item.get("a_running", 0)),
                    )
                )
            except (ValueError, KeyError) as e:
                logger.warning(f"Skipping malformed Kp record: {e}")
        return records

"""CelesTrak GP data fetcher.

Fetches orbital element data from CelesTrak's GP API in OMM JSON format.
No authentication required. Supports fetching by group or individual NORAD ID.

API: https://celestrak.org/NORAD/elements/gp.php
Rate limits: CelesTrak bans IPs after 100 HTTP errors in 2 hours.
"""

import logging
from dataclasses import dataclass
from datetime import datetime

import httpx

from src.config import settings

logger = logging.getLogger(__name__)


@dataclass
class GPRecord:
    """Parsed GP (General Perturbations) record from CelesTrak."""

    norad_id: int
    name: str
    object_type: str | None
    epoch: datetime
    mean_motion: float
    eccentricity: float
    inclination: float
    raan: float
    arg_perigee: float
    mean_anomaly: float
    bstar: float
    tle_line1: str | None
    tle_line2: str | None


class CelesTrakClient:
    """Async client for CelesTrak GP data API."""

    def __init__(self, base_url: str | None = None):
        self.base_url = (base_url or settings.celestrak_base_url).rstrip("/")
        self.gp_url = f"{self.base_url}/NORAD/elements/gp.php"

    async def fetch_group(self, group: str) -> list[GPRecord]:
        """Fetch all GP records for a satellite group.

        Args:
            group: CelesTrak group name (e.g., "active", "stations").
        """
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.get(
                self.gp_url,
                params={"GROUP": group, "FORMAT": "json"},
            )
            response.raise_for_status()
            return [self._parse_record(item) for item in response.json()]

    async def fetch_by_norad_id(self, norad_id: int) -> GPRecord | None:
        """Fetch GP record for a single satellite by NORAD catalog number."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                self.gp_url,
                params={"CATNR": norad_id, "FORMAT": "json"},
            )
            response.raise_for_status()
            data = response.json()
            if not data:
                return None
            return self._parse_record(data[0])

    async def fetch_full_catalog(self) -> list[GPRecord]:
        """Fetch the full active satellite catalog (~10,000 objects).

        For the full ~47,000 object catalog including debris, use Space-Track.
        """
        return await self.fetch_group("active")

    def _parse_record(self, item: dict) -> GPRecord:
        return GPRecord(
            norad_id=int(item["NORAD_CAT_ID"]),
            name=item.get("OBJECT_NAME", ""),
            object_type=item.get("OBJECT_TYPE"),
            epoch=datetime.fromisoformat(item["EPOCH"]),
            mean_motion=float(item["MEAN_MOTION"]),
            eccentricity=float(item["ECCENTRICITY"]),
            inclination=float(item["INCLINATION"]),
            raan=float(item["RA_OF_ASC_NODE"]),
            arg_perigee=float(item["ARG_OF_PERICENTER"]),
            mean_anomaly=float(item["MEAN_ANOMALY"]),
            bstar=float(item["BSTAR"]),
            tle_line1=item.get("TLE_LINE1"),
            tle_line2=item.get("TLE_LINE2"),
        )

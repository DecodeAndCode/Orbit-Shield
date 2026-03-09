"""SOCRATES conjunction report parser.

Fetches and parses the SOCRATES (Satellite Orbital Conjunction Reports
Assessing Threatening Encounters in Space) CSV data from CelesTrak.
Updated 3x daily. No authentication required.

Source: https://celestrak.org/SOCRATES/
"""

import csv
import io
import logging
from dataclasses import dataclass
from datetime import datetime

import httpx

from src.config import settings

logger = logging.getLogger(__name__)

SORT_OPTIONS = {
    "min_range": "sort-minRange.csv",
    "max_prob": "sort-maxProb.csv",
    "min_range_rate": "sort-minRangeRate.csv",
}


@dataclass
class SOCRATESRecord:
    """Parsed SOCRATES conjunction record."""

    primary_norad_id: int
    primary_name: str
    primary_days_since_epoch: float
    secondary_norad_id: int
    secondary_name: str
    secondary_days_since_epoch: float
    tca: datetime
    miss_distance_km: float
    relative_velocity_kms: float
    max_probability: float
    dilution_km: float


class SOCRATESClient:
    """Async client for CelesTrak SOCRATES conjunction data."""

    def __init__(self, base_url: str | None = None):
        self.base_url = (base_url or settings.celestrak_base_url).rstrip("/")

    async def fetch_conjunctions(
        self, sort_by: str = "min_range"
    ) -> list[SOCRATESRecord]:
        """Fetch the latest SOCRATES conjunction report.

        Args:
            sort_by: Sort order -- "min_range", "max_prob", or "min_range_rate".
        """
        filename = SORT_OPTIONS.get(sort_by, SORT_OPTIONS["min_range"])
        url = f"{self.base_url}/SOCRATES/{filename}"

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.get(url)
            response.raise_for_status()

        return self._parse_csv(response.text)

    def _parse_csv(self, csv_text: str) -> list[SOCRATESRecord]:
        records: list[SOCRATESRecord] = []
        reader = csv.DictReader(io.StringIO(csv_text))

        for row in reader:
            try:
                record = SOCRATESRecord(
                    primary_norad_id=int(row["NORAD_CAT_ID_1"]),
                    primary_name=row["OBJECT_NAME_1"].strip(),
                    primary_days_since_epoch=float(row["DSE_1"]),
                    secondary_norad_id=int(row["NORAD_CAT_ID_2"]),
                    secondary_name=row["OBJECT_NAME_2"].strip(),
                    secondary_days_since_epoch=float(row["DSE_2"]),
                    tca=datetime.fromisoformat(row["TCA"].strip()),
                    miss_distance_km=float(row["TCA_RANGE"]),
                    relative_velocity_kms=float(row["TCA_RELATIVE_SPEED"]),
                    max_probability=float(row["MAX_PROB"]),
                    dilution_km=float(row["DILUTION"]),
                )
                records.append(record)
            except (ValueError, KeyError) as e:
                logger.warning(f"Skipping malformed SOCRATES row: {e}")
                continue

        logger.info(f"Parsed {len(records)} SOCRATES conjunction records")
        return records

"""Parser for Space-Track CDM records.

Space-Track's /class/cdm_public and /class/cdm JSON endpoints return
per-encounter CDMs with RTN-frame 6x6 covariance entries stored as 21
lower-triangular fields per object (SAT{N}_C{R,T,N,RDOT,TDOT,NDOT}_{row}).

This module normalizes one JSON record into the shape our ORM expects.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)

# Lower-triangular RTN covariance field names per satellite.
# Order follows Space-Track CDM schema (21 unique terms, 6x6 symmetric).
_COV_FIELDS = [
    "CR_R",
    "CT_R", "CT_T",
    "CN_R", "CN_T", "CN_N",
    "CRDOT_R", "CRDOT_T", "CRDOT_N", "CRDOT_RDOT",
    "CTDOT_R", "CTDOT_T", "CTDOT_N", "CTDOT_RDOT", "CTDOT_TDOT",
    "CNDOT_R", "CNDOT_T", "CNDOT_N", "CNDOT_RDOT", "CNDOT_TDOT", "CNDOT_NDOT",
]


@dataclass
class ParsedCDM:
    cdm_id: str
    creation_date: datetime | None
    tca: datetime
    miss_distance_km: float | None
    pc: float | None
    primary_norad_id: int
    primary_name: str | None
    primary_object_type: str | None
    primary_rcs: str | None
    primary_covariance: dict[str, float]
    secondary_norad_id: int
    secondary_name: str | None
    secondary_object_type: str | None
    secondary_rcs: str | None
    secondary_covariance: dict[str, float]
    relative_velocity_kms: float | None
    raw: dict[str, Any]


def _parse_dt(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def _parse_float(value: Any) -> float | None:
    if value in (None, "", "null"):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _extract_cov(record: dict, prefix: str) -> dict[str, float]:
    """Pull the 21 RTN covariance entries for SAT1_ / SAT2_ prefix."""
    out: dict[str, float] = {}
    for name in _COV_FIELDS:
        key = f"{prefix}{name}"
        v = _parse_float(record.get(key))
        if v is not None:
            out[name] = v
    return out


def parse_cdm(record: dict[str, Any]) -> ParsedCDM | None:
    """Normalize one Space-Track CDM JSON record.

    Returns None when required fields are missing (malformed record).
    """
    try:
        cdm_id = str(record.get("CDM_ID") or record.get("MESSAGE_ID") or "").strip()
        primary_id = record.get("SAT_1_ID") or record.get("SAT1_OBJECT_DESIGNATOR")
        secondary_id = record.get("SAT_2_ID") or record.get("SAT2_OBJECT_DESIGNATOR")
        tca = _parse_dt(record.get("TCA"))
        if not cdm_id or primary_id is None or secondary_id is None or tca is None:
            return None

        rel_speed_ms = _parse_float(record.get("RELATIVE_SPEED"))
        rel_speed_kms = rel_speed_ms / 1000.0 if rel_speed_ms is not None else None

        return ParsedCDM(
            cdm_id=cdm_id,
            creation_date=_parse_dt(record.get("CREATED") or record.get("CREATION_DATE")),
            tca=tca,
            miss_distance_km=_parse_float(record.get("MIN_RNG")),
            pc=_parse_float(record.get("PC")),
            primary_norad_id=int(primary_id),
            primary_name=record.get("SAT_1_NAME") or record.get("SAT1_OBJECT_NAME"),
            primary_object_type=record.get("SAT1_OBJECT_TYPE"),
            primary_rcs=record.get("SAT1_RCS"),
            primary_covariance=_extract_cov(record, "SAT1_"),
            secondary_norad_id=int(secondary_id),
            secondary_name=record.get("SAT_2_NAME") or record.get("SAT2_OBJECT_NAME"),
            secondary_object_type=record.get("SAT2_OBJECT_TYPE"),
            secondary_rcs=record.get("SAT2_RCS"),
            secondary_covariance=_extract_cov(record, "SAT2_"),
            relative_velocity_kms=rel_speed_kms,
            raw=record,
        )
    except (TypeError, ValueError, KeyError) as exc:
        logger.warning(f"Failed to parse CDM record: {exc}")
        return None

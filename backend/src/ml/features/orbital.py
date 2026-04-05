"""Orbital feature extraction for ML models.

Extracts 14 features from satellite orbital elements and metadata:
mean_motion, eccentricity, inclination, bstar, perigee_alt_km,
apogee_alt_km, semi_major_axis_km, orbital_period_minutes,
object_type_encoded, rcs_size_encoded, tle_age_hours,
tle_count_30d, is_leo, ballistic_coefficient_proxy.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.db.models import OrbitalElement, Satellite
from src.propagation.sgp4_engine import R_EARTH_KM, MU_EARTH, _compute_altitudes

ORBITAL_FEATURE_NAMES = [
    "mean_motion",
    "eccentricity",
    "inclination",
    "bstar",
    "perigee_alt_km",
    "apogee_alt_km",
    "semi_major_axis_km",
    "orbital_period_minutes",
    "object_type_encoded",
    "rcs_size_encoded",
    "tle_age_hours",
    "tle_count_30d",
    "is_leo",
    "ballistic_coefficient_proxy",
]

# Encoding maps
OBJECT_TYPE_MAP = {
    "PAYLOAD": 0,
    "ROCKET BODY": 1,
    "DEBRIS": 2,
    "UNKNOWN": 3,
    None: 3,
}

RCS_SIZE_MAP = {
    "SMALL": 0,
    "MEDIUM": 1,
    "LARGE": 2,
    None: 1,
}


def compute_derived_orbital_features(
    mean_motion: float,
    eccentricity: float,
    inclination: float,
    bstar: float,
) -> dict[str, float]:
    """Compute derived features from core orbital elements.

    Args:
        mean_motion: Revolutions per day.
        eccentricity: Orbital eccentricity.
        inclination: Inclination in degrees.
        bstar: B* drag term.

    Returns:
        Dict with perigee_alt_km, apogee_alt_km, semi_major_axis_km,
        orbital_period_minutes, is_leo, ballistic_coefficient_proxy.
    """
    perigee_alt, apogee_alt = _compute_altitudes(mean_motion, eccentricity)

    # Semi-major axis from mean motion
    n_rad_per_sec = mean_motion * 2.0 * math.pi / 86400.0
    if n_rad_per_sec > 0:
        semi_major_axis = (MU_EARTH / (n_rad_per_sec ** 2)) ** (1.0 / 3.0)
    else:
        semi_major_axis = R_EARTH_KM

    orbital_period = 1440.0 / mean_motion if mean_motion > 0 else 0.0
    is_leo = 1.0 if perigee_alt < 2000 else 0.0

    # Ballistic coefficient proxy: |B*| × semi_major_axis²
    ballistic_coeff = abs(bstar) * semi_major_axis ** 2

    return {
        "perigee_alt_km": perigee_alt,
        "apogee_alt_km": apogee_alt,
        "semi_major_axis_km": semi_major_axis,
        "orbital_period_minutes": orbital_period,
        "is_leo": is_leo,
        "ballistic_coefficient_proxy": ballistic_coeff,
    }


def extract_satellite_features(
    norad_id: int,
    session: Session,
    reference_time: datetime | None = None,
) -> dict[str, float] | None:
    """Extract 14 orbital features for a single satellite.

    Args:
        norad_id: NORAD catalog ID.
        session: Synchronous SQLAlchemy session.
        reference_time: Reference time for TLE age computation.

    Returns:
        Feature dict with 14 values, or None if satellite not found.
    """
    if reference_time is None:
        reference_time = datetime.now(timezone.utc)

    # Get latest orbital element
    stmt = (
        select(OrbitalElement)
        .where(OrbitalElement.norad_id == norad_id)
        .order_by(OrbitalElement.epoch.desc())
        .limit(1)
    )
    oe = session.execute(stmt).scalars().first()
    if oe is None:
        return None

    # Get satellite metadata
    sat = session.get(Satellite, norad_id)

    mean_motion = oe.mean_motion or 15.0
    eccentricity = oe.eccentricity or 0.001
    inclination = oe.inclination or 0.0
    bstar = oe.bstar or 0.0

    derived = compute_derived_orbital_features(
        mean_motion, eccentricity, inclination, bstar
    )

    # TLE age
    tle_age_hours = (reference_time - oe.epoch).total_seconds() / 3600.0

    # TLE count in last 30 days
    cutoff = reference_time - timedelta(days=30)
    count_stmt = (
        select(func.count())
        .select_from(OrbitalElement)
        .where(
            OrbitalElement.norad_id == norad_id,
            OrbitalElement.epoch >= cutoff,
        )
    )
    tle_count_30d = session.execute(count_stmt).scalar() or 0

    # Encode categoricals
    obj_type = sat.object_type if sat else None
    rcs_size = sat.rcs_size if sat else None

    return {
        "mean_motion": mean_motion,
        "eccentricity": eccentricity,
        "inclination": inclination,
        "bstar": bstar,
        **derived,
        "object_type_encoded": float(OBJECT_TYPE_MAP.get(obj_type, 3)),
        "rcs_size_encoded": float(RCS_SIZE_MAP.get(rcs_size, 1)),
        "tle_age_hours": tle_age_hours,
        "tle_count_30d": float(tle_count_30d),
    }


def extract_satellite_features_batch(
    norad_ids: list[int],
    session: Session,
    reference_time: datetime | None = None,
) -> pd.DataFrame:
    """Extract orbital features for multiple satellites.

    Args:
        norad_ids: List of NORAD catalog IDs.
        session: Synchronous SQLAlchemy session.
        reference_time: Reference time for TLE age computation.

    Returns:
        DataFrame with shape (n_satellites, 14), indexed by norad_id.
        Satellites with missing data are dropped.
    """
    rows = []
    for nid in norad_ids:
        feat = extract_satellite_features(nid, session, reference_time)
        if feat is not None:
            feat["norad_id"] = nid
            rows.append(feat)

    if not rows:
        return pd.DataFrame(columns=["norad_id"] + ORBITAL_FEATURE_NAMES)

    df = pd.DataFrame(rows)
    df = df.set_index("norad_id")
    return df

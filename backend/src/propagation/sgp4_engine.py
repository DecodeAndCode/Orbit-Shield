"""SGP4 batch propagation engine.

Loads TLEs from the database, builds Satrec objects, and propagates
the entire satellite catalog over a configurable time window using
the sgp4 library's C-accelerated array API.

All positions/velocities are in the TEME (True Equator Mean Equinox) frame.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

import numpy as np
from sgp4.api import Satrec, SatrecArray, jday
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from src.db.models import OrbitalElement

logger = logging.getLogger(__name__)

# Constants
R_EARTH_KM = 6378.137
MU_EARTH = 398600.4418  # km^3/s^2


@dataclass
class CatalogEntry:
    """A satellite with its parsed TLE and orbital metadata."""

    norad_id: int
    satrec: Satrec
    perigee_alt_km: float
    apogee_alt_km: float
    inclination_deg: float


@dataclass
class PropagationResult:
    """Result of propagating the catalog over a time window."""

    positions: np.ndarray  # (n_sats, n_steps, 3) TEME km
    velocities: np.ndarray  # (n_sats, n_steps, 3) TEME km/s
    times: list[datetime] = field(default_factory=list)
    valid_mask: np.ndarray = field(default_factory=lambda: np.array([], dtype=bool))
    norad_ids: list[int] = field(default_factory=list)


def datetime_to_jd(dt: datetime) -> tuple[float, float]:
    """Convert a datetime to Julian Date (jd, fr) pair for sgp4.

    Args:
        dt: UTC datetime.

    Returns:
        Tuple of (julian_date, fractional_day) suitable for sgp4 calls.
    """
    return jday(dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second + dt.microsecond / 1e6)


def _compute_altitudes(mean_motion_revs_per_day: float, eccentricity: float) -> tuple[float, float]:
    """Compute perigee and apogee altitudes from mean motion and eccentricity.

    Args:
        mean_motion_revs_per_day: Mean motion in revolutions per day.
        eccentricity: Orbital eccentricity.

    Returns:
        (perigee_alt_km, apogee_alt_km)
    """
    n_rad_per_sec = mean_motion_revs_per_day * 2.0 * math.pi / 86400.0
    if n_rad_per_sec <= 0:
        return 0.0, 0.0
    a_km = (MU_EARTH / (n_rad_per_sec ** 2)) ** (1.0 / 3.0)
    perigee = a_km * (1.0 - eccentricity) - R_EARTH_KM
    apogee = a_km * (1.0 + eccentricity) - R_EARTH_KM
    return perigee, apogee


def load_catalog(session: Session) -> list[CatalogEntry]:
    """Load the latest TLE per satellite from the orbital_elements table.

    Queries for the most recent epoch per norad_id, builds Satrec objects,
    and computes orbital metadata for pre-filtering.

    Args:
        session: Synchronous SQLAlchemy session.

    Returns:
        List of CatalogEntry with valid TLEs. Objects with missing or
        unparseable TLEs are skipped.
    """
    # Subquery: latest epoch per norad_id
    latest_epoch = (
        select(
            OrbitalElement.norad_id,
            func.max(OrbitalElement.epoch).label("max_epoch"),
        )
        .group_by(OrbitalElement.norad_id)
        .subquery()
    )

    # Join to get full rows for latest TLEs
    stmt = (
        select(OrbitalElement)
        .join(
            latest_epoch,
            (OrbitalElement.norad_id == latest_epoch.c.norad_id)
            & (OrbitalElement.epoch == latest_epoch.c.max_epoch),
        )
    )

    rows = session.execute(stmt).scalars().all()
    catalog: list[CatalogEntry] = []

    for row in rows:
        if not row.tle_line1 or not row.tle_line2:
            continue
        try:
            sat = Satrec.twoline2rv(row.tle_line1, row.tle_line2)
        except Exception:
            logger.warning("Failed to parse TLE for NORAD %d, skipping", row.norad_id)
            continue

        # Use mean motion from the Satrec object (revs/day stored internally as rad/min)
        # sat.no_kozai is in rad/min; convert to rev/day
        n_revs_day = sat.no_kozai * 1440.0 / (2.0 * math.pi)
        perigee, apogee = _compute_altitudes(n_revs_day, sat.ecco)

        catalog.append(
            CatalogEntry(
                norad_id=row.norad_id,
                satrec=sat,
                perigee_alt_km=perigee,
                apogee_alt_km=apogee,
                inclination_deg=math.degrees(sat.inclo),
            )
        )

    logger.info("Loaded %d satellites with valid TLEs", len(catalog))
    return catalog


def build_time_grid(
    start: datetime,
    end: datetime,
    step_seconds: int = 60,
) -> tuple[np.ndarray, np.ndarray, list[datetime]]:
    """Build arrays of Julian Date pairs for the propagation window.

    Args:
        start: Window start (UTC).
        end: Window end (UTC).
        step_seconds: Time step in seconds.

    Returns:
        (jd_array, fr_array, datetimes) where jd/fr are numpy arrays
        suitable for sgp4 array API.
    """
    times: list[datetime] = []
    t = start
    while t <= end:
        times.append(t)
        t += timedelta(seconds=step_seconds)

    jd_arr = np.empty(len(times), dtype=np.float64)
    fr_arr = np.empty(len(times), dtype=np.float64)

    for i, dt in enumerate(times):
        jd_arr[i], fr_arr[i] = datetime_to_jd(dt)

    return jd_arr, fr_arr, times


def propagate_catalog(
    catalog: list[CatalogEntry],
    start: datetime,
    end: datetime,
    step_seconds: int = 60,
) -> PropagationResult:
    """Propagate the entire catalog over a time window.

    Uses SatrecArray for C-accelerated batch propagation across all
    satellites and all time steps simultaneously.

    Args:
        catalog: List of CatalogEntry from load_catalog().
        start: Propagation window start (UTC).
        end: Propagation window end (UTC).
        step_seconds: Time step in seconds between propagation points.

    Returns:
        PropagationResult with positions/velocities in TEME frame.
        Satellites that produce SGP4 errors at any time step are masked
        out via valid_mask.
    """
    if not catalog:
        return PropagationResult(
            positions=np.empty((0, 0, 3)),
            velocities=np.empty((0, 0, 3)),
            times=[],
            valid_mask=np.array([], dtype=bool),
            norad_ids=[],
        )

    jd_arr, fr_arr, times = build_time_grid(start, end, step_seconds)
    n_sats = len(catalog)
    n_steps = len(times)

    # Build SatrecArray for vectorized propagation
    satrecs = [entry.satrec for entry in catalog]
    sat_array = SatrecArray(satrecs)

    # Propagate: returns (errors, positions, velocities)
    # errors: (n_sats, n_steps), positions: (n_sats, n_steps, 3), velocities: (n_sats, n_steps, 3)
    errors, positions, velocities = sat_array.sgp4(jd_arr, fr_arr)

    # A satellite is valid if all its time steps have error code 0
    valid_mask = np.all(errors == 0, axis=1)
    n_valid = int(np.sum(valid_mask))
    n_invalid = n_sats - n_valid
    if n_invalid > 0:
        logger.info(
            "SGP4 errors for %d/%d satellites (decayed or invalid TLE), masking out",
            n_invalid,
            n_sats,
        )

    norad_ids = [entry.norad_id for entry in catalog]

    return PropagationResult(
        positions=positions,
        velocities=velocities,
        times=times,
        valid_mask=valid_mask,
        norad_ids=norad_ids,
    )

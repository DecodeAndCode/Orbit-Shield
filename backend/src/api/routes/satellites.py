"""GET /api/satellites — paginated satellite catalog."""

import math

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.schemas import SatelliteResponse
from src.db.models import OrbitalElement, Satellite
from src.db.session import get_session
from src.propagation.sgp4_engine import MU_EARTH, R_EARTH_KM

router = APIRouter()


def _compute_altitudes(
    mean_motion: float | None, eccentricity: float | None
) -> tuple[float | None, float | None]:
    """Compute perigee and apogee altitude (km) from mean motion and eccentricity.

    Args:
        mean_motion: Mean motion in revolutions per day.
        eccentricity: Orbital eccentricity (dimensionless).

    Returns:
        Tuple of (perigee_alt_km, apogee_alt_km), or (None, None) if inputs invalid.
    """
    if mean_motion is None or eccentricity is None or mean_motion <= 0:
        return None, None
    period_sec = 86400.0 / mean_motion
    a_km = (MU_EARTH * (period_sec / (2 * math.pi)) ** 2) ** (1.0 / 3.0)
    perigee = a_km * (1 - eccentricity) - R_EARTH_KM
    apogee = a_km * (1 + eccentricity) - R_EARTH_KM
    return perigee, apogee


def _compute_regime(perigee_alt_km: float | None) -> str | None:
    """Classify orbital regime from perigee altitude.

    Args:
        perigee_alt_km: Perigee altitude in km above Earth's surface.

    Returns:
        One of "LEO", "MEO", "GEO", or None if altitude unavailable.
    """
    if perigee_alt_km is None:
        return None
    if perigee_alt_km < 2000:
        return "LEO"
    elif perigee_alt_km < 35786:
        return "MEO"
    else:
        return "GEO"


@router.get("/satellites")
async def list_satellites(
    search: str | None = Query(None, description="Filter by name or NORAD ID"),
    regime: str | None = Query(None, description="Filter by orbital regime: LEO, MEO, GEO"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
):
    """Return paginated satellite catalog with computed orbital parameters.

    Joins the latest orbital element per satellite to compute perigee/apogee
    altitudes and classify the orbital regime.

    Args:
        search: Optional name substring or exact NORAD ID filter.
        regime: Optional orbital regime filter (LEO/MEO/GEO).
        limit: Maximum number of results to return (1–1000).
        offset: Number of results to skip for pagination.
        session: Async database session (injected).

    Returns:
        Paginated response with items, total, limit, and offset.
    """
    # Subquery: latest orbital element per satellite via window function
    latest_oe = (
        select(
            OrbitalElement.norad_id,
            OrbitalElement.inclination,
            OrbitalElement.mean_motion,
            OrbitalElement.eccentricity,
            func.row_number()
            .over(
                partition_by=OrbitalElement.norad_id,
                order_by=OrbitalElement.epoch.desc(),
            )
            .label("rn"),
        ).subquery()
    )
    latest = select(latest_oe).where(latest_oe.c.rn == 1).subquery()

    # Base query joining satellites with their latest orbital elements
    query = select(
        Satellite,
        latest.c.inclination,
        latest.c.mean_motion,
        latest.c.eccentricity,
    ).outerjoin(latest, Satellite.norad_id == latest.c.norad_id)

    if search:
        name_filter = Satellite.name.ilike(f"%{search}%")
        if search.isdigit():
            query = query.where(name_filter | (Satellite.norad_id == int(search)))
        else:
            query = query.where(name_filter)

    # Count total matching rows before pagination
    count_q = select(func.count()).select_from(query.subquery())
    total: int = (await session.execute(count_q)).scalar_one()

    # Fetch paginated rows
    rows = (await session.execute(query.offset(offset).limit(limit))).all()

    items: list[SatelliteResponse] = []
    for sat, incl, mm, ecc in rows:
        perigee, apogee = _compute_altitudes(mm, ecc)
        regime_val = _compute_regime(perigee)

        items.append(
            SatelliteResponse(
                norad_id=sat.norad_id,
                name=sat.name,
                object_type=sat.object_type,
                country=sat.country,
                launch_date=sat.launch_date,
                rcs_size=sat.rcs_size,
                inclination=incl,
                perigee_alt_km=round(perigee, 2) if perigee is not None else None,
                apogee_alt_km=round(apogee, 2) if apogee is not None else None,
                regime=regime_val,
            )
        )

    # Regime is a computed field — filter in-memory after resolving altitudes
    if regime:
        items = [i for i in items if i.regime == regime.upper()]

    return {"items": items, "total": total, "limit": limit, "offset": offset}

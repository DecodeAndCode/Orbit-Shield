"""POST /api/propagate — run SGP4 propagation for selected satellites."""

import math
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.schemas import PropagateRequest, PropagateResponse, SatellitePosition
from src.db.session import get_session
from src.propagation.sgp4_engine import (
    R_EARTH_KM,
    load_catalog,
    propagate_catalog,
)

router = APIRouter()


def _teme_to_geodetic(x_km: float, y_km: float, z_km: float) -> tuple[float, float, float]:
    """Convert TEME position to lat/lon/alt (simplified, ignoring Earth rotation offset).

    Args:
        x_km: X component in TEME frame (km).
        y_km: Y component in TEME frame (km).
        z_km: Z component in TEME frame (km).

    Returns:
        (lat_deg, lon_deg, alt_km) geocentric latitude, longitude, and altitude.
    """
    r = math.sqrt(x_km**2 + y_km**2 + z_km**2)
    lat = math.degrees(math.asin(z_km / r)) if r > 0 else 0.0
    lon = math.degrees(math.atan2(y_km, x_km))
    alt = r - R_EARTH_KM
    return lat, lon, alt


@router.post("/propagate")
async def propagate(
    req: PropagateRequest,
    session: AsyncSession = Depends(get_session),
) -> list[PropagateResponse]:
    """Propagate selected satellites over the requested time window.

    Loads TLEs from the database, runs SGP4 batch propagation, and returns
    position/velocity time series in TEME frame with geodetic coordinates.

    Args:
        req: Propagation request with NORAD IDs, duration, and time step.
        session: Async database session (injected).

    Returns:
        List of PropagateResponse, one per requested satellite that has valid TLEs.
    """
    # load_catalog uses sync SQLAlchemy Session
    sync_session = session.sync_session
    catalog = load_catalog(sync_session)

    if not catalog:
        return []

    # Filter to only requested NORAD IDs
    norad_id_set = set(req.norad_ids)
    catalog = [entry for entry in catalog if entry.norad_id in norad_id_set]

    if not catalog:
        return []

    now = datetime.now(tz=timezone.utc)
    end = now + timedelta(hours=req.duration_hours)
    step_seconds = int(req.step_minutes * 60)

    result = propagate_catalog(
        catalog,
        start=now,
        end=end,
        step_seconds=step_seconds,
    )

    responses = []
    for i, norad_id in enumerate(result.norad_ids):
        if not result.valid_mask[i]:
            continue

        positions = []
        for t_idx, epoch in enumerate(result.times):
            pos = result.positions[i, t_idx]
            lat, lon, alt = _teme_to_geodetic(pos[0], pos[1], pos[2])
            positions.append(
                SatellitePosition(
                    epoch=epoch,
                    x_km=round(float(pos[0]), 3),
                    y_km=round(float(pos[1]), 3),
                    z_km=round(float(pos[2]), 3),
                    lat_deg=round(lat, 4),
                    lon_deg=round(lon, 4),
                    alt_km=round(alt, 2),
                )
            )

        responses.append(PropagateResponse(norad_id=norad_id, positions=positions))

    return responses

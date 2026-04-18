"""GET /api/positions — single-epoch geodetic snapshot for the full catalog.

Used by the frontend globe to render a point cloud of all satellites
(Wayfinder-style), as opposed to /propagate which returns time series
for a small selected subset.
"""

import math
from datetime import datetime, timezone

import numpy as np
from fastapi import APIRouter, Depends
from sgp4.api import SatrecArray
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.schemas import CatalogPosition, CatalogPositionsResponse
from src.db.session import get_session
from src.propagation.sgp4_engine import (
    R_EARTH_KM,
    datetime_to_jd,
    load_catalog,
)

router = APIRouter()


@router.get("/positions", response_model=CatalogPositionsResponse)
async def positions(
    session: AsyncSession = Depends(get_session),
) -> CatalogPositionsResponse:
    """Return current TEME→geodetic position for every satellite with a valid TLE/OMM.

    One epoch only (now). Vectorized SGP4 over the full catalog. Designed for
    a globe point cloud render — not for trajectory analysis.
    """
    catalog = await session.run_sync(lambda s: load_catalog(s))
    if not catalog:
        return CatalogPositionsResponse(epoch=datetime.now(tz=timezone.utc), count=0, positions=[])

    now = datetime.now(tz=timezone.utc)
    jd, fr = datetime_to_jd(now)
    jd_arr = np.array([jd], dtype=np.float64)
    fr_arr = np.array([fr], dtype=np.float64)

    sat_array = SatrecArray([e.satrec for e in catalog])
    errors, pos, _ = sat_array.sgp4(jd_arr, fr_arr)

    out: list[CatalogPosition] = []
    # Earth rotation angle (GMST approx) for TEME→ECEF longitude correction
    # Simple approximation: GMST in radians at this UTC.
    # Vallado eq 3-45 simplified.
    jd_ut1 = jd + fr
    t_ut1 = (jd_ut1 - 2451545.0) / 36525.0
    gmst_sec = (
        67310.54841
        + (876600.0 * 3600.0 + 8640184.812866) * t_ut1
        + 0.093104 * t_ut1**2
        - 6.2e-6 * t_ut1**3
    )
    gmst_rad = math.radians((gmst_sec % 86400.0) / 240.0)  # sec→deg→rad

    for i, entry in enumerate(catalog):
        if errors[i, 0] != 0:
            continue
        x, y, z = float(pos[i, 0, 0]), float(pos[i, 0, 1]), float(pos[i, 0, 2])
        r = math.sqrt(x * x + y * y + z * z)
        if r <= 0:
            continue
        lat = math.degrees(math.asin(z / r))
        lon_teme = math.atan2(y, x)
        lon = math.degrees(lon_teme - gmst_rad)
        # wrap to [-180, 180]
        lon = ((lon + 180.0) % 360.0) - 180.0
        alt = r - R_EARTH_KM
        if alt < 80 or alt > 50000:  # filter decayed/garbage
            continue
        out.append(
            CatalogPosition(
                norad_id=entry.norad_id,
                lat_deg=round(lat, 3),
                lon_deg=round(lon, 3),
                alt_km=round(alt, 1),
            )
        )

    return CatalogPositionsResponse(epoch=now, count=len(out), positions=out)

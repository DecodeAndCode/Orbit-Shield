"""Offline snapshot served when the database is unreachable.

A serverless database can be suspended for reasons that have nothing to do
with this application — a spent monthly allowance, maintenance, a cold start
that times out. Returning an error page for the whole site in those windows
is a poor trade when the data needed to render it barely changes.

Two kinds of data are bundled, and they degrade differently:

  * Orbital elements are propagated with SGP4 at request time, so globe
    positions are genuinely current. Element sets stay usable for days past
    their epoch, which is what makes this honest rather than a mock.
  * Conjunctions are frozen at the last successful screening. They are real
    computed results, but they do not advance, so every response sourced from
    the snapshot is flagged and callers are expected to label it.

Regenerate with `python scripts/build_snapshot.py`.
"""

from __future__ import annotations

import gzip
import json
import logging
import math
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from types import SimpleNamespace
from typing import Any

logger = logging.getLogger(__name__)

SNAPSHOT_PATH = Path(__file__).resolve().parent.parent / "data" / "snapshot.json.gz"

# Header set on any response served from the snapshot so clients can tell the
# difference without inspecting the body.
SOURCE_HEADER = "X-Data-Source"
SOURCE_SNAPSHOT = "snapshot"
SOURCE_LIVE = "live"


@lru_cache(maxsize=1)
def _payload() -> dict[str, Any] | None:
    """Read and cache the snapshot file, or None when it is absent."""
    if not SNAPSHOT_PATH.exists():
        logger.warning("No snapshot bundled at %s", SNAPSHOT_PATH)
        return None
    try:
        with gzip.open(SNAPSHOT_PATH, "rt", encoding="utf-8") as fh:
            data = json.load(fh)
        logger.info(
            "Loaded snapshot generated %s (%d satellites, %d conjunctions)",
            data.get("generated_at"),
            len(data.get("orbital_elements", [])),
            len(data.get("conjunctions", [])),
        )
        return data
    except Exception:
        logger.exception("Snapshot could not be read")
        return None


def available() -> bool:
    return _payload() is not None


def generated_at() -> str | None:
    data = _payload()
    return data.get("generated_at") if data else None


def satellites() -> list[dict[str, Any]]:
    data = _payload()
    return list(data.get("satellites", [])) if data else []


def conjunctions() -> list[dict[str, Any]]:
    """Frozen conjunctions, already ordered by descending classical Pc."""
    data = _payload()
    return list(data.get("conjunctions", [])) if data else []


@lru_cache(maxsize=1)
def _names() -> dict[int, str | None]:
    return {s["norad_id"]: s.get("name") for s in satellites()}


def satellite_name(norad_id: int) -> str | None:
    return _names().get(norad_id)


@lru_cache(maxsize=1)
def catalog() -> list[Any]:
    """Build CatalogEntry objects from the snapshot.

    Mirrors `load_catalog`, including its fallback from TLE text to OMM
    element sets, so callers can propagate the result identically.
    """
    from src.propagation.sgp4_engine import (
        CatalogEntry,
        _compute_altitudes,
        _satrec_from_elements,
    )
    from sgp4.api import Satrec

    data = _payload()
    if not data:
        return []

    entries: list[Any] = []
    for row in data.get("orbital_elements", []):
        try:
            if row.get("tle_line1") and row.get("tle_line2"):
                sat = Satrec.twoline2rv(row["tle_line1"], row["tle_line2"])
            elif row.get("mean_motion") is not None and row.get("eccentricity") is not None:
                # _satrec_from_elements reads attributes, so present the dict
                # as an object with the same field names as the ORM row.
                sat = _satrec_from_elements(
                    SimpleNamespace(
                        norad_id=row["norad_id"],
                        epoch=datetime.fromisoformat(row["epoch"]),
                        bstar=row.get("bstar"),
                        eccentricity=row["eccentricity"],
                        arg_perigee=row.get("arg_perigee"),
                        inclination=row.get("inclination"),
                        mean_anomaly=row.get("mean_anomaly"),
                        mean_motion=row["mean_motion"],
                        raan=row.get("raan"),
                    )
                )
            else:
                continue
        except Exception:
            continue

        n_revs_day = sat.no_kozai * 1440.0 / (2.0 * math.pi)
        perigee, apogee = _compute_altitudes(n_revs_day, sat.ecco)
        entries.append(
            CatalogEntry(
                norad_id=row["norad_id"],
                satrec=sat,
                perigee_alt_km=perigee,
                apogee_alt_km=apogee,
                inclination_deg=math.degrees(sat.inclo),
            )
        )

    logger.info("Snapshot catalog built: %d entries", len(entries))
    return entries


# Messages a managed provider returns when the database is administratively
# unavailable rather than broken: a spent monthly allowance, a suspended or
# paused project. These arrive as ordinary Postgres errors during connection
# setup — asyncpg raises them before SQLAlchemy wraps anything — so type alone
# cannot distinguish them from a genuine query fault. Matching on the message
# is what makes the difference detectable.
PROVIDER_UNAVAILABLE_SIGNATURES = (
    "exceeded the data transfer quota",
    "exceeded the logical size limit",
    "exceeded the compute time quota",
    "reaching its monthly free plan limit",
    "project is paused",
    "project has been suspended",
    "quota exceeded",
)


def is_connectivity_error(exc: BaseException) -> bool:
    """True when an exception means the database is unusable, not misused.

    Covers two distinct cases:

      * Transport failures — refused connections, dropped sockets, timeouts.
      * Provider capacity blocks, which arrive as ordinary Postgres errors
        and so are identified by message rather than by type.

    Deliberately narrow otherwise. Programming errors, missing tables and
    constraint violations must keep surfacing as real failures rather than
    silently falling back to stale data.
    """
    from sqlalchemy.exc import (
        DisconnectionError,
        InterfaceError,
        OperationalError,
        TimeoutError as SATimeoutError,
    )

    if isinstance(
        exc, (OperationalError, InterfaceError, DisconnectionError, SATimeoutError)
    ):
        return True
    if isinstance(exc, (ConnectionError, TimeoutError, OSError)):
        return True

    # Walk the cause chain: the driver error is often wrapped by the time it
    # reaches a route handler.
    seen: set[int] = set()
    current: BaseException | None = exc
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        lowered = str(current).lower()
        if any(sig in lowered for sig in PROVIDER_UNAVAILABLE_SIGNATURES):
            return True
        current = current.__cause__ or current.__context__

    return False

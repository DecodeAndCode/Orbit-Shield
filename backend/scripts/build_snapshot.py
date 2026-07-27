"""Build the offline snapshot bundled with the API.

The API serves this when the database is unreachable, so the site degrades to
real-but-frozen data instead of an error page. Two different things are stored,
and they degrade differently:

  * TLEs — propagated with SGP4 at request time, so the globe still shows
    genuinely current positions. TLEs stay usable for days to weeks past their
    epoch, which is why this is honest rather than a fake.
  * Conjunctions — a frozen list from the last successful screening. These are
    real computed results, but they do not advance, so anything served from the
    snapshot is flagged so the UI can label it.

Regenerate against any populated database:

    python scripts/build_snapshot.py
    python scripts/build_snapshot.py --max-conjunctions 1000
"""

from __future__ import annotations

import argparse
import gzip
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)-7s %(message)s")
logger = logging.getLogger("snapshot")

OUTPUT_PATH = Path(__file__).resolve().parent.parent / "src" / "data" / "snapshot.json.gz"


def build(max_conjunctions: int) -> dict:
    from sqlalchemy import create_engine, func, select
    from sqlalchemy.orm import Session

    from src.config import settings
    from src.db.models import Conjunction, OrbitalElement, Satellite

    engine = create_engine(settings.database_url_sync, pool_pre_ping=True)
    now = datetime.now(timezone.utc)

    with Session(engine) as session:
        # Latest TLE per satellite, mirroring load_catalog's selection.
        latest = (
            select(
                OrbitalElement.norad_id.label("norad_id"),
                func.max(OrbitalElement.epoch).label("max_epoch"),
            )
            .group_by(OrbitalElement.norad_id)
            .subquery()
        )
        stmt = select(OrbitalElement).join(
            latest,
            (OrbitalElement.norad_id == latest.c.norad_id)
            & (OrbitalElement.epoch == latest.c.max_epoch),
        )

        elements: list[dict] = []
        seen: set[int] = set()
        for oe in session.execute(stmt).scalars():
            if oe.norad_id in seen:
                continue
            # Two shapes reach the catalog: legacy TLE text, and OMM element
            # sets (what CelesTrak serves as JSON). load_catalog builds a
            # Satrec from whichever is present, so the snapshot keeps both and
            # skips only rows that can produce neither.
            has_tle = bool(oe.tle_line1 and oe.tle_line2)
            has_elements = oe.mean_motion is not None and oe.eccentricity is not None
            if not (has_tle or has_elements):
                continue
            seen.add(oe.norad_id)
            elements.append(
                {
                    "norad_id": oe.norad_id,
                    "epoch": oe.epoch.isoformat(),
                    "tle_line1": oe.tle_line1,
                    "tle_line2": oe.tle_line2,
                    "mean_motion": oe.mean_motion,
                    "eccentricity": oe.eccentricity,
                    "inclination": oe.inclination,
                    "raan": oe.raan,
                    "arg_perigee": oe.arg_perigee,
                    "mean_anomaly": oe.mean_anomaly,
                    "bstar": oe.bstar,
                }
            )
        logger.info("Orbital elements: %d satellites", len(elements))

        sat_rows = session.execute(
            select(
                Satellite.norad_id,
                Satellite.name,
                Satellite.object_type,
                Satellite.country,
                Satellite.rcs_size,
            ).where(Satellite.norad_id.in_(seen))
        ).all()
        satellites = [
            {
                "norad_id": r[0],
                "name": r[1],
                "object_type": r[2],
                "country": r[3],
                "rcs_size": r[4],
            }
            for r in sat_rows
        ]
        logger.info("Satellite metadata: %d rows", len(satellites))

        conj_rows = session.execute(
            select(Conjunction)
            .where(Conjunction.tca >= now)
            .order_by(Conjunction.pc_classical.desc().nulls_last())
            .limit(max_conjunctions)
        ).scalars()
        conjunctions = [
            {
                "id": c.id,
                "primary_norad_id": c.primary_norad_id,
                "secondary_norad_id": c.secondary_norad_id,
                "tca": c.tca.isoformat(),
                "miss_distance_km": c.miss_distance_km,
                "relative_velocity_kms": c.relative_velocity_kms,
                "pc_classical": c.pc_classical,
                "pc_ml": c.pc_ml,
                "screening_source": c.screening_source,
                "created_at": c.created_at.isoformat() if c.created_at else None,
            }
            for c in conj_rows
        ]
        logger.info("Conjunctions: %d rows", len(conjunctions))

    return {
        "generated_at": now.isoformat(),
        "satellites": satellites,
        "orbital_elements": elements,
        "conjunctions": conjunctions,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-conjunctions", type=int, default=500)
    args = parser.parse_args()

    payload = build(args.max_conjunctions)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(OUTPUT_PATH, "wt", encoding="utf-8", compresslevel=9) as fh:
        json.dump(payload, fh, separators=(",", ":"))

    size_mb = OUTPUT_PATH.stat().st_size / 1024 / 1024
    logger.info("Wrote %s (%.2f MB compressed)", OUTPUT_PATH, size_mb)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

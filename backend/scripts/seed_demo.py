"""Seed demo data: a few well-known sats + synthetic conjunctions.

Run: uv run python scripts/seed_demo.py
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.dialects.postgresql import insert as pg_insert

from src.config import settings
from src.db.models import Satellite, OrbitalElement, Conjunction, AlertConfig


# ISS + Hubble + Starlink-1007 + Cosmos-2251 debris (well-known objects)
SATS = [
    (25544, "ISS (ZARYA)",      "PAYLOAD", "ISS", "1998-11-20", "LARGE"),
    (20580, "HST",              "PAYLOAD", "US",  "1990-04-24", "LARGE"),
    (44713, "STARLINK-1007",    "PAYLOAD", "US",  "2019-11-11", "MEDIUM"),
    (33759, "COSMOS 2251 DEB",  "DEBRIS",  "CIS", "1993-06-16", "SMALL"),
    (48274, "STARLINK-2589",    "PAYLOAD", "US",  "2021-04-29", "MEDIUM"),
]

# Real ISS TLE (sample)
TLES = {
    25544: (
        "1 25544U 98067A   24001.50000000  .00010000  00000-0  20000-3 0  9999",
        "2 25544  51.6400 100.0000 0005000  90.0000 270.0000 15.50000000123456",
    ),
}


def main() -> None:
    engine = create_engine(settings.database_url_sync)
    Session = sessionmaker(bind=engine)
    s = Session()

    now = datetime.now(timezone.utc)

    for nid, name, otype, country, ldate, rcs in SATS:
        stmt = pg_insert(Satellite.__table__).values(
            norad_id=nid, name=name, object_type=otype, country=country,
            launch_date=datetime.fromisoformat(ldate).date(), rcs_size=rcs,
        ).on_conflict_do_update(
            index_elements=["norad_id"],
            set_={"name": name, "object_type": otype},
        )
        s.execute(stmt)

    for nid, (l1, l2) in TLES.items():
        s.add(OrbitalElement(
            norad_id=nid, epoch=now,
            tle_line1=l1, tle_line2=l2,
            mean_motion=15.5, eccentricity=0.0005, inclination=51.64,
            raan=100.0, arg_perigee=90.0, mean_anomaly=270.0, bstar=2e-4,
        ))

    # Synthetic conjunctions: one HIGH (ISS vs debris), one MEDIUM, one LOW
    conjs = [
        (25544, 33759, 0.450, 14.2, 3.2e-4, 5.1e-4, 2),   # HIGH
        (44713, 48274, 1.250, 11.8, 4.7e-6, 6.2e-6, 12),  # MEDIUM
        (20580, 25544, 5.800,  9.4, 1.1e-8, None,    24), # LOW
    ]
    for p, sec, miss, vel, pc, ml, hrs in conjs:
        stmt = pg_insert(Conjunction.__table__).values(
            primary_norad_id=p, secondary_norad_id=sec,
            tca=now + timedelta(hours=hrs),
            miss_distance_km=miss, relative_velocity_kms=vel,
            pc_classical=pc, pc_ml=ml, screening_source="DEMO",
        ).on_conflict_do_nothing(constraint="uq_conjunction_pair_tca")
        s.execute(stmt)

    # One alert config
    s.add(AlertConfig(
        watched_norad_ids=[25544],
        pc_threshold=1e-4, enabled=True,
        notification_channels={"email": "demo@collider.local"},
    ))

    s.commit()
    print(f"seeded: {len(SATS)} sats, {len(conjs)} conjunctions, 1 alert")
    s.close()


if __name__ == "__main__":
    main()

"""Equivalence tests for the bulk orbital feature extractor.

`extract_features_bulk` replaces ~3 queries per satellite with 3 queries
total for the whole set. These tests pin it to the same output as the
original per-satellite `extract_satellite_features`.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

from src.db.models import Base, OrbitalElement, Satellite
from src.ml.features.orbital import (
    ORBITAL_FEATURE_NAMES,
    extract_features_bulk,
    extract_satellite_features,
)

# Naive on purpose: SQLite drops tzinfo on round-trip, so a naive reference
# time keeps both extractors on the same footing here. Production runs on
# Postgres, where epochs come back timezone-aware.
REFERENCE_TIME = datetime(2024, 2, 20, 12, 0, 0)


@pytest.fixture
def session() -> Session:
    """In-memory SQLite session seeded with satellites and TLE history."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(
        engine, tables=[Satellite.__table__, OrbitalElement.__table__]
    )

    with Session(engine) as s:
        specs = [
            # (norad_id, name, object_type, rcs_size, n_tles, mean_motion, ecc, inc)
            (25544, "ISS (ZARYA)", "PAYLOAD", "LARGE", 5, 15.50, 0.0005, 51.64),
            (48274, "STARLINK-2000", "PAYLOAD", "MEDIUM", 3, 15.06, 0.0001, 53.05),
            (13403, "COSMOS 1408 DEB", "DEBRIS", "SMALL", 1, 14.80, 0.0032, 82.56),
            (5, "VANGUARD 1", "PAYLOAD", None, 2, 10.85, 0.1846, 34.25),
        ]
        row_id = 0
        for nid, name, otype, rcs, n_tles, mm, ecc, inc in specs:
            s.add(
                Satellite(
                    norad_id=nid, name=name, object_type=otype, rcs_size=rcs
                )
            )
            for k in range(n_tles):
                row_id += 1
                s.add(
                    OrbitalElement(
                        id=row_id,
                        norad_id=nid,
                        epoch=REFERENCE_TIME - timedelta(days=k * 2),
                        mean_motion=mm,
                        eccentricity=ecc,
                        inclination=inc,
                        raan=100.0,
                        arg_perigee=50.0,
                        mean_anomaly=25.0,
                        bstar=1.5e-4,
                    )
                )
        # A satellite with metadata but no orbital elements at all
        s.add(Satellite(norad_id=99001, name="NO TLE SAT", object_type="UNKNOWN"))
        s.commit()
        yield s


ALL_IDS = [25544, 48274, 13403, 5]


def test_bulk_matches_per_satellite(session):
    """Bulk output must equal the per-satellite extractor, key for key."""
    bulk = extract_features_bulk(ALL_IDS, session, REFERENCE_TIME)

    assert set(bulk) == set(ALL_IDS)

    for nid in ALL_IDS:
        single = extract_satellite_features(nid, session, REFERENCE_TIME)
        assert single is not None
        assert set(bulk[nid]) == set(single)
        for key in ORBITAL_FEATURE_NAMES:
            assert bulk[nid][key] == pytest.approx(single[key]), (
                f"mismatch on norad {nid}, feature {key}"
            )


def test_bulk_omits_satellites_without_orbital_elements(session):
    """A satellite with no TLE rows is omitted, matching the single-row None."""
    assert extract_satellite_features(99001, session, REFERENCE_TIME) is None
    bulk = extract_features_bulk(ALL_IDS + [99001], session, REFERENCE_TIME)
    assert 99001 not in bulk


def test_bulk_tle_counts_are_per_satellite(session):
    """TLE counts must not bleed across satellites when fetched set-wise."""
    bulk = extract_features_bulk(ALL_IDS, session, REFERENCE_TIME)
    assert bulk[25544]["tle_count_30d"] == 5.0
    assert bulk[48274]["tle_count_30d"] == 3.0
    assert bulk[13403]["tle_count_30d"] == 1.0
    assert bulk[5]["tle_count_30d"] == 2.0


def test_bulk_uses_constant_number_of_queries(session):
    """Query count must not scale with the number of satellites.

    This is the whole point of the function: a full-catalog screening asks
    for ~30k satellites, and per-satellite querying made that unusable.
    """
    counter = {"n": 0}

    @event.listens_for(session.bind, "before_cursor_execute")
    def _count(conn, cursor, statement, params, context, executemany):
        counter["n"] += 1

    extract_features_bulk(ALL_IDS, session, REFERENCE_TIME)
    few = counter["n"]

    counter["n"] = 0
    extract_features_bulk(ALL_IDS * 50, session, REFERENCE_TIME)
    many = counter["n"]

    assert few <= 3, f"expected at most 3 queries, got {few}"
    assert many == few, "query count grew with input size"


def test_bulk_empty_input_returns_empty(session):
    assert extract_features_bulk([], session, REFERENCE_TIME) == {}

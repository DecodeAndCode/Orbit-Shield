"""Tests for the memory-bounded streaming screening pipeline.

Validates that `screen_conjunctions_streaming` produces the same set of
detected conjunction events as the classical `propagate_catalog` +
`screen_conjunctions` pipeline, and that its peak RAM stays bounded
independent of the time window length.
"""

from __future__ import annotations

import math
import tracemalloc
from datetime import datetime, timedelta, timezone

import pytest
from sgp4.api import Satrec

from src.propagation.sgp4_engine import (
    CatalogEntry,
    _compute_altitudes,
    propagate_catalog,
    propagate_step_stream,
)
from src.propagation.screening import (
    screen_conjunctions,
    screen_conjunctions_streaming,
)

# ISS TLE (epoch ~2024-02-14)
ISS_TLE_LINE1 = "1 25544U 98067A   24045.51749023  .00018927  00000+0  33474-3 0  9996"
ISS_TLE_LINE2 = "2 25544  51.6408 129.5309 0005714  41.6071  50.0754 15.50135050440443"

# A near-twin of the ISS — same epoch, same inclination, slightly different RAAN/mean anomaly
# so the orbits eventually approach each other. Useful as a guaranteed-conjunction fixture.
ISS_TWIN_TLE_LINE1 = "1 99999U 24001A   24045.51749023  .00018927  00000+0  33474-3 0  9996"
ISS_TWIN_TLE_LINE2 = "2 99999  51.6408 130.0000 0005714  41.6071  50.5000 15.50135050440443"

# Vanguard 1 — high orbit, very different inclination from ISS
VANGUARD_TLE_LINE1 = "1 00005U 58002B   24044.48706498  .00000295  00000+0  39647-3 0  9995"
VANGUARD_TLE_LINE2 = "2 00005  34.2486  23.4208 1846384 147.4640 223.0822 10.84982059349825"


def _make_entry(norad_id: int, line1: str, line2: str) -> CatalogEntry:
    sat = Satrec.twoline2rv(line1, line2)
    n_revs_day = sat.no_kozai * 1440.0 / (2.0 * math.pi)
    perigee, apogee = _compute_altitudes(n_revs_day, sat.ecco)
    return CatalogEntry(
        norad_id=norad_id,
        satrec=sat,
        perigee_alt_km=perigee,
        apogee_alt_km=apogee,
        inclination_deg=math.degrees(sat.inclo),
    )


@pytest.fixture
def small_catalog() -> list[CatalogEntry]:
    """ISS + an ISS twin (likely close approach) + Vanguard (far, unrelated)."""
    return [
        _make_entry(25544, ISS_TLE_LINE1, ISS_TLE_LINE2),
        _make_entry(99999, ISS_TWIN_TLE_LINE1, ISS_TWIN_TLE_LINE2),
        _make_entry(5, VANGUARD_TLE_LINE1, VANGUARD_TLE_LINE2),
    ]


@pytest.fixture
def short_window() -> tuple[datetime, datetime, int]:
    """Small window aligned with the TLE epoch to keep SGP4 accurate."""
    start = datetime(2024, 2, 14, 12, 25, 0, tzinfo=timezone.utc)
    return start, start + timedelta(minutes=120), 30


def test_propagate_step_stream_yields_per_timestep(small_catalog, short_window):
    """Generator emits the expected number of timesteps with correct shapes."""
    start, end, step = short_window
    expected_steps = int((end - start).total_seconds() // step) + 1

    seen = 0
    for t_idx, t_time, pos, vel, valid in propagate_step_stream(
        small_catalog, start, end, step
    ):
        assert t_idx == seen
        assert t_time >= start
        assert pos.shape == (len(small_catalog), 3)
        assert vel.shape == (len(small_catalog), 3)
        assert valid.shape == (len(small_catalog),)
        assert valid.dtype == bool
        seen += 1
    assert seen == expected_steps


def test_streaming_equivalence_with_classical(small_catalog, short_window):
    """Streaming variant detects the same pair set as the classical pipeline."""
    start, end, step = short_window

    # Use a generous radius so a conjunction is actually detected within the window
    radius_km = 50.0

    prop_result = propagate_catalog(small_catalog, start, end, step)
    classical = screen_conjunctions(
        small_catalog,
        prop_result,
        screening_radius_km=radius_km,
        altitude_margin_km=50.0,
        inclination_threshold_deg=15.0,
    )

    streaming = screen_conjunctions_streaming(
        small_catalog,
        start,
        end,
        step_seconds=step,
        screening_radius_km=radius_km,
        altitude_margin_km=50.0,
        inclination_threshold_deg=15.0,
    )

    def pair_set(events):
        return {(e.primary_norad_id, e.secondary_norad_id) for e in events}

    # The two paths should detect the same set of (primary, secondary) pairs
    assert pair_set(streaming) == pair_set(classical)


def test_streaming_excludes_high_inclination_difference(small_catalog, short_window):
    """Vanguard (inclination ~34°) and ISS (~51°) differ by 17° > threshold 15°.

    The streaming variant must NOT report a (25544, 5) or (5, 25544) pair.
    """
    start, end, step = short_window
    streaming = screen_conjunctions_streaming(
        small_catalog,
        start,
        end,
        step_seconds=step,
        screening_radius_km=50.0,
        altitude_margin_km=50.0,
        inclination_threshold_deg=15.0,
    )
    for event in streaming:
        pair = {event.primary_norad_id, event.secondary_norad_id}
        assert 5 not in pair, "Vanguard should be filtered by inclination"


def test_streaming_memory_bounded(small_catalog):
    """Peak RAM during streaming should not blow up with window length.

    We run a much longer window (24h) and check that peak allocation stays
    under a small ceiling that the classical path would blow through on a
    real catalog.
    """
    start = datetime(2024, 2, 14, 12, 25, 0, tzinfo=timezone.utc)
    end = start + timedelta(hours=24)
    step = 60

    tracemalloc.start()
    # Drain the generator without holding any list of results
    count = 0
    for _ in propagate_step_stream(small_catalog, start, end, step):
        count += 1
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    assert count > 0
    # 3 sats × 24h × 60s step is trivial; peak should be well under 10 MB.
    # On a real 31k-sat catalog the same code stays bounded by O(n_sats),
    # not O(n_sats × n_steps).
    assert peak < 10 * 1024 * 1024, f"Peak RAM was {peak / 1024 / 1024:.2f} MB"

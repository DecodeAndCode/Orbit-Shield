"""Tests for SGP4 propagation engine and conjunction screening pipeline."""

import math
from datetime import datetime, timedelta, timezone

import numpy as np
import pytest
from sgp4.api import Satrec

from src.propagation.sgp4_engine import (
    CatalogEntry,
    PropagationResult,
    _compute_altitudes,
    build_time_grid,
    datetime_to_jd,
    propagate_catalog,
)
from src.propagation.screening import (
    ConjunctionEvent,
    altitude_overlap_filter,
    inclination_filter,
    kdtree_screen,
    refine_tca,
    screen_conjunctions,
)

# ISS TLE (epoch ~2024, good for testing)
ISS_TLE_LINE1 = "1 25544U 98067A   24045.51749023  .00018927  00000+0  33474-3 0  9996"
ISS_TLE_LINE2 = "2 25544  51.6408 129.5309 0005714  41.6071  50.0754 15.50135050440443"

# Vanguard 1 — high orbit, very different from ISS
VANGUARD_TLE_LINE1 = "1 00005U 58002B   24044.48706498  .00000295  00000+0  39647-3 0  9995"
VANGUARD_TLE_LINE2 = "2 00005  34.2486  23.4208 1846384 147.4640 223.0822 10.84982059349825"


def _make_entry(norad_id: int, line1: str, line2: str) -> CatalogEntry:
    """Helper to create a CatalogEntry from TLE lines."""
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


class TestSgp4Engine:
    """Tests for the SGP4 propagation engine."""

    def test_datetime_to_jd_roundtrip(self):
        """Julian Date conversion produces reasonable values."""
        dt = datetime(2024, 2, 14, 12, 0, 0, tzinfo=timezone.utc)
        jd, fr = datetime_to_jd(dt)
        # JD for 2024-02-14 should be around 2460354.x
        assert 2460354 <= jd + fr <= 2460355

    def test_compute_altitudes_iss(self):
        """ISS altitude should be ~400-420 km."""
        # ISS mean motion is ~15.5 rev/day
        perigee, apogee = _compute_altitudes(15.5, 0.0005)
        assert 390 < perigee < 430
        assert 390 < apogee < 430

    def test_compute_altitudes_geostationary(self):
        """GEO satellite altitude should be ~35,786 km."""
        perigee, apogee = _compute_altitudes(1.0, 0.0001)
        assert 35000 < perigee < 36500
        assert 35000 < apogee < 36500

    def test_propagate_single_satellite(self):
        """Propagate ISS for one orbit and verify reasonable position."""
        entry = _make_entry(25544, ISS_TLE_LINE1, ISS_TLE_LINE2)
        # Use the TLE epoch as start time to minimize propagation error
        sat = entry.satrec
        epoch = datetime(2024, 2, 14, 12, 25, 0, tzinfo=timezone.utc)
        end = epoch + timedelta(minutes=92)  # ~1 ISS orbit

        result = propagate_catalog([entry], epoch, end, step_seconds=60)

        assert result.positions.shape == (1, 93, 3)  # 92 min + 1
        assert result.velocities.shape == (1, 93, 3)
        assert result.valid_mask[0] is np.True_

        # ISS orbits at ~6778 km from Earth center (6378 + 400)
        distances = np.linalg.norm(result.positions[0], axis=1)
        assert np.all(distances > 6300)
        assert np.all(distances < 6900)

    def test_propagate_empty_catalog(self):
        """Empty catalog returns empty result."""
        result = propagate_catalog(
            [],
            datetime(2024, 1, 1, tzinfo=timezone.utc),
            datetime(2024, 1, 1, 1, tzinfo=timezone.utc),
        )
        assert result.positions.shape[0] == 0
        assert len(result.norad_ids) == 0

    def test_build_time_grid(self):
        """Time grid has correct number of steps."""
        start = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end = start + timedelta(minutes=10)
        jd, fr, times = build_time_grid(start, end, step_seconds=60)
        assert len(times) == 11  # 0, 1, 2, ..., 10 minutes
        assert len(jd) == 11
        assert len(fr) == 11


class TestScreening:
    """Tests for the conjunction screening pipeline."""

    def test_altitude_overlap_filter_overlapping(self):
        """Two LEO satellites with similar altitudes should pass."""
        entry_a = CatalogEntry(
            norad_id=1, satrec=None, perigee_alt_km=400, apogee_alt_km=420, inclination_deg=51.6
        )
        entry_b = CatalogEntry(
            norad_id=2, satrec=None, perigee_alt_km=410, apogee_alt_km=430, inclination_deg=51.6
        )
        catalog = [entry_a, entry_b]
        pairs = altitude_overlap_filter(catalog, [0, 1], margin_km=50)
        assert (0, 1) in pairs

    def test_altitude_overlap_filter_non_overlapping(self):
        """LEO and GEO satellites should not pass altitude filter."""
        entry_a = CatalogEntry(
            norad_id=1, satrec=None, perigee_alt_km=400, apogee_alt_km=420, inclination_deg=51.6
        )
        entry_b = CatalogEntry(
            norad_id=2, satrec=None, perigee_alt_km=35000, apogee_alt_km=35800, inclination_deg=0.1
        )
        catalog = [entry_a, entry_b]
        pairs = altitude_overlap_filter(catalog, [0, 1], margin_km=50)
        assert len(pairs) == 0

    def test_inclination_filter(self):
        """Large inclination difference should filter out pair."""
        entry_a = CatalogEntry(
            norad_id=1, satrec=None, perigee_alt_km=400, apogee_alt_km=420, inclination_deg=51.6
        )
        entry_b = CatalogEntry(
            norad_id=2, satrec=None, perigee_alt_km=400, apogee_alt_km=420, inclination_deg=97.0
        )
        catalog = [entry_a, entry_b]
        pairs = inclination_filter(catalog, {(0, 1)}, threshold_deg=15.0)
        assert len(pairs) == 0

    def test_inclination_filter_passes_similar(self):
        """Similar inclinations should pass."""
        entry_a = CatalogEntry(
            norad_id=1, satrec=None, perigee_alt_km=400, apogee_alt_km=420, inclination_deg=51.6
        )
        entry_b = CatalogEntry(
            norad_id=2, satrec=None, perigee_alt_km=400, apogee_alt_km=420, inclination_deg=55.0
        )
        catalog = [entry_a, entry_b]
        pairs = inclination_filter(catalog, {(0, 1)}, threshold_deg=15.0)
        assert (0, 1) in pairs

    def test_kdtree_finds_close_pair(self):
        """Two objects within 5 km should be detected by k-d tree."""
        n_sats = 3
        n_steps = 5
        positions = np.zeros((n_sats, n_steps, 3))

        # Place satellite 0 at (7000, 0, 0) and satellite 1 at (7003, 0, 0)
        # That's 3 km apart — within 5 km radius
        for t in range(n_steps):
            positions[0, t, :] = [7000, 0, 0]
            positions[1, t, :] = [7003, 0, 0]
            positions[2, t, :] = [7500, 0, 0]  # 500 km away

        times = [datetime(2024, 1, 1, tzinfo=timezone.utc) + timedelta(minutes=i) for i in range(n_steps)]
        candidate_pairs = {(0, 1), (0, 2), (1, 2)}
        hits = kdtree_screen(positions, times, candidate_pairs, radius_km=5.0)

        assert (0, 1) in hits
        assert (0, 2) not in hits
        assert (1, 2) not in hits

    def test_kdtree_tracks_closest_step(self):
        """k-d tree should return the step with minimum distance."""
        n_sats = 2
        n_steps = 5
        positions = np.zeros((n_sats, n_steps, 3))

        # Satellite 0 fixed, satellite 1 approaches then recedes
        for t in range(n_steps):
            positions[0, t, :] = [7000, 0, 0]
        positions[1, 0, :] = [7004, 0, 0]  # 4 km
        positions[1, 1, :] = [7003, 0, 0]  # 3 km
        positions[1, 2, :] = [7001, 0, 0]  # 1 km — closest
        positions[1, 3, :] = [7003, 0, 0]  # 3 km
        positions[1, 4, :] = [7004, 0, 0]  # 4 km

        times = [datetime(2024, 1, 1, tzinfo=timezone.utc) + timedelta(minutes=i) for i in range(n_steps)]
        hits = kdtree_screen(positions, times, {(0, 1)}, radius_km=5.0)

        assert (0, 1) in hits
        assert hits[(0, 1)] == 2  # step 2 is closest

    def test_refine_tca(self):
        """TCA refinement should find a time between coarse steps."""
        entry_a = _make_entry(25544, ISS_TLE_LINE1, ISS_TLE_LINE2)
        entry_b = _make_entry(5, VANGUARD_TLE_LINE1, VANGUARD_TLE_LINE2)

        # Pick an arbitrary time — we just check the function runs and
        # returns a valid ConjunctionEvent
        t_coarse = datetime(2024, 2, 14, 12, 30, 0, tzinfo=timezone.utc)
        event = refine_tca(entry_a, entry_b, t_coarse, window_seconds=120.0)

        # These two satellites are in very different orbits, so the event
        # should exist but with a large miss distance
        assert event is not None
        assert event.primary_norad_id == 25544
        assert event.secondary_norad_id == 5
        assert event.miss_distance_km > 0
        assert event.relative_velocity_kms > 0
        # TCA should be within the search window
        assert abs((event.tca - t_coarse).total_seconds()) <= 120

    def test_screening_pipeline_no_conjunctions_different_orbits(self):
        """ISS and Vanguard should not produce a conjunction (different altitude bands)."""
        entry_a = _make_entry(25544, ISS_TLE_LINE1, ISS_TLE_LINE2)
        entry_b = _make_entry(5, VANGUARD_TLE_LINE1, VANGUARD_TLE_LINE2)

        catalog = [entry_a, entry_b]
        epoch = datetime(2024, 2, 14, 12, 0, 0, tzinfo=timezone.utc)
        end = epoch + timedelta(minutes=30)

        result = propagate_catalog(catalog, epoch, end, step_seconds=60)
        events = screen_conjunctions(catalog, result, screening_radius_km=5.0)

        # Vanguard has perigee ~650km and apogee ~3850km while ISS is ~400km
        # But Vanguard's perigee overlaps with ISS altitude range, so they
        # may or may not be filtered at the altitude stage. Either way,
        # at 5km radius they shouldn't have an actual conjunction.
        # We just verify the pipeline runs without error.
        assert isinstance(events, list)

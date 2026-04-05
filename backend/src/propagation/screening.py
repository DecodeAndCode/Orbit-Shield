"""Conjunction screening pipeline.

Four-stage filter to detect close approaches between satellites:
1. Perigee/Apogee altitude overlap — quick orbital band rejection
2. Inclination filter — reject incompatible orbital planes
3. k-d tree spatial search — find pairs within screening radius at each time step
4. TCA refinement — numerical root-finding for exact time of closest approach
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import numpy as np
from scipy.optimize import minimize_scalar
from scipy.spatial import cKDTree
from sgp4.api import Satrec

from src.propagation.sgp4_engine import (
    CatalogEntry,
    PropagationResult,
    datetime_to_jd,
)

logger = logging.getLogger(__name__)


@dataclass
class ConjunctionEvent:
    """A detected close approach between two satellites."""

    primary_norad_id: int
    secondary_norad_id: int
    tca: datetime
    miss_distance_km: float
    relative_velocity_kms: float
    relative_position_km: np.ndarray | None = None
    relative_velocity_kms_vec: np.ndarray | None = None


def screen_conjunctions(
    catalog: list[CatalogEntry],
    prop_result: PropagationResult,
    screening_radius_km: float = 5.0,
    altitude_margin_km: float = 50.0,
    inclination_threshold_deg: float = 15.0,
) -> list[ConjunctionEvent]:
    """Run the full conjunction screening pipeline.

    Args:
        catalog: Satellite catalog entries (parallel with prop_result axes).
        prop_result: Propagation positions/velocities from propagate_catalog().
        screening_radius_km: k-d tree search radius in km.
        altitude_margin_km: Margin added to altitude bands for overlap check.
        inclination_threshold_deg: Max inclination difference for pre-filter.

    Returns:
        List of ConjunctionEvent for all detected close approaches.
    """
    if len(catalog) < 2:
        return []

    valid = prop_result.valid_mask
    valid_indices = np.where(valid)[0].tolist()

    if len(valid_indices) < 2:
        logger.info("Fewer than 2 valid satellites, no screening possible")
        return []

    # Stage 1: Altitude overlap filter
    candidate_pairs = altitude_overlap_filter(catalog, valid_indices, altitude_margin_km)
    logger.info(
        "Stage 1 (altitude overlap): %d candidate pairs from %d valid satellites",
        len(candidate_pairs),
        len(valid_indices),
    )

    if not candidate_pairs:
        return []

    # Stage 2: Inclination filter
    candidate_pairs = inclination_filter(catalog, candidate_pairs, inclination_threshold_deg)
    logger.info("Stage 2 (inclination filter): %d candidate pairs remaining", len(candidate_pairs))

    if not candidate_pairs:
        return []

    # Stage 3: k-d tree spatial search
    # Use a larger coarse radius to account for satellite motion between time steps.
    # At LEO speeds (~7.5 km/s), objects move ~450 km per 60s step.
    # Coarse radius = max_relative_velocity * step_seconds / 2 + screening_radius
    # Max relative velocity ~15 km/s (head-on LEO), so for 60s steps: 15*30 + 5 = 455 km
    step_seconds = (prop_result.times[1] - prop_result.times[0]).total_seconds() if len(prop_result.times) > 1 else 60
    max_rel_velocity_kms = 15.0  # Conservative max for LEO head-on encounters
    coarse_radius_km = max_rel_velocity_kms * step_seconds / 2.0 + screening_radius_km
    logger.info("Using coarse screening radius: %.0f km (step=%ds)", coarse_radius_km, step_seconds)

    coarse_hits = kdtree_screen(
        prop_result.positions,
        prop_result.times,
        candidate_pairs,
        coarse_radius_km,
    )
    logger.info("Stage 3 (k-d tree): %d close approach candidates found", len(coarse_hits))

    if not coarse_hits:
        return []

    # Stage 4: Refine TCA for each candidate, then filter by actual screening radius
    events: list[ConjunctionEvent] = []
    for (i, j), step_idx in coarse_hits.items():
        event = refine_tca(
            catalog[i],
            catalog[j],
            prop_result.times[step_idx],
            window_seconds=step_seconds,
        )
        if event is not None and event.miss_distance_km <= screening_radius_km:
            events.append(event)

    logger.info("Stage 4 (TCA refinement): %d conjunction events within %.1f km", len(events), screening_radius_km)
    return events


def altitude_overlap_filter(
    catalog: list[CatalogEntry],
    valid_indices: list[int],
    margin_km: float = 50.0,
) -> set[tuple[int, int]]:
    """Filter pairs to those with overlapping perigee/apogee altitude bands.

    Uses a sweep-line algorithm on sorted perigee altitudes for O(n log n)
    performance instead of O(n^2) brute force.

    Args:
        catalog: Full catalog entries.
        valid_indices: Indices of valid (non-decayed) satellites.
        margin_km: Margin added to each end of the altitude band.

    Returns:
        Set of (i, j) index pairs with overlapping altitude bands.
    """
    n = len(valid_indices)
    if n < 2:
        return set()

    # Build (index, perigee_low, apogee_high) tuples
    bands = []
    for idx in valid_indices:
        entry = catalog[idx]
        low = entry.perigee_alt_km - margin_km
        high = entry.apogee_alt_km + margin_km
        bands.append((idx, low, high))

    # Sort by lower bound of altitude band
    bands.sort(key=lambda x: x[1])

    pairs: set[tuple[int, int]] = set()

    # Sweep-line: for each satellite, check subsequent ones until their
    # perigee exceeds our apogee (no more overlap possible)
    for a in range(n):
        idx_a, low_a, high_a = bands[a]
        for b in range(a + 1, n):
            idx_b, low_b, high_b = bands[b]
            # Since sorted by low, if low_b > high_a, no more overlaps
            if low_b > high_a:
                break
            # Bands overlap
            pair = (min(idx_a, idx_b), max(idx_a, idx_b))
            pairs.add(pair)

    return pairs


def inclination_filter(
    catalog: list[CatalogEntry],
    candidate_pairs: set[tuple[int, int]],
    threshold_deg: float = 15.0,
) -> set[tuple[int, int]]:
    """Remove pairs with large inclination differences.

    Satellites in very different orbital planes are unlikely to have
    close approaches in LEO. High-altitude or polar crossing cases
    are still caught by the k-d tree stage.

    Args:
        catalog: Full catalog entries.
        candidate_pairs: Pairs that passed altitude overlap filter.
        threshold_deg: Maximum inclination difference to keep.

    Returns:
        Filtered set of pairs.
    """
    filtered: set[tuple[int, int]] = set()
    for i, j in candidate_pairs:
        delta = abs(catalog[i].inclination_deg - catalog[j].inclination_deg)
        if delta <= threshold_deg:
            filtered.add((i, j))
    return filtered


def kdtree_screen(
    positions: np.ndarray,
    times: list[datetime],
    candidate_pairs: set[tuple[int, int]],
    radius_km: float = 5.0,
) -> dict[tuple[int, int], int]:
    """Find close pairs at each time step using k-d tree spatial indexing.

    Builds a cKDTree at each time step and queries for pairs within the
    screening radius. Only pairs that passed pre-filters are retained.

    Args:
        positions: Shape (n_sats, n_steps, 3) position array in TEME km.
        times: List of datetimes corresponding to time steps.
        candidate_pairs: Pre-filtered set of (i, j) index pairs.
        radius_km: Screening radius in km.

    Returns:
        Dict mapping (i, j) -> time_step_index of the closest approach
        found during the coarse search.
    """
    n_sats, n_steps, _ = positions.shape
    # Track best (minimum distance) step for each pair
    best: dict[tuple[int, int], tuple[int, float]] = {}  # pair -> (step, dist)

    for t in range(n_steps):
        pos_at_t = positions[:, t, :]  # (n_sats, 3)

        # Find satellites with valid (non-NaN) positions at this step
        valid_at_t = ~np.any(np.isnan(pos_at_t), axis=1)
        valid_indices_t = np.where(valid_at_t)[0]

        if len(valid_indices_t) < 2:
            continue

        # Build k-d tree from valid positions only
        valid_positions = pos_at_t[valid_indices_t]
        tree = cKDTree(valid_positions)
        step_pairs = tree.query_pairs(r=radius_km)

        for local_a, local_b in step_pairs:
            # Map back from local k-d tree indices to global catalog indices
            global_a = int(valid_indices_t[local_a])
            global_b = int(valid_indices_t[local_b])
            pair_sorted = (min(global_a, global_b), max(global_a, global_b))
            if pair_sorted not in candidate_pairs:
                continue

            dist = float(np.linalg.norm(pos_at_t[global_a] - pos_at_t[global_b]))
            if pair_sorted not in best or dist < best[pair_sorted][1]:
                best[pair_sorted] = (t, dist)

    return {pair: step for pair, (step, _) in best.items()}


def _sgp4_distance(
    sat_a: Satrec,
    sat_b: Satrec,
    dt: datetime,
) -> tuple[float, np.ndarray, np.ndarray]:
    """Compute distance and relative velocity between two satellites at a time.

    Args:
        sat_a: First satellite Satrec object.
        sat_b: Second satellite Satrec object.
        dt: UTC datetime to evaluate.

    Returns:
        (distance_km, position_diff, velocity_diff)
    """
    jd, fr = datetime_to_jd(dt)

    e1, r1, v1 = sat_a.sgp4(jd, fr)
    e2, r2, v2 = sat_b.sgp4(jd, fr)

    if e1 != 0 or e2 != 0:
        return float("inf"), np.zeros(3), np.zeros(3)

    pos_a = np.array(r1)
    pos_b = np.array(r2)
    vel_a = np.array(v1)
    vel_b = np.array(v2)

    diff = pos_a - pos_b
    dist = float(np.linalg.norm(diff))
    vel_diff = vel_a - vel_b

    return dist, diff, vel_diff


def refine_tca(
    entry_a: CatalogEntry,
    entry_b: CatalogEntry,
    t_coarse: datetime,
    window_seconds: float = 120.0,
) -> ConjunctionEvent | None:
    """Refine the Time of Closest Approach using Brent's method.

    Starting from the coarse TCA found by the k-d tree, searches
    ±window_seconds with fine-grained SGP4 propagation to find the
    exact minimum distance.

    Args:
        entry_a: First satellite catalog entry.
        entry_b: Second satellite catalog entry.
        t_coarse: Coarse TCA from k-d tree step.
        window_seconds: Half-width of the search window in seconds.

    Returns:
        ConjunctionEvent with refined TCA, or None if SGP4 fails.
    """
    t_start = t_coarse - timedelta(seconds=window_seconds)

    def distance_at_offset(offset_seconds: float) -> float:
        t = t_start + timedelta(seconds=offset_seconds)
        dist, _, _ = _sgp4_distance(entry_a.satrec, entry_b.satrec, t)
        return dist

    result = minimize_scalar(
        distance_at_offset,
        bounds=(0, 2 * window_seconds),
        method="bounded",
        options={"xatol": 0.01},  # 10ms precision
    )

    tca = t_start + timedelta(seconds=result.x)
    dist, pos_diff, vel_diff = _sgp4_distance(entry_a.satrec, entry_b.satrec, tca)

    if math.isinf(dist):
        return None

    rel_vel = float(np.linalg.norm(vel_diff))

    return ConjunctionEvent(
        primary_norad_id=entry_a.norad_id,
        secondary_norad_id=entry_b.norad_id,
        tca=tca,
        miss_distance_km=dist,
        relative_velocity_kms=rel_vel,
        relative_position_km=pos_diff,
        relative_velocity_kms_vec=vel_diff,
    )

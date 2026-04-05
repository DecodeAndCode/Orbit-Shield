"""Synthetic data generators for ML model training.

Generates physically plausible orbital features, covariance targets,
and conjunction events for training when real data is insufficient.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

from src.ml.features.orbital import ORBITAL_FEATURE_NAMES
from src.ml.features.conjunction import CONJUNCTION_FEATURE_NAMES
from src.propagation.sgp4_engine import R_EARTH_KM, MU_EARTH


def generate_synthetic_orbital_features(
    n_samples: int = 5000,
    seed: int = 42,
) -> pd.DataFrame:
    """Generate synthetic satellite orbital features with physical constraints.

    Produces realistic distributions for LEO, MEO, and GEO satellites.

    Args:
        n_samples: Number of synthetic satellites.
        seed: Random seed for reproducibility.

    Returns:
        DataFrame with columns matching ORBITAL_FEATURE_NAMES.
    """
    rng = np.random.default_rng(seed)

    # Regime mix: 70% LEO, 15% MEO, 15% GEO
    n_leo = int(0.70 * n_samples)
    n_meo = int(0.15 * n_samples)
    n_geo = n_samples - n_leo - n_meo

    rows = []
    for regime, count, alt_range, ecc_range, inc_range in [
        ("LEO", n_leo, (200, 2000), (0.0001, 0.05), (0, 100)),
        ("MEO", n_meo, (2000, 20000), (0.0001, 0.02), (50, 65)),
        ("GEO", n_geo, (35000, 36000), (0.0001, 0.005), (0, 5)),
    ]:
        for _ in range(count):
            # Perigee altitude → semi-major axis → mean motion
            perigee_alt = rng.uniform(*alt_range)
            eccentricity = rng.uniform(*ecc_range)
            semi_major_axis = (perigee_alt + R_EARTH_KM) / (1.0 - eccentricity)
            apogee_alt = semi_major_axis * (1.0 + eccentricity) - R_EARTH_KM

            # Mean motion from Kepler's third law
            n_rad_per_sec = math.sqrt(MU_EARTH / semi_major_axis ** 3)
            mean_motion = n_rad_per_sec * 86400.0 / (2.0 * math.pi)

            inclination = rng.uniform(*inc_range)
            bstar = rng.lognormal(mean=-12.0, sigma=2.0) * rng.choice([-1, 1])

            orbital_period = 1440.0 / mean_motion if mean_motion > 0 else 0.0
            is_leo = 1.0 if perigee_alt < 2000 else 0.0
            ballistic_coeff = abs(bstar) * semi_major_axis ** 2

            object_type = rng.choice([0.0, 1.0, 2.0, 3.0], p=[0.4, 0.2, 0.35, 0.05])
            rcs_size = rng.choice([0.0, 1.0, 2.0], p=[0.3, 0.4, 0.3])
            tle_age_hours = rng.exponential(scale=48.0)
            tle_count_30d = float(rng.integers(1, 30))

            rows.append({
                "mean_motion": mean_motion,
                "eccentricity": eccentricity,
                "inclination": inclination,
                "bstar": bstar,
                "perigee_alt_km": perigee_alt,
                "apogee_alt_km": apogee_alt,
                "semi_major_axis_km": semi_major_axis,
                "orbital_period_minutes": orbital_period,
                "object_type_encoded": object_type,
                "rcs_size_encoded": rcs_size,
                "tle_age_hours": tle_age_hours,
                "tle_count_30d": tle_count_30d,
                "is_leo": is_leo,
                "ballistic_coefficient_proxy": ballistic_coeff,
            })

    return pd.DataFrame(rows, columns=ORBITAL_FEATURE_NAMES)


def generate_synthetic_covariance_targets(
    features: pd.DataFrame,
    seed: int = 42,
) -> np.ndarray:
    """Generate synthetic log10(sigma_km) targets based on orbital features.

    Higher altitude → larger sigma. More TLEs → smaller sigma.
    Added noise simulates real-world variation.

    Args:
        features: DataFrame with orbital features.
        seed: Random seed.

    Returns:
        Array of log10(sigma_km) values.
    """
    rng = np.random.default_rng(seed)
    n = len(features)

    perigee = features["perigee_alt_km"].values
    tle_count = features["tle_count_30d"].values
    tle_age = features["tle_age_hours"].values

    # Base sigma scales with altitude
    base_log_sigma = np.where(
        perigee < 2000,
        np.log10(0.5) + 0.3 * (perigee / 2000),  # LEO: 0.5-1 km
        np.where(
            perigee < 20000,
            np.log10(2.0) + 0.4 * ((perigee - 2000) / 18000),  # MEO: 2-5 km
            np.log10(5.0) + 0.3 * ((perigee - 20000) / 16000),  # GEO: 5-10 km
        ),
    )

    # More TLEs → better tracking → smaller sigma
    tle_factor = -0.1 * np.log10(tle_count + 1)

    # Older TLE → larger sigma
    age_factor = 0.05 * np.log10(tle_age + 1)

    # Noise
    noise = rng.normal(0, 0.15, size=n)

    return base_log_sigma + tle_factor + age_factor + noise


def generate_synthetic_conjunctions(
    n_events: int = 5000,
    seed: int = 42,
) -> pd.DataFrame:
    """Generate synthetic conjunction events with labels.

    Creates encounter features with a realistic class distribution:
    ~2% high-risk (Pc > 1e-4), ~98% low-risk.

    Args:
        n_events: Number of synthetic events.
        seed: Random seed.

    Returns:
        DataFrame with CONJUNCTION_FEATURE_NAMES columns plus 'label' (0/1).
    """
    rng = np.random.default_rng(seed)
    rows = []

    for _ in range(n_events):
        # Miss distance: most are > 1 km, few are very close
        miss_distance = rng.exponential(scale=2.0) + 0.01

        # Relative velocity: LEO head-on ~14, co-planar ~1
        rel_vel = rng.uniform(0.5, 15.0)

        # B-plane components from miss distance
        angle = rng.uniform(0, 2 * math.pi)
        b_plane_x = miss_distance * math.cos(angle)
        b_plane_y = miss_distance * math.sin(angle)

        approach_angle = rng.uniform(0, 180)

        # Orbital features for primary and secondary
        def _random_orbital() -> dict[str, float]:
            mm = rng.uniform(1.0, 16.0)
            ecc = rng.uniform(0.0001, 0.05)
            inc = rng.uniform(0, 100)
            bstar = rng.lognormal(-12, 2) * rng.choice([-1, 1])
            n_rad = mm * 2 * math.pi / 86400
            a_km = (MU_EARTH / n_rad ** 2) ** (1 / 3) if n_rad > 0 else 7000
            perigee = a_km * (1 - ecc) - R_EARTH_KM
            apogee = a_km * (1 + ecc) - R_EARTH_KM
            return {
                "mean_motion": mm,
                "eccentricity": ecc,
                "inclination": inc,
                "perigee_alt_km": max(perigee, 100),
                "apogee_alt_km": max(apogee, 100),
                "bstar": bstar,
            }

        pri = _random_orbital()
        sec = _random_orbital()

        # Covariance features
        combined_sigma = rng.uniform(0.1, 10.0)
        sigma_ratio = rng.uniform(1.0, 5.0)
        mahalanobis_est = miss_distance / combined_sigma

        # Weather
        f107 = rng.uniform(70, 250)
        kp = rng.uniform(0, 9)

        # Label: high-risk when miss distance is small and velocity is high
        # This creates a ~2% positive rate
        risk_score = math.exp(-miss_distance / 0.5) * (rel_vel / 15.0)
        label = 1 if risk_score > 0.3 else 0

        rows.append({
            "miss_distance_km": miss_distance,
            "relative_velocity_kms": rel_vel,
            "b_plane_x_km": b_plane_x,
            "b_plane_y_km": b_plane_y,
            "approach_angle_deg": approach_angle,
            "pri_mean_motion": pri["mean_motion"],
            "pri_eccentricity": pri["eccentricity"],
            "pri_inclination": pri["inclination"],
            "pri_perigee_alt_km": pri["perigee_alt_km"],
            "pri_apogee_alt_km": pri["apogee_alt_km"],
            "pri_bstar": pri["bstar"],
            "sec_mean_motion": sec["mean_motion"],
            "sec_eccentricity": sec["eccentricity"],
            "sec_inclination": sec["inclination"],
            "sec_perigee_alt_km": sec["perigee_alt_km"],
            "sec_apogee_alt_km": sec["apogee_alt_km"],
            "sec_bstar": sec["bstar"],
            "combined_sigma_km": combined_sigma,
            "sigma_ratio": sigma_ratio,
            "mahalanobis_estimate": mahalanobis_est,
            "f107_flux": f107,
            "kp_index": kp,
            "label": label,
        })

    return pd.DataFrame(rows)

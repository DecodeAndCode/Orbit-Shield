"""Conjunction encounter feature extraction for ML models.

Extracts 22 features from encounter geometry and orbital metadata:
- 5 encounter features: miss_distance, relative_velocity, b_plane_x, b_plane_y, approach_angle
- 6 primary orbital features: mean_motion, eccentricity, inclination, perigee_alt, apogee_alt, bstar
- 6 secondary orbital features: same as primary
- 3 covariance features: combined_sigma_km, sigma_ratio, mahalanobis_estimate
- 2 weather features: f107_flux, kp_index
"""

from __future__ import annotations

import math

import numpy as np

from src.propagation.probability import build_encounter_frame

CONJUNCTION_FEATURE_NAMES = [
    # Encounter geometry (5)
    "miss_distance_km",
    "relative_velocity_kms",
    "b_plane_x_km",
    "b_plane_y_km",
    "approach_angle_deg",
    # Primary orbital (6)
    "pri_mean_motion",
    "pri_eccentricity",
    "pri_inclination",
    "pri_perigee_alt_km",
    "pri_apogee_alt_km",
    "pri_bstar",
    # Secondary orbital (6)
    "sec_mean_motion",
    "sec_eccentricity",
    "sec_inclination",
    "sec_perigee_alt_km",
    "sec_apogee_alt_km",
    "sec_bstar",
    # Covariance (3)
    "combined_sigma_km",
    "sigma_ratio",
    "mahalanobis_estimate",
    # Weather (2)
    "f107_flux",
    "kp_index",
]


def extract_conjunction_features(
    miss_distance_km: float,
    relative_velocity_kms: float,
    relative_position_km: np.ndarray,
    relative_velocity_vec: np.ndarray,
    primary_features: dict[str, float],
    secondary_features: dict[str, float],
    primary_cov: np.ndarray | None = None,
    secondary_cov: np.ndarray | None = None,
    weather: dict[str, float] | None = None,
) -> dict[str, float]:
    """Extract 22 features for a conjunction event.

    Args:
        miss_distance_km: Scalar miss distance at TCA.
        relative_velocity_kms: Scalar relative velocity at TCA.
        relative_position_km: 3D relative position vector at TCA.
        relative_velocity_vec: 3D relative velocity vector at TCA.
        primary_features: Orbital feature dict for primary object.
        secondary_features: Orbital feature dict for secondary object.
        primary_cov: 3x3 position covariance of primary (km²), or None.
        secondary_cov: 3x3 position covariance of secondary (km²), or None.
        weather: Dict with f107_flux and kp_index, or None.

    Returns:
        Feature dict with 22 values.
    """
    # B-plane projection
    vel_norm = np.linalg.norm(relative_velocity_vec)
    if vel_norm > 1e-10:
        bplane = build_encounter_frame(relative_velocity_vec)
        miss_b = bplane.T @ relative_position_km
        b_plane_x = float(miss_b[0])
        b_plane_y = float(miss_b[1])
    else:
        b_plane_x = 0.0
        b_plane_y = 0.0

    # Approach angle (angle between relative position and velocity)
    pos_norm = np.linalg.norm(relative_position_km)
    if pos_norm > 1e-10 and vel_norm > 1e-10:
        cos_angle = np.dot(relative_position_km, relative_velocity_vec) / (
            pos_norm * vel_norm
        )
        cos_angle = np.clip(cos_angle, -1.0, 1.0)
        approach_angle = math.degrees(math.acos(float(cos_angle)))
    else:
        approach_angle = 90.0

    # Covariance features
    if primary_cov is not None and secondary_cov is not None:
        combined_cov = primary_cov + secondary_cov
        eigenvalues = np.linalg.eigvalsh(combined_cov)
        eigenvalues = np.maximum(eigenvalues, 1e-20)
        combined_sigma = float(np.sqrt(eigenvalues.max()))
        sigma_ratio = float(np.sqrt(eigenvalues.max() / eigenvalues.min()))
        if combined_sigma > 0:
            mahalanobis_est = miss_distance_km / combined_sigma
        else:
            mahalanobis_est = 0.0
    else:
        combined_sigma = 1.0
        sigma_ratio = 1.0
        mahalanobis_est = miss_distance_km

    weather = weather or {}

    return {
        "miss_distance_km": miss_distance_km,
        "relative_velocity_kms": relative_velocity_kms,
        "b_plane_x_km": b_plane_x,
        "b_plane_y_km": b_plane_y,
        "approach_angle_deg": approach_angle,
        "pri_mean_motion": primary_features.get("mean_motion", 15.0),
        "pri_eccentricity": primary_features.get("eccentricity", 0.001),
        "pri_inclination": primary_features.get("inclination", 0.0),
        "pri_perigee_alt_km": primary_features.get("perigee_alt_km", 400.0),
        "pri_apogee_alt_km": primary_features.get("apogee_alt_km", 420.0),
        "pri_bstar": primary_features.get("bstar", 0.0),
        "sec_mean_motion": secondary_features.get("mean_motion", 15.0),
        "sec_eccentricity": secondary_features.get("eccentricity", 0.001),
        "sec_inclination": secondary_features.get("inclination", 0.0),
        "sec_perigee_alt_km": secondary_features.get("perigee_alt_km", 400.0),
        "sec_apogee_alt_km": secondary_features.get("apogee_alt_km", 420.0),
        "sec_bstar": secondary_features.get("bstar", 0.0),
        "combined_sigma_km": combined_sigma,
        "sigma_ratio": sigma_ratio,
        "mahalanobis_estimate": mahalanobis_est,
        "f107_flux": weather.get("f107_flux", 150.0),
        "kp_index": weather.get("kp_index", 3.0),
    }

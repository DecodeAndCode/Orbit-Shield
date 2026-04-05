"""Classical collision probability computation (B-plane method).

Implements the NASA CARA approach: project the encounter geometry into
the B-plane (perpendicular to relative velocity), combine covariances,
and integrate a 2D Gaussian over the circular hard-body exclusion zone.

Two methods are provided:
- Linearized (Alfano): Pc ≈ R²/(2√det(C)) × exp(-½ b^T C⁻¹ b).
  Fast, accurate when R << σ (typical operational case).
- Numerical: scipy.integrate.dblquad over the hard-body circle.
  Used when R/σ_min ≥ 0.1 (R comparable to uncertainty).

References:
    Alfano, S. (2005) "A Numerical Implementation of Spherical Object
    Collision Probability", AIAA/AAS.
    NASA CARA, "Conjunction Assessment Risk Analysis", various.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from datetime import datetime, timezone

import numpy as np
from scipy.integrate import dblquad
from sgp4.api import Satrec

from src.propagation.sgp4_engine import datetime_to_jd

logger = logging.getLogger(__name__)

# Threshold for switching between linearized and numerical integration.
# When hard_body_radius / sigma_min < this value, use linearized.
LINEARIZED_THRESHOLD = 0.1

# Default combined hard-body radius for two active satellites (km).
DEFAULT_HARD_BODY_RADIUS_KM = 0.020  # 20 meters


@dataclass
class CollisionProbabilityResult:
    """Result of a collision probability computation."""

    pc: float
    method: str  # "linearized" or "numerical"
    miss_distance_bplane_km: float
    mahalanobis_distance: float
    covariance_source: str  # "cdm", "tle_ensemble", "default"


def compute_collision_probability(
    relative_position_km: np.ndarray,
    relative_velocity_kms: np.ndarray,
    primary_cov: np.ndarray,
    secondary_cov: np.ndarray,
    hard_body_radius: float = DEFAULT_HARD_BODY_RADIUS_KM,
) -> CollisionProbabilityResult:
    """Compute classical collision probability via B-plane projection.

    Args:
        relative_position_km: 3D position difference at TCA (km), primary - secondary.
        relative_velocity_kms: 3D velocity difference at TCA (km/s).
        primary_cov: 3x3 position covariance of primary object (km²).
        secondary_cov: 3x3 position covariance of secondary object (km²).
        hard_body_radius: Combined hard-body radius of both objects (km).

    Returns:
        CollisionProbabilityResult with Pc and metadata.
    """
    # 1. Build B-plane projection
    bplane_matrix = build_encounter_frame(relative_velocity_kms)

    # 2. Project miss distance into B-plane (3D → 2D)
    miss_b = bplane_matrix.T @ relative_position_km  # (2,)

    # 3. Combine and project covariance into B-plane
    combined_cov_3d = primary_cov + secondary_cov
    cov_b = bplane_matrix.T @ combined_cov_3d @ bplane_matrix  # (2, 2)

    # 4. Compute miss distance and Mahalanobis distance
    miss_dist_b = float(np.linalg.norm(miss_b))
    try:
        cov_b_inv = np.linalg.inv(cov_b)
        mahalanobis = float(np.sqrt(miss_b @ cov_b_inv @ miss_b))
    except np.linalg.LinAlgError:
        logger.warning("Singular B-plane covariance, returning Pc=0")
        return CollisionProbabilityResult(
            pc=0.0,
            method="singular",
            miss_distance_bplane_km=miss_dist_b,
            mahalanobis_distance=float("inf"),
            covariance_source="unknown",
        )

    # 5. Validate eigenvalues
    eigenvalues = np.linalg.eigvalsh(cov_b)
    if np.any(eigenvalues <= 0):
        logger.warning("Non-positive-definite B-plane covariance, returning Pc=0")
        return CollisionProbabilityResult(
            pc=0.0,
            method="invalid_covariance",
            miss_distance_bplane_km=miss_dist_b,
            mahalanobis_distance=mahalanobis,
            covariance_source="unknown",
        )

    # 6. Choose method based on R/σ_min ratio
    sigma_min = float(np.sqrt(eigenvalues.min()))
    ratio = hard_body_radius / sigma_min if sigma_min > 0 else float("inf")

    if ratio < LINEARIZED_THRESHOLD:
        pc = _pc_max_probability(miss_b, cov_b, hard_body_radius)
        method = "linearized"
    else:
        pc = _pc_numerical_integration(miss_b, cov_b, hard_body_radius)
        method = "numerical"

    return CollisionProbabilityResult(
        pc=pc,
        method=method,
        miss_distance_bplane_km=miss_dist_b,
        mahalanobis_distance=mahalanobis,
        covariance_source="unknown",  # Caller sets this
    )


def build_encounter_frame(relative_velocity: np.ndarray) -> np.ndarray:
    """Construct the B-plane projection matrix from relative velocity.

    The B-plane is perpendicular to the relative velocity vector. We build
    two orthonormal basis vectors spanning this plane.

    Args:
        relative_velocity: 3D relative velocity vector (km/s).

    Returns:
        (3, 2) matrix whose columns are the B-plane basis vectors.
    """
    v = relative_velocity / np.linalg.norm(relative_velocity)

    # Choose a reference vector not parallel to v
    ref = np.array([0.0, 0.0, 1.0])
    if abs(np.dot(v, ref)) > 0.9:
        ref = np.array([1.0, 0.0, 0.0])

    # Gram-Schmidt: e1 = ref - (ref·v)v, normalized
    e1 = ref - np.dot(ref, v) * v
    e1 = e1 / np.linalg.norm(e1)

    # e2 = v × e1 (right-hand rule)
    e2 = np.cross(v, e1)
    e2 = e2 / np.linalg.norm(e2)

    return np.column_stack([e1, e2])


def _pc_max_probability(
    miss_b: np.ndarray,
    cov_b: np.ndarray,
    radius: float,
) -> float:
    """Linearized (Alfano) collision probability approximation.

    Pc ≈ R² / (2 √det(C)) × exp(-½ b^T C⁻¹ b)

    Valid when R << σ_min (hard-body radius much smaller than uncertainty).

    Args:
        miss_b: 2D miss distance in B-plane (km).
        cov_b: 2x2 combined covariance in B-plane (km²).
        radius: Combined hard-body radius (km).

    Returns:
        Collision probability.
    """
    det_c = np.linalg.det(cov_b)
    if det_c <= 0:
        return 0.0

    cov_inv = np.linalg.inv(cov_b)
    exponent = -0.5 * float(miss_b @ cov_inv @ miss_b)
    pc = (radius ** 2) / (2.0 * math.sqrt(det_c)) * math.exp(exponent)

    return min(pc, 1.0)


def _pc_numerical_integration(
    miss_b: np.ndarray,
    cov_b: np.ndarray,
    radius: float,
) -> float:
    """Full numerical integration of 2D Gaussian over hard-body circle.

    Integrates the bivariate Gaussian PDF over a circle of the given radius
    centered at the origin, where the Gaussian is centered at miss_b.

    Args:
        miss_b: 2D miss distance in B-plane (km).
        cov_b: 2x2 combined covariance in B-plane (km²).
        radius: Combined hard-body radius (km).

    Returns:
        Collision probability.
    """
    det_c = np.linalg.det(cov_b)
    if det_c <= 0:
        return 0.0

    cov_inv = np.linalg.inv(cov_b)
    norm_factor = 1.0 / (2.0 * math.pi * math.sqrt(det_c))

    def integrand(y: float, x: float) -> float:
        d = np.array([x - miss_b[0], y - miss_b[1]])
        exponent = -0.5 * float(d @ cov_inv @ d)
        return norm_factor * math.exp(exponent)

    def y_lower(x: float) -> float:
        r2 = radius ** 2 - x ** 2
        return -math.sqrt(max(r2, 0.0))

    def y_upper(x: float) -> float:
        r2 = radius ** 2 - x ** 2
        return math.sqrt(max(r2, 0.0))

    pc, _ = dblquad(
        integrand,
        -radius,
        radius,
        y_lower,
        y_upper,
        epsabs=1e-12,
        epsrel=1e-10,
    )

    return min(max(pc, 0.0), 1.0)


def estimate_covariance_from_tles(
    satrecs: list[Satrec],
    target_epoch: datetime,
) -> np.ndarray | None:
    """Estimate position covariance from sequential TLE propagations.

    Propagates multiple historical TLEs to the same target epoch and computes
    the sample covariance of the resulting position scatter. This captures
    the uncertainty inherent in TLE-based orbit determination.

    Args:
        satrecs: List of Satrec objects built from sequential TLEs (≥3 required).
        target_epoch: UTC datetime to propagate all TLEs to.

    Returns:
        3x3 position covariance matrix (km²), or None if insufficient data.
    """
    if len(satrecs) < 3:
        return None

    jd, fr = datetime_to_jd(target_epoch)
    positions = []

    for sat in satrecs:
        e, r, _ = sat.sgp4(jd, fr)
        if e == 0:
            positions.append(r)

    if len(positions) < 3:
        return None

    pos_array = np.array(positions)  # (N, 3)
    cov = np.cov(pos_array, rowvar=False)  # (3, 3)

    # Sanity check: covariance should be positive semi-definite
    eigenvalues = np.linalg.eigvalsh(cov)
    if np.any(eigenvalues < 0):
        logger.warning("Negative eigenvalue in TLE covariance estimate, clamping")
        cov = _nearest_positive_definite(cov)

    return cov


def _nearest_positive_definite(a: np.ndarray) -> np.ndarray:
    """Find the nearest positive-definite matrix via eigenvalue clamping."""
    eigenvalues, eigenvectors = np.linalg.eigh(a)
    eigenvalues = np.maximum(eigenvalues, 1e-10)
    return eigenvectors @ np.diag(eigenvalues) @ eigenvectors.T


def default_covariance_km2(altitude_km: float) -> np.ndarray:
    """Altitude-based fallback covariance when no TLE ensemble or CDM is available.

    Returns an isotropic 3x3 diagonal covariance with σ scaled by altitude regime:
    - LEO (< 2000 km): σ = 1 km
    - MEO (2000–20000 km): σ = 5 km
    - GEO (> 20000 km): σ = 10 km

    Args:
        altitude_km: Approximate orbital altitude in km.

    Returns:
        3x3 diagonal covariance matrix (km²).
    """
    if altitude_km < 2000:
        sigma = 1.0
    elif altitude_km < 20000:
        sigma = 5.0
    else:
        sigma = 10.0

    return np.diag([sigma ** 2, sigma ** 2, sigma ** 2])

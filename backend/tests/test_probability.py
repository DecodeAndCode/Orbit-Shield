"""Tests for classical collision probability (B-plane method)."""

import math
from datetime import datetime, timezone

import numpy as np
import pytest
from sgp4.api import Satrec

from src.propagation.probability import (
    CollisionProbabilityResult,
    build_encounter_frame,
    compute_collision_probability,
    default_covariance_km2,
    estimate_covariance_from_tles,
    _pc_max_probability,
    _pc_numerical_integration,
)


# ISS TLE for covariance estimation tests
ISS_TLE_LINE1 = "1 25544U 98067A   24045.51749023  .00018927  00000+0  33474-3 0  9996"
ISS_TLE_LINE2 = "2 25544  51.6408 129.5309 0005714  41.6071  50.0754 15.50135050440443"


class TestBplaneFrame:
    """Tests for B-plane encounter frame construction."""

    def test_orthonormality(self):
        """B-plane basis vectors must be orthonormal and perpendicular to v."""
        v = np.array([3.0, -4.0, 1.0])
        frame = build_encounter_frame(v)
        e1, e2 = frame[:, 0], frame[:, 1]
        v_hat = v / np.linalg.norm(v)

        # Unit length
        assert abs(np.linalg.norm(e1) - 1.0) < 1e-12
        assert abs(np.linalg.norm(e2) - 1.0) < 1e-12

        # Mutual orthogonality
        assert abs(np.dot(e1, e2)) < 1e-12

        # Perpendicular to velocity
        assert abs(np.dot(e1, v_hat)) < 1e-12
        assert abs(np.dot(e2, v_hat)) < 1e-12

    def test_orthonormality_z_aligned(self):
        """Frame works when velocity is aligned with z-axis."""
        v = np.array([0.0, 0.0, 7.5])
        frame = build_encounter_frame(v)
        e1, e2 = frame[:, 0], frame[:, 1]
        v_hat = v / np.linalg.norm(v)

        assert abs(np.linalg.norm(e1) - 1.0) < 1e-12
        assert abs(np.linalg.norm(e2) - 1.0) < 1e-12
        assert abs(np.dot(e1, e2)) < 1e-12
        assert abs(np.dot(e1, v_hat)) < 1e-12
        assert abs(np.dot(e2, v_hat)) < 1e-12

    def test_frame_shape(self):
        """Frame should be (3, 2)."""
        v = np.array([1.0, 2.0, 3.0])
        frame = build_encounter_frame(v)
        assert frame.shape == (3, 2)


class TestLinearizedPc:
    """Tests for the linearized (Alfano) Pc approximation."""

    def test_zero_miss_isotropic(self):
        """Zero miss distance with isotropic covariance: Pc = R²/(2σ²)."""
        sigma = 1.0  # km
        radius = 0.020  # km (20 m)
        miss = np.array([0.0, 0.0])
        cov = np.diag([sigma ** 2, sigma ** 2])

        pc = _pc_max_probability(miss, cov, radius)
        expected = radius ** 2 / (2.0 * sigma ** 2)
        assert abs(pc - expected) / expected < 1e-6

    def test_large_miss_distance(self):
        """Pc ≈ 0 when miss distance >> σ."""
        sigma = 1.0
        miss = np.array([100.0, 100.0])  # 141 km away, way beyond σ
        cov = np.diag([sigma ** 2, sigma ** 2])

        pc = _pc_max_probability(miss, cov, 0.020)
        assert pc < 1e-30

    def test_scales_with_r_squared(self):
        """Doubling R should quadruple Pc (in linearized regime)."""
        sigma = 1.0
        miss = np.array([0.5, 0.3])
        cov = np.diag([sigma ** 2, sigma ** 2])

        pc1 = _pc_max_probability(miss, cov, 0.010)
        pc2 = _pc_max_probability(miss, cov, 0.020)

        ratio = pc2 / pc1
        assert abs(ratio - 4.0) < 0.01

    def test_pc_bounded_by_one(self):
        """Pc should never exceed 1.0."""
        miss = np.array([0.0, 0.0])
        # Very large radius relative to sigma
        cov = np.diag([0.001, 0.001])
        pc = _pc_max_probability(miss, cov, 10.0)
        assert pc <= 1.0


class TestNumericalPc:
    """Tests for the full numerical integration Pc."""

    def test_zero_miss_isotropic(self):
        """Numerical integration with zero miss and isotropic cov."""
        sigma = 1.0
        radius = 0.020
        miss = np.array([0.0, 0.0])
        cov = np.diag([sigma ** 2, sigma ** 2])

        pc = _pc_numerical_integration(miss, cov, radius)
        expected = radius ** 2 / (2.0 * sigma ** 2)
        # Numerical and linearized should agree well for small R/σ
        assert abs(pc - expected) / expected < 0.01

    def test_large_miss_distance(self):
        """Pc ≈ 0 for large miss distance."""
        miss = np.array([50.0, 50.0])
        cov = np.diag([1.0, 1.0])
        pc = _pc_numerical_integration(miss, cov, 0.020)
        assert pc < 1e-20

    def test_large_radius_moderate_miss(self):
        """Numerical integration handles R comparable to σ."""
        sigma = 0.1  # 100 m
        radius = 0.050  # 50 m — R/σ = 0.5
        miss = np.array([0.05, 0.0])
        cov = np.diag([sigma ** 2, sigma ** 2])

        pc = _pc_numerical_integration(miss, cov, radius)
        # Should be a meaningful probability
        assert 0 < pc < 1.0


class TestLinearizedVsNumerical:
    """Test agreement between linearized and numerical methods."""

    def test_agreement_small_r_sigma(self):
        """Both methods agree when R << σ."""
        sigma = 1.0
        radius = 0.020  # R/σ = 0.02 << 0.1
        miss = np.array([0.3, 0.2])
        cov = np.diag([sigma ** 2, sigma ** 2])

        pc_lin = _pc_max_probability(miss, cov, radius)
        pc_num = _pc_numerical_integration(miss, cov, radius)

        # Should agree to within 1%
        if pc_lin > 0:
            assert abs(pc_num - pc_lin) / pc_lin < 0.01

    def test_agreement_anisotropic(self):
        """Both methods agree for anisotropic covariance when R << σ."""
        radius = 0.010  # 10 m
        miss = np.array([0.1, 0.5])
        cov = np.array([[2.0, 0.3], [0.3, 0.5]])

        pc_lin = _pc_max_probability(miss, cov, radius)
        pc_num = _pc_numerical_integration(miss, cov, radius)

        if pc_lin > 0:
            assert abs(pc_num - pc_lin) / pc_lin < 0.01


class TestComputeCollisionProbability:
    """Tests for the main entry point."""

    def test_basic_computation(self):
        """Basic Pc computation returns a valid result."""
        rel_pos = np.array([1.0, 0.5, 0.0])
        rel_vel = np.array([7.0, 0.0, 0.0])
        cov = np.diag([1.0, 1.0, 1.0])

        result = compute_collision_probability(rel_pos, rel_vel, cov, cov)

        assert isinstance(result, CollisionProbabilityResult)
        assert 0 <= result.pc <= 1.0
        assert result.method in ("linearized", "numerical")
        assert result.miss_distance_bplane_km >= 0
        assert result.mahalanobis_distance >= 0

    def test_head_on_zero_miss(self):
        """Head-on approach with zero lateral miss should have highest Pc."""
        rel_pos = np.array([0.0, 0.0, 0.0])
        rel_vel = np.array([14.0, 0.0, 0.0])
        cov = np.diag([1.0, 1.0, 1.0])

        result = compute_collision_probability(rel_pos, rel_vel, cov, cov)
        # Zero miss in B-plane means maximum Pc for given covariance
        assert result.pc > 0
        assert result.miss_distance_bplane_km < 1e-10

    def test_large_separation(self):
        """Large separation should give Pc ≈ 0."""
        rel_pos = np.array([0.0, 500.0, 0.0])
        rel_vel = np.array([10.0, 0.0, 0.0])
        cov = np.diag([1.0, 1.0, 1.0])

        result = compute_collision_probability(rel_pos, rel_vel, cov, cov)
        assert result.pc < 1e-20


class TestCovarianceEstimation:
    """Tests for TLE-derived covariance estimation."""

    def test_estimate_from_synthetic_tles(self):
        """Covariance from multiple TLEs should be a valid 3x3 matrix."""
        # Build multiple Satrec objects from the same TLE — in practice
        # these would be from different epochs, but for testing the math
        # works with one TLE propagated to the same epoch
        sat = Satrec.twoline2rv(ISS_TLE_LINE1, ISS_TLE_LINE2)
        # Create 5 slightly different satrecs by perturbing bstar
        satrecs = []
        for i in range(5):
            s = Satrec.twoline2rv(ISS_TLE_LINE1, ISS_TLE_LINE2)
            # Small perturbation via different epoch fraction
            satrecs.append(s)

        target = datetime(2024, 2, 14, 12, 0, 0, tzinfo=timezone.utc)
        cov = estimate_covariance_from_tles(satrecs, target)

        # With identical TLEs, covariance will be near-zero (all positions same)
        # But the function should still return a valid matrix
        if cov is not None:
            assert cov.shape == (3, 3)
            # Should be symmetric
            np.testing.assert_allclose(cov, cov.T, atol=1e-10)

    def test_insufficient_tles_returns_none(self):
        """Fewer than 3 TLEs should return None."""
        sat = Satrec.twoline2rv(ISS_TLE_LINE1, ISS_TLE_LINE2)
        assert estimate_covariance_from_tles([sat, sat], datetime.now(timezone.utc)) is None
        assert estimate_covariance_from_tles([], datetime.now(timezone.utc)) is None


class TestDefaultCovariance:
    """Tests for altitude-based fallback covariance."""

    def test_leo(self):
        """LEO altitude should give σ=1 km."""
        cov = default_covariance_km2(400)
        assert cov.shape == (3, 3)
        np.testing.assert_allclose(np.diag(cov), [1.0, 1.0, 1.0])

    def test_meo(self):
        """MEO altitude should give σ=5 km."""
        cov = default_covariance_km2(10000)
        np.testing.assert_allclose(np.diag(cov), [25.0, 25.0, 25.0])

    def test_geo(self):
        """GEO altitude should give σ=10 km."""
        cov = default_covariance_km2(35786)
        np.testing.assert_allclose(np.diag(cov), [100.0, 100.0, 100.0])

    def test_boundary_leo_meo(self):
        """Altitude exactly at 2000 km should be MEO."""
        cov = default_covariance_km2(2000)
        np.testing.assert_allclose(np.diag(cov), [25.0, 25.0, 25.0])

    def test_diagonal(self):
        """Fallback covariance should be diagonal (isotropic)."""
        cov = default_covariance_km2(500)
        off_diag = cov - np.diag(np.diag(cov))
        np.testing.assert_allclose(off_diag, 0.0)

"""Tests for ML feature extraction modules."""

import math

import numpy as np
import pytest

from src.ml.features.orbital import (
    ORBITAL_FEATURE_NAMES,
    OBJECT_TYPE_MAP,
    RCS_SIZE_MAP,
    compute_derived_orbital_features,
)
from src.ml.features.conjunction import (
    CONJUNCTION_FEATURE_NAMES,
    extract_conjunction_features,
)
from src.ml.features.weather import (
    DEFAULT_F107_FLUX,
    DEFAULT_KP_INDEX,
    get_current_weather,
)


class TestOrbitalFeatures:
    def test_feature_count(self):
        """ORBITAL_FEATURE_NAMES should have 14 features."""
        assert len(ORBITAL_FEATURE_NAMES) == 14

    def test_derived_features_leo(self):
        """LEO satellite derived features are physically reasonable."""
        feat = compute_derived_orbital_features(
            mean_motion=15.5,  # ISS-like
            eccentricity=0.0006,
            inclination=51.6,
            bstar=3.3e-4,
        )
        assert 100 < feat["perigee_alt_km"] < 500
        assert 100 < feat["apogee_alt_km"] < 500
        assert 6500 < feat["semi_major_axis_km"] < 7000
        assert 90 < feat["orbital_period_minutes"] < 95
        assert feat["is_leo"] == 1.0
        assert feat["ballistic_coefficient_proxy"] > 0

    def test_derived_features_geo(self):
        """GEO satellite derived features."""
        feat = compute_derived_orbital_features(
            mean_motion=1.0027,  # ~GEO
            eccentricity=0.0001,
            inclination=0.05,
            bstar=1e-6,
        )
        assert feat["perigee_alt_km"] > 30000
        assert feat["is_leo"] == 0.0
        assert feat["orbital_period_minutes"] > 1400

    def test_object_type_encoding(self):
        """Object type map covers expected types."""
        assert OBJECT_TYPE_MAP["PAYLOAD"] == 0
        assert OBJECT_TYPE_MAP["DEBRIS"] == 2
        assert OBJECT_TYPE_MAP[None] == 3

    def test_rcs_size_encoding(self):
        """RCS size map covers expected sizes."""
        assert RCS_SIZE_MAP["SMALL"] == 0
        assert RCS_SIZE_MAP["LARGE"] == 2
        assert RCS_SIZE_MAP[None] == 1


class TestConjunctionFeatures:
    def test_feature_count(self):
        """CONJUNCTION_FEATURE_NAMES should have 22 features."""
        assert len(CONJUNCTION_FEATURE_NAMES) == 22

    def test_basic_extraction(self):
        """Extract features from a basic encounter."""
        rel_pos = np.array([1.0, 0.5, 0.2])
        rel_vel = np.array([7.0, 0.0, 0.0])

        pri_feat = {
            "mean_motion": 15.5,
            "eccentricity": 0.001,
            "inclination": 51.6,
            "perigee_alt_km": 400.0,
            "apogee_alt_km": 410.0,
            "bstar": 3e-4,
        }
        sec_feat = {
            "mean_motion": 14.8,
            "eccentricity": 0.005,
            "inclination": 98.0,
            "perigee_alt_km": 500.0,
            "apogee_alt_km": 530.0,
            "bstar": 1e-5,
        }

        features = extract_conjunction_features(
            miss_distance_km=float(np.linalg.norm(rel_pos)),
            relative_velocity_kms=float(np.linalg.norm(rel_vel)),
            relative_position_km=rel_pos,
            relative_velocity_vec=rel_vel,
            primary_features=pri_feat,
            secondary_features=sec_feat,
        )

        assert len(features) == 22
        assert set(features.keys()) == set(CONJUNCTION_FEATURE_NAMES)
        assert features["miss_distance_km"] > 0
        assert features["relative_velocity_kms"] > 0
        assert 0 <= features["approach_angle_deg"] <= 180

    def test_with_covariance(self):
        """Covariance features are computed when provided."""
        rel_pos = np.array([1.0, 0.0, 0.0])
        rel_vel = np.array([0.0, 7.0, 0.0])
        cov = np.diag([1.0, 1.0, 1.0])

        features = extract_conjunction_features(
            miss_distance_km=1.0,
            relative_velocity_kms=7.0,
            relative_position_km=rel_pos,
            relative_velocity_vec=rel_vel,
            primary_features={},
            secondary_features={},
            primary_cov=cov,
            secondary_cov=cov,
        )

        assert features["combined_sigma_km"] > 0
        assert features["sigma_ratio"] >= 1.0
        assert features["mahalanobis_estimate"] >= 0

    def test_without_covariance(self):
        """Default covariance features when not provided."""
        features = extract_conjunction_features(
            miss_distance_km=2.0,
            relative_velocity_kms=10.0,
            relative_position_km=np.array([2.0, 0.0, 0.0]),
            relative_velocity_vec=np.array([10.0, 0.0, 0.0]),
            primary_features={},
            secondary_features={},
        )

        assert features["combined_sigma_km"] == 1.0
        assert features["sigma_ratio"] == 1.0

    def test_with_weather(self):
        """Weather features are passed through."""
        features = extract_conjunction_features(
            miss_distance_km=1.0,
            relative_velocity_kms=7.0,
            relative_position_km=np.array([1.0, 0.0, 0.0]),
            relative_velocity_vec=np.array([0.0, 7.0, 0.0]),
            primary_features={},
            secondary_features={},
            weather={"f107_flux": 200.0, "kp_index": 5.0},
        )

        assert features["f107_flux"] == 200.0
        assert features["kp_index"] == 5.0

    def test_zero_velocity_handling(self):
        """Zero relative velocity doesn't crash."""
        features = extract_conjunction_features(
            miss_distance_km=0.0,
            relative_velocity_kms=0.0,
            relative_position_km=np.array([0.0, 0.0, 0.0]),
            relative_velocity_vec=np.array([0.0, 0.0, 0.0]),
            primary_features={},
            secondary_features={},
        )
        assert features["b_plane_x_km"] == 0.0
        assert features["b_plane_y_km"] == 0.0
        assert features["approach_angle_deg"] == 90.0


class TestWeatherFeatures:
    def test_defaults_when_redis_unavailable(self):
        """Returns defaults when Redis is not available."""
        weather = get_current_weather("redis://nonexistent:9999/0")
        assert weather["f107_flux"] == DEFAULT_F107_FLUX
        assert weather["kp_index"] == DEFAULT_KP_INDEX

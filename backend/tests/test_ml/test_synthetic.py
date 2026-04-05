"""Tests for synthetic data generators."""

import numpy as np
import pandas as pd
import pytest

from src.ml.features.orbital import ORBITAL_FEATURE_NAMES
from src.ml.features.conjunction import CONJUNCTION_FEATURE_NAMES
from src.ml.training.synthetic import (
    generate_synthetic_orbital_features,
    generate_synthetic_covariance_targets,
    generate_synthetic_conjunctions,
)


class TestSyntheticOrbitalFeatures:
    def test_shape(self):
        """Output has correct shape and column names."""
        df = generate_synthetic_orbital_features(n_samples=100, seed=0)
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 100
        assert list(df.columns) == ORBITAL_FEATURE_NAMES

    def test_physical_constraints(self):
        """Generated features satisfy physical constraints."""
        df = generate_synthetic_orbital_features(n_samples=1000, seed=42)

        # Eccentricity in [0, 1)
        assert (df["eccentricity"] >= 0).all()
        assert (df["eccentricity"] < 1).all()

        # Inclination in [0, 180)
        assert (df["inclination"] >= 0).all()
        assert (df["inclination"] < 180).all()

        # Mean motion > 0
        assert (df["mean_motion"] > 0).all()

        # Perigee <= apogee
        assert (df["perigee_alt_km"] <= df["apogee_alt_km"] + 1).all()

        # Semi-major axis > R_earth
        assert (df["semi_major_axis_km"] > 6300).all()

        # is_leo is binary
        assert set(df["is_leo"].unique()).issubset({0.0, 1.0})

    def test_regime_mix(self):
        """Approximately 70% LEO, 15% MEO, 15% GEO."""
        df = generate_synthetic_orbital_features(n_samples=10000, seed=42)
        leo_frac = (df["perigee_alt_km"] < 2000).mean()
        assert 0.65 < leo_frac < 0.75

    def test_reproducibility(self):
        """Same seed produces same data."""
        df1 = generate_synthetic_orbital_features(n_samples=50, seed=99)
        df2 = generate_synthetic_orbital_features(n_samples=50, seed=99)
        pd.testing.assert_frame_equal(df1, df2)

    def test_no_nan(self):
        """No NaN values in output."""
        df = generate_synthetic_orbital_features(n_samples=500, seed=42)
        assert not df.isna().any().any()


class TestSyntheticCovarianceTargets:
    def test_shape(self):
        """Output shape matches input."""
        features = generate_synthetic_orbital_features(n_samples=100, seed=42)
        targets = generate_synthetic_covariance_targets(features, seed=42)
        assert len(targets) == 100

    def test_reasonable_range(self):
        """log10(sigma) should be roughly in [-1, 2]."""
        features = generate_synthetic_orbital_features(n_samples=1000, seed=42)
        targets = generate_synthetic_covariance_targets(features, seed=42)
        # Most values between -1 and 2 (0.1 km to 100 km sigma)
        assert np.percentile(targets, 5) > -2
        assert np.percentile(targets, 95) < 3

    def test_altitude_correlation(self):
        """Higher altitude should correlate with larger sigma."""
        features = generate_synthetic_orbital_features(n_samples=5000, seed=42)
        targets = generate_synthetic_covariance_targets(features, seed=42)

        leo_mask = features["perigee_alt_km"] < 2000
        geo_mask = features["perigee_alt_km"] > 30000

        leo_mean = targets[leo_mask.values].mean()
        geo_mean = targets[geo_mask.values].mean()
        assert geo_mean > leo_mean


class TestSyntheticConjunctions:
    def test_shape(self):
        """Output has correct shape."""
        df = generate_synthetic_conjunctions(n_events=200, seed=42)
        assert len(df) == 200
        for col in CONJUNCTION_FEATURE_NAMES:
            assert col in df.columns
        assert "label" in df.columns

    def test_label_distribution(self):
        """Roughly 2-10% positive labels."""
        df = generate_synthetic_conjunctions(n_events=10000, seed=42)
        pos_rate = df["label"].mean()
        assert 0.01 < pos_rate < 0.15

    def test_both_classes_present(self):
        """Both classes present."""
        df = generate_synthetic_conjunctions(n_events=5000, seed=42)
        assert set(df["label"].unique()) == {0, 1}

    def test_no_nan(self):
        """No NaN values."""
        df = generate_synthetic_conjunctions(n_events=500, seed=42)
        assert not df.isna().any().any()

    def test_positive_values(self):
        """Miss distance and velocity are positive."""
        df = generate_synthetic_conjunctions(n_events=500, seed=42)
        assert (df["miss_distance_km"] > 0).all()
        assert (df["relative_velocity_kms"] > 0).all()

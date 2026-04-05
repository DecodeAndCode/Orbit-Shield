"""Tests for Covariance Estimator model."""

import numpy as np
import pytest

from src.ml.models.covariance import CovarianceEstimator
from src.ml.features.orbital import ORBITAL_FEATURE_NAMES
from src.ml.training.synthetic import (
    generate_synthetic_orbital_features,
    generate_synthetic_covariance_targets,
)


@pytest.fixture
def trained_model():
    """Train a covariance model on synthetic data."""
    features = generate_synthetic_orbital_features(n_samples=500, seed=42)
    targets = generate_synthetic_covariance_targets(features, seed=42)

    model = CovarianceEstimator()
    model.train(features.values, targets)
    return model


class TestCovarianceEstimator:
    def test_properties(self):
        """Model has correct name, version, features."""
        model = CovarianceEstimator()
        assert model.name == "covariance_estimator"
        assert model.version == "1.0.0"
        assert model.feature_names == ORBITAL_FEATURE_NAMES
        assert len(model.feature_names) == 14

    def test_train_returns_metrics(self):
        """Training returns RMSE and R² metrics."""
        features = generate_synthetic_orbital_features(n_samples=300, seed=42)
        targets = generate_synthetic_covariance_targets(features, seed=42)

        model = CovarianceEstimator()
        metrics = model.train(features.values, targets)

        assert "rmse" in metrics
        assert "r2" in metrics
        assert metrics["rmse"] > 0
        assert metrics["rmse"] < 2.0  # Should learn something

    def test_predict_shape(self, trained_model):
        """Predictions have correct shape."""
        features = generate_synthetic_orbital_features(n_samples=10, seed=99)
        results = trained_model.predict(features.values)

        assert len(results) == 10
        for r in results:
            assert r.model_name == "covariance_estimator"
            assert isinstance(r.value, float)

    def test_predict_covariance_returns_3x3(self, trained_model):
        """predict_covariance returns a 3x3 diagonal matrix."""
        features = generate_synthetic_orbital_features(n_samples=1, seed=99)
        cov = trained_model.predict_covariance(features.values[0])

        assert cov.shape == (3, 3)
        # Should be diagonal and positive
        assert cov[0, 1] == 0.0
        assert cov[0, 0] > 0
        # All diagonal elements equal (isotropic)
        np.testing.assert_allclose(cov[0, 0], cov[1, 1])
        np.testing.assert_allclose(cov[0, 0], cov[2, 2])

    def test_predict_covariance_2d_input(self, trained_model):
        """predict_covariance works with 2D input."""
        features = generate_synthetic_orbital_features(n_samples=1, seed=99)
        cov = trained_model.predict_covariance(features.values)
        assert cov.shape == (3, 3)

    def test_leo_vs_geo_sigma(self, trained_model):
        """LEO predictions should have smaller sigma than GEO."""
        leo_features = generate_synthetic_orbital_features(n_samples=200, seed=1)
        geo_features = generate_synthetic_orbital_features(n_samples=200, seed=2)

        # Filter to LEO and GEO
        leo = leo_features[leo_features["perigee_alt_km"] < 2000].head(20)
        geo = geo_features[geo_features["perigee_alt_km"] > 30000].head(20)

        if len(leo) > 0 and len(geo) > 0:
            leo_preds = trained_model.predict(leo.values)
            geo_preds = trained_model.predict(geo.values)

            leo_mean = np.mean([r.value for r in leo_preds])
            geo_mean = np.mean([r.value for r in geo_preds])
            # GEO sigma should generally be larger
            assert geo_mean > leo_mean

    def test_get_model(self, trained_model):
        """get_model returns the underlying XGBRegressor."""
        from xgboost import XGBRegressor

        model = trained_model.get_model()
        assert isinstance(model, XGBRegressor)

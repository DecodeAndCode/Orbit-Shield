"""Tests for ML inference engine."""

import numpy as np
import pytest

from src.ml.config import ml_settings
from src.ml.features.conjunction import CONJUNCTION_FEATURE_NAMES
from src.ml.features.orbital import ORBITAL_FEATURE_NAMES
from src.ml.inference import MLInferenceEngine
from src.ml.models.covariance import CovarianceEstimator
from src.ml.models.conjunction_risk import ConjunctionRiskClassifier
from src.ml.registry import ModelRegistry
from src.ml.training.synthetic import (
    generate_synthetic_conjunctions,
    generate_synthetic_covariance_targets,
    generate_synthetic_orbital_features,
)


@pytest.fixture
def model_dir(tmp_path):
    """Temporary model directory."""
    return tmp_path


@pytest.fixture
def registry_with_models(model_dir):
    """Registry with trained models saved."""
    registry = ModelRegistry(model_dir=model_dir)

    # Train and save covariance model
    features = generate_synthetic_orbital_features(n_samples=300, seed=42)
    targets = generate_synthetic_covariance_targets(features, seed=42)
    cov_model = CovarianceEstimator()
    cov_model.train(features.values, targets)
    registry.save_model(cov_model.get_model(), ml_settings.covariance_model_name)

    # Train and save conjunction risk model
    df = generate_synthetic_conjunctions(n_events=1000, seed=42)
    X = df[CONJUNCTION_FEATURE_NAMES].values
    y = df["label"].values
    risk_model = ConjunctionRiskClassifier()
    risk_model.train(X, y)
    registry.save_model(risk_model.get_model(), ml_settings.conjunction_risk_model_name)

    return registry


class TestMLInferenceEngine:
    def test_initialize_no_models(self, model_dir, monkeypatch):
        """Engine initializes gracefully with no saved models."""
        monkeypatch.setattr(ml_settings, "model_dir", model_dir)
        engine = MLInferenceEngine()
        engine.initialize()

        assert not engine.is_available
        assert not engine.has_covariance_model
        assert not engine.has_conjunction_risk_model

    def test_initialize_with_models(self, model_dir, registry_with_models, monkeypatch):
        """Engine loads both models when available."""
        monkeypatch.setattr(ml_settings, "model_dir", model_dir)
        engine = MLInferenceEngine()
        engine.initialize()

        assert engine.is_available
        assert engine.has_covariance_model
        assert engine.has_conjunction_risk_model

    def test_predict_covariance(self, model_dir, registry_with_models, monkeypatch):
        """Covariance prediction returns valid 3x3 matrix."""
        monkeypatch.setattr(ml_settings, "model_dir", model_dir)
        engine = MLInferenceEngine()
        engine.initialize()

        features = {name: 0.0 for name in ORBITAL_FEATURE_NAMES}
        features["mean_motion"] = 15.5
        features["eccentricity"] = 0.001
        features["inclination"] = 51.6
        features["perigee_alt_km"] = 400.0
        features["apogee_alt_km"] = 410.0
        features["semi_major_axis_km"] = 6778.0
        features["orbital_period_minutes"] = 92.0
        features["is_leo"] = 1.0

        result = engine.predict_covariance(features)
        assert result is not None
        cov, source = result
        assert cov.shape == (3, 3)
        assert source == "ml_covariance"
        assert cov[0, 0] > 0

    def test_predict_covariance_no_model(self, model_dir, monkeypatch):
        """Returns None when covariance model not loaded."""
        monkeypatch.setattr(ml_settings, "model_dir", model_dir)
        engine = MLInferenceEngine()
        engine.initialize()

        features = {name: 0.0 for name in ORBITAL_FEATURE_NAMES}
        result = engine.predict_covariance(features)
        assert result is None

    def test_predict_conjunction_risk(self, model_dir, registry_with_models, monkeypatch):
        """Conjunction risk prediction returns probability."""
        monkeypatch.setattr(ml_settings, "model_dir", model_dir)
        engine = MLInferenceEngine()
        engine.initialize()

        features = {name: 0.0 for name in CONJUNCTION_FEATURE_NAMES}
        features["miss_distance_km"] = 1.0
        features["relative_velocity_kms"] = 7.0
        features["combined_sigma_km"] = 1.0
        features["sigma_ratio"] = 1.0
        features["mahalanobis_estimate"] = 1.0

        prob = engine.predict_conjunction_risk(features)
        assert prob is not None
        assert 0.0 <= prob <= 1.0

    def test_predict_conjunction_risk_no_model(self, model_dir, monkeypatch):
        """Returns None when risk model not loaded."""
        monkeypatch.setattr(ml_settings, "model_dir", model_dir)
        engine = MLInferenceEngine()
        engine.initialize()

        features = {name: 0.0 for name in CONJUNCTION_FEATURE_NAMES}
        result = engine.predict_conjunction_risk(features)
        assert result is None

    def test_inference_disabled(self, model_dir, registry_with_models, monkeypatch):
        """Models not loaded when inference is disabled."""
        monkeypatch.setattr(ml_settings, "model_dir", model_dir)
        monkeypatch.setattr(ml_settings, "ml_inference_enabled", False)
        engine = MLInferenceEngine()
        engine.initialize()

        assert not engine.is_available

"""Tests for Conjunction Risk Classifier model."""

import numpy as np
import pytest

from src.ml.models.conjunction_risk import ConjunctionRiskClassifier
from src.ml.features.conjunction import CONJUNCTION_FEATURE_NAMES
from src.ml.training.synthetic import generate_synthetic_conjunctions


@pytest.fixture
def trained_model():
    """Train a conjunction risk model on synthetic data."""
    df = generate_synthetic_conjunctions(n_events=2000, seed=42)
    X = df[CONJUNCTION_FEATURE_NAMES].values
    y = df["label"].values

    model = ConjunctionRiskClassifier()
    model.train(X, y)
    return model


class TestConjunctionRiskClassifier:
    def test_properties(self):
        """Model has correct name, version, features."""
        model = ConjunctionRiskClassifier()
        assert model.name == "conjunction_risk_classifier"
        assert model.version == "1.0.0"
        assert model.feature_names == CONJUNCTION_FEATURE_NAMES
        assert len(model.feature_names) == 22

    def test_train_returns_metrics(self):
        """Training returns classification metrics."""
        df = generate_synthetic_conjunctions(n_events=1000, seed=42)
        X = df[CONJUNCTION_FEATURE_NAMES].values
        y = df["label"].values

        model = ConjunctionRiskClassifier()
        metrics = model.train(X, y)

        assert "accuracy" in metrics
        assert "precision" in metrics
        assert "recall" in metrics
        assert "f1" in metrics
        assert metrics["accuracy"] > 0.5  # Better than random

    def test_predict_shape(self, trained_model):
        """Predictions have correct shape."""
        df = generate_synthetic_conjunctions(n_events=10, seed=99)
        X = df[CONJUNCTION_FEATURE_NAMES].values

        results = trained_model.predict(X)
        assert len(results) == 10
        for r in results:
            assert r.model_name == "conjunction_risk_classifier"
            assert 0.0 <= r.value <= 1.0
            assert 0.5 <= r.confidence <= 1.0

    def test_probabilities_sum_correctly(self, trained_model):
        """Predicted probabilities are valid."""
        df = generate_synthetic_conjunctions(n_events=50, seed=99)
        X = df[CONJUNCTION_FEATURE_NAMES].values

        results = trained_model.predict(X)
        for r in results:
            # Value is probability of class 1
            assert 0.0 <= r.value <= 1.0

    def test_high_risk_detection(self, trained_model):
        """Model assigns higher risk to close, fast approaches."""
        # Create a clearly dangerous encounter
        dangerous = np.zeros((1, 22))
        dangerous[0, 0] = 0.05  # Very small miss distance
        dangerous[0, 1] = 14.0  # High relative velocity
        dangerous[0, 17] = 0.1  # Small combined sigma
        dangerous[0, 18] = 1.0  # Low sigma ratio
        dangerous[0, 19] = 0.5  # Low mahalanobis

        # Create a clearly safe encounter
        safe = np.zeros((1, 22))
        safe[0, 0] = 4.0  # Large miss distance
        safe[0, 1] = 1.0  # Low relative velocity
        safe[0, 17] = 5.0  # Large combined sigma
        safe[0, 18] = 1.0  # Low sigma ratio
        safe[0, 19] = 10.0  # High mahalanobis

        dangerous_risk = trained_model.predict(dangerous)[0].value
        safe_risk = trained_model.predict(safe)[0].value

        # Dangerous should have higher risk
        assert dangerous_risk > safe_risk

    def test_get_model(self, trained_model):
        """get_model returns the underlying XGBClassifier."""
        from xgboost import XGBClassifier

        model = trained_model.get_model()
        assert isinstance(model, XGBClassifier)

    def test_scale_pos_weight(self):
        """Custom scale_pos_weight is respected."""
        model = ConjunctionRiskClassifier(scale_pos_weight=50.0)
        assert model.get_model().get_params()["scale_pos_weight"] == 50.0

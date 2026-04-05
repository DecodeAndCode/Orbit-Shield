"""Base model interface and prediction result dataclass."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

import numpy as np


@dataclass
class PredictionResult:
    """Result from an ML model prediction."""

    value: float
    confidence: float
    model_name: str
    model_version: str


class ColliderModel(ABC):
    """Abstract base class for all Collider ML models."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Model name identifier."""

    @property
    @abstractmethod
    def version(self) -> str:
        """Model version string."""

    @property
    @abstractmethod
    def feature_names(self) -> list[str]:
        """Ordered list of feature names expected by the model."""

    @abstractmethod
    def predict(self, features: np.ndarray) -> list[PredictionResult]:
        """Run inference on feature array.

        Args:
            features: 2D array of shape (n_samples, n_features).

        Returns:
            List of PredictionResult, one per sample.
        """

    @abstractmethod
    def train(self, X: np.ndarray, y: np.ndarray) -> dict[str, float]:
        """Train the model on labeled data.

        Args:
            X: Feature matrix (n_samples, n_features).
            y: Target array (n_samples,).

        Returns:
            Dict of training metrics (e.g. rmse, accuracy).
        """

    @abstractmethod
    def get_model(self) -> Any:
        """Return the underlying sklearn/xgboost model object."""

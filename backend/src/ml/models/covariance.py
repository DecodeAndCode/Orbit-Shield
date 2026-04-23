"""Covariance Estimator model.

Predicts log10(sigma_km) from orbital metadata features.
Replaces altitude-based default_covariance_km2() with object-specific
predictions when a trained model is available.
"""

from __future__ import annotations

import logging

import numpy as np
from xgboost import XGBRegressor

from src.ml.models.base import OrbitShieldModel, PredictionResult
from src.ml.features.orbital import ORBITAL_FEATURE_NAMES

logger = logging.getLogger(__name__)

MODEL_NAME = "covariance_estimator"
MODEL_VERSION = "1.0.0"


class CovarianceEstimator(OrbitShieldModel):
    """XGBoost regressor predicting log10(position uncertainty in km)."""

    def __init__(self) -> None:
        self._model = XGBRegressor(
            n_estimators=200,
            max_depth=6,
            learning_rate=0.1,
            subsample=0.8,
            colsample_bytree=0.8,
            random_state=42,
        )
        self._is_trained = False

    @property
    def name(self) -> str:
        return MODEL_NAME

    @property
    def version(self) -> str:
        return MODEL_VERSION

    @property
    def feature_names(self) -> list[str]:
        return ORBITAL_FEATURE_NAMES

    def predict(self, features: np.ndarray) -> list[PredictionResult]:
        """Predict log10(sigma_km) for each sample.

        Args:
            features: (n_samples, 14) array of orbital features.

        Returns:
            List of PredictionResult with value=log10(sigma_km).
        """
        predictions = self._model.predict(features)
        results = []
        for pred in predictions:
            results.append(
                PredictionResult(
                    value=float(pred),
                    confidence=1.0,
                    model_name=self.name,
                    model_version=self.version,
                )
            )
        return results

    def predict_covariance(self, features: np.ndarray) -> np.ndarray:
        """Predict a 3x3 isotropic covariance matrix.

        Args:
            features: (1, 14) or (14,) array of orbital features.

        Returns:
            3x3 covariance matrix diag([sigma^2, sigma^2, sigma^2]).
        """
        if features.ndim == 1:
            features = features.reshape(1, -1)

        result = self.predict(features)[0]
        sigma_km = 10.0 ** result.value
        sigma_km2 = sigma_km ** 2
        return np.diag([sigma_km2, sigma_km2, sigma_km2])

    def train(self, X: np.ndarray, y: np.ndarray) -> dict[str, float]:
        """Train the XGBRegressor on (features, log10(sigma_km)) pairs.

        Args:
            X: Feature matrix (n_samples, 14).
            y: Target array of log10(sigma_km) values.

        Returns:
            Training metrics dict with rmse and r2.
        """
        from sklearn.model_selection import train_test_split
        from sklearn.metrics import mean_squared_error, r2_score

        X_train, X_val, y_train, y_val = train_test_split(
            X, y, test_size=0.2, random_state=42
        )

        self._model.fit(
            X_train,
            y_train,
            eval_set=[(X_val, y_val)],
            verbose=False,
        )

        y_pred = self._model.predict(X_val)
        rmse = float(np.sqrt(mean_squared_error(y_val, y_pred)))
        r2 = float(r2_score(y_val, y_pred))

        self._is_trained = True
        logger.info("Covariance model trained: RMSE=%.4f, R²=%.4f", rmse, r2)

        return {"rmse": rmse, "r2": r2}

    def get_model(self) -> XGBRegressor:
        return self._model

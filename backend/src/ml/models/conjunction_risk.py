"""Conjunction Risk Classifier model.

Predicts P(Pc > 1e-4) from encounter geometry and orbital features.
Output probability is stored as pc_ml in the conjunctions table.
"""

from __future__ import annotations

import logging

import numpy as np
from xgboost import XGBClassifier

from src.ml.models.base import ColliderModel, PredictionResult
from src.ml.features.conjunction import CONJUNCTION_FEATURE_NAMES

logger = logging.getLogger(__name__)

MODEL_NAME = "conjunction_risk_classifier"
MODEL_VERSION = "1.0.0"


class ConjunctionRiskClassifier(ColliderModel):
    """XGBoost classifier predicting P(Pc > maneuver threshold)."""

    def __init__(self, scale_pos_weight: float = 100.0) -> None:
        self._model = XGBClassifier(
            n_estimators=300,
            max_depth=6,
            learning_rate=0.05,
            subsample=0.8,
            colsample_bytree=0.8,
            scale_pos_weight=scale_pos_weight,
            eval_metric="logloss",
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
        return CONJUNCTION_FEATURE_NAMES

    def predict(self, features: np.ndarray) -> list[PredictionResult]:
        """Predict risk probability for each sample.

        Args:
            features: (n_samples, 22) array of conjunction features.

        Returns:
            List of PredictionResult with value=P(Pc > 1e-4).
        """
        probas = self._model.predict_proba(features)[:, 1]
        results = []
        for prob in probas:
            results.append(
                PredictionResult(
                    value=float(prob),
                    confidence=float(max(prob, 1.0 - prob)),
                    model_name=self.name,
                    model_version=self.version,
                )
            )
        return results

    def train(self, X: np.ndarray, y: np.ndarray) -> dict[str, float]:
        """Train the XGBClassifier on (features, label) pairs.

        Args:
            X: Feature matrix (n_samples, 22).
            y: Binary labels (1 = Pc > 1e-4, 0 = low risk).

        Returns:
            Training metrics dict with accuracy, precision, recall, f1, auc.
        """
        from sklearn.metrics import (
            accuracy_score,
            f1_score,
            precision_score,
            recall_score,
            roc_auc_score,
        )
        from sklearn.model_selection import train_test_split

        X_train, X_val, y_train, y_val = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y
        )

        self._model.fit(
            X_train,
            y_train,
            eval_set=[(X_val, y_val)],
            verbose=False,
        )

        y_pred = self._model.predict(X_val)
        y_proba = self._model.predict_proba(X_val)[:, 1]

        metrics = {
            "accuracy": float(accuracy_score(y_val, y_pred)),
            "precision": float(precision_score(y_val, y_pred, zero_division=0)),
            "recall": float(recall_score(y_val, y_pred, zero_division=0)),
            "f1": float(f1_score(y_val, y_pred, zero_division=0)),
        }

        # AUC requires both classes in validation set
        if len(set(y_val)) > 1:
            metrics["auc"] = float(roc_auc_score(y_val, y_proba))

        self._is_trained = True
        logger.info(
            "Conjunction risk model trained: AUC=%.4f, F1=%.4f",
            metrics.get("auc", 0),
            metrics["f1"],
        )

        return metrics

    def get_model(self) -> XGBClassifier:
        return self._model

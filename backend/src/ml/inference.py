"""ML inference engine for the screening pipeline.

Orchestrates model loading and prediction, with graceful degradation
when models are unavailable.
"""

from __future__ import annotations

import logging

import numpy as np

from src.ml import ML_AVAILABLE
from src.ml.config import ml_settings
from src.ml.features.conjunction import CONJUNCTION_FEATURE_NAMES
from src.ml.features.orbital import ORBITAL_FEATURE_NAMES

logger = logging.getLogger(__name__)


class MLInferenceEngine:
    """Manages ML model lifecycle and runs inference in the screening pipeline.

    Loads models from the registry on initialize(). All predictions return None
    when the corresponding model is not loaded, ensuring zero impact on the
    classical pipeline.
    """

    def __init__(self) -> None:
        self._covariance_model = None
        self._conjunction_risk_model = None
        self._initialized = False

    def initialize(self) -> None:
        """Load trained models from the registry.

        Logs which models are available. Never raises — failures are logged
        and the corresponding model stays None.
        """
        if not ML_AVAILABLE:
            logger.info("ML dependencies not installed, inference disabled")
            self._initialized = True
            return

        if not ml_settings.ml_inference_enabled:
            logger.info("ML inference disabled via ML_INFERENCE_ENABLED=false")
            self._initialized = True
            return

        from src.ml.registry import ModelRegistry

        registry = ModelRegistry()

        # Load covariance model
        try:
            self._covariance_model = registry.load_model(
                ml_settings.covariance_model_name
            )
            logger.info("Loaded covariance model: %s", ml_settings.covariance_model_name)
        except FileNotFoundError:
            logger.info("Covariance model not found, ML covariance disabled")

        # Load conjunction risk model
        try:
            self._conjunction_risk_model = registry.load_model(
                ml_settings.conjunction_risk_model_name
            )
            logger.info(
                "Loaded conjunction risk model: %s",
                ml_settings.conjunction_risk_model_name,
            )
        except FileNotFoundError:
            logger.info("Conjunction risk model not found, ML risk disabled")

        self._initialized = True

    @property
    def is_available(self) -> bool:
        """True if at least one model is loaded."""
        return self._covariance_model is not None or self._conjunction_risk_model is not None

    @property
    def has_covariance_model(self) -> bool:
        return self._covariance_model is not None

    @property
    def has_conjunction_risk_model(self) -> bool:
        return self._conjunction_risk_model is not None

    def predict_covariance(
        self,
        features: dict[str, float],
    ) -> tuple[np.ndarray, str] | None:
        """Predict a 3x3 position covariance from orbital features.

        Args:
            features: Dict with keys matching ORBITAL_FEATURE_NAMES.

        Returns:
            (3x3 covariance matrix, "ml_covariance") or None if model unavailable.
        """
        if self._covariance_model is None:
            return None

        try:
            feature_vec = np.array(
                [features[name] for name in ORBITAL_FEATURE_NAMES],
                dtype=np.float64,
            ).reshape(1, -1)

            log_sigma = float(self._covariance_model.predict(feature_vec)[0])
            sigma_km = 10.0 ** log_sigma
            sigma_km2 = sigma_km ** 2

            return np.diag([sigma_km2, sigma_km2, sigma_km2]), "ml_covariance"
        except Exception:
            logger.debug("ML covariance prediction failed", exc_info=True)
            return None

    def predict_conjunction_risk(
        self,
        features: dict[str, float],
    ) -> float | None:
        """Predict P(Pc > 1e-4) from conjunction features.

        Args:
            features: Dict with keys matching CONJUNCTION_FEATURE_NAMES.

        Returns:
            Probability float (for pc_ml column), or None if model unavailable.
        """
        if self._conjunction_risk_model is None:
            return None

        try:
            feature_vec = np.array(
                [features[name] for name in CONJUNCTION_FEATURE_NAMES],
                dtype=np.float64,
            ).reshape(1, -1)

            proba = self._conjunction_risk_model.predict_proba(feature_vec)[0, 1]
            return float(proba)
        except Exception:
            logger.debug("ML conjunction risk prediction failed", exc_info=True)
            return None

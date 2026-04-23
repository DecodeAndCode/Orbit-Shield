"""Training script for the Conjunction Risk Classifier model.

Can train from:
1. Real conjunction data in the database (when enough events exist with pc_classical)
2. Synthetic data as fallback

Usage:
    python -m src.ml.training.train_conjunction
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from src.config import settings
from src.ml.config import ml_settings
from src.ml.features.conjunction import CONJUNCTION_FEATURE_NAMES
from src.ml.models.conjunction_risk import ConjunctionRiskClassifier
from src.ml.registry import ModelRegistry
from src.ml.training.from_cdms import build_training_set
from src.ml.training.synthetic import generate_synthetic_conjunctions

logger = logging.getLogger(__name__)

MIN_CDMS_FOR_DB_TRAINING = 100


def generate_training_data_from_db(
    session: Session,
) -> tuple[np.ndarray, np.ndarray] | None:
    """Build (X, y) from real CDM history in the database.

    Returns None when fewer than MIN_CDMS_FOR_DB_TRAINING usable rows exist;
    caller then falls back to synthetic data.
    """
    from src.db.models import CDMHistory

    total = session.execute(
        select(CDMHistory).where(CDMHistory.pc.is_not(None))
    ).scalars().all()

    if len(total) < MIN_CDMS_FOR_DB_TRAINING:
        logger.info(
            "Only %d labeled CDMs in DB (need %d), falling back to synthetic",
            len(total),
            MIN_CDMS_FOR_DB_TRAINING,
        )
        return None

    try:
        return build_training_set(session)
    except RuntimeError as exc:
        logger.warning("CDM training set build failed: %s", exc)
        return None


def train_conjunction_model(
    X: np.ndarray,
    y: np.ndarray,
) -> dict[str, float]:
    """Train and save the conjunction risk classifier.

    Args:
        X: Feature matrix (n_samples, 22).
        y: Binary labels.

    Returns:
        Training metrics dict.
    """
    # Compute class imbalance for scale_pos_weight
    n_pos = int(y.sum())
    n_neg = len(y) - n_pos
    scale_pos_weight = n_neg / n_pos if n_pos > 0 else 100.0

    model = ConjunctionRiskClassifier(scale_pos_weight=scale_pos_weight)
    metrics = model.train(X, y)

    registry = ModelRegistry()
    registry.save_model(
        model.get_model(),
        ml_settings.conjunction_risk_model_name,
        metadata={
            "name": model.name,
            "version": model.version,
            "feature_names": model.feature_names,
            "metrics": metrics,
            "n_samples": len(y),
            "n_positive": n_pos,
            "n_negative": n_neg,
        },
    )

    return metrics


def main() -> None:
    """CLI entry point for training the conjunction risk model."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    # Try DB first
    engine = create_engine(settings.database_url_sync)
    session = Session(engine)

    try:
        result = generate_training_data_from_db(session)
    finally:
        session.close()

    if result is not None:
        X, y = result
        logger.info("Training on %d DB samples", len(y))
    else:
        logger.info("Generating synthetic training data")
        df = generate_synthetic_conjunctions(n_events=10000)
        feature_cols = CONJUNCTION_FEATURE_NAMES
        X = df[feature_cols].values
        y = df["label"].values

    metrics = train_conjunction_model(X, y)
    logger.info("Training complete: %s", metrics)


if __name__ == "__main__":
    main()

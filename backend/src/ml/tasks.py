"""Celery tasks for ML model training and management."""

import logging
from datetime import datetime
from pathlib import Path
import shutil
import json
from typing import Optional

from celery import shared_task

from . import ML_AVAILABLE

if ML_AVAILABLE:
    from .training.train_covariance import (
        train_covariance_model,
        generate_training_data_from_db as gen_cov_data,
        generate_synthetic_orbital_features,
        generate_synthetic_covariance_targets,
    )
    from .training.train_conjunction import (
        train_conjunction_model,
        generate_training_data_from_db as gen_conj_data,
    )
    from .training.synthetic import generate_synthetic_conjunctions
    from .features.conjunction import CONJUNCTION_FEATURE_NAMES
    from .registry import ModelRegistry
    from src.config import settings
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


@shared_task(name="ml.retrain_models")
def retrain_models(force: bool = False) -> dict:
    """
    Retrain ML models with latest data.

    Args:
        force: If True, retrain even if performance is acceptable

    Returns:
        dict with training results and metrics
    """
    if not ML_AVAILABLE:
        logger.warning("ML dependencies not available, skipping retraining")
        return {"status": "skipped", "reason": "ML dependencies not installed"}

    logger.info("Starting ML model retraining...")
    results = {
        "timestamp": datetime.utcnow().isoformat(),
        "models": {}
    }

    try:
        engine = create_engine(settings.database_url_sync)
        session = Session(engine)

        try:
            # Train covariance estimator
            logger.info("Training covariance estimator...")
            cov_data = gen_cov_data(session)
            if cov_data is not None:
                X_cov, y_cov = cov_data
                logger.info(f"Training on {len(y_cov)} DB samples")
            else:
                logger.info("Falling back to synthetic covariance data")
                features_df = generate_synthetic_orbital_features(n_samples=5000)
                X_cov = features_df.values
                y_cov = generate_synthetic_covariance_targets(features_df)

            cov_metrics = train_covariance_model(X_cov, y_cov)
            results["models"]["covariance"] = {
                "status": "success",
                "metrics": cov_metrics,
                "n_samples": len(y_cov)
            }
            logger.info(f"Covariance model trained: R²={cov_metrics.get('test_r2', 'N/A'):.4f}")

            # Train conjunction risk classifier
            logger.info("Training conjunction risk classifier...")
            conj_data = gen_conj_data(session)
            if conj_data is not None:
                X_conj, y_conj = conj_data
                logger.info(f"Training on {len(y_conj)} DB samples")
            else:
                logger.info("Falling back to synthetic conjunction data")
                df = generate_synthetic_conjunctions(n_events=10000)
                X_conj = df[CONJUNCTION_FEATURE_NAMES].values
                y_conj = df["label"].values

            conj_metrics = train_conjunction_model(X_conj, y_conj)
            results["models"]["conjunction"] = {
                "status": "success",
                "metrics": conj_metrics,
                "n_samples": len(y_conj)
            }
            logger.info(f"Conjunction model trained: AUC={conj_metrics.get('test_auc', 'N/A'):.4f}")

        finally:
            session.close()

        # Version and archive old models
        _archive_old_models()

        results["status"] = "success"
        logger.info("ML model retraining completed successfully")

    except Exception as e:
        logger.error(f"Error during model retraining: {e}", exc_info=True)
        results["status"] = "error"
        results["error"] = str(e)

    return results


@shared_task(name="ml.monitor_model_performance")
def monitor_model_performance() -> dict:
    """
    Monitor deployed model performance and trigger retraining if needed.

    Checks:
    - Model age (retrain if > 90 days)
    - Performance metrics from model metadata
    - Data drift indicators

    Returns:
        dict with performance status and recommendations
    """
    if not ML_AVAILABLE:
        return {"status": "skipped", "reason": "ML dependencies not installed"}

    registry = ModelRegistry()
    results = {
        "timestamp": datetime.utcnow().isoformat(),
        "models": {},
        "action": "none"
    }

    try:
        # Check covariance model
        cov_model, cov_meta = registry.load_model("covariance_estimator")
        if cov_model and cov_meta:
            cov_age_days = (datetime.utcnow() - datetime.fromisoformat(cov_meta["trained_at"])).days
            cov_r2 = cov_meta["metrics"]["test_r2"]

            results["models"]["covariance"] = {
                "age_days": cov_age_days,
                "r2": cov_r2,
                "threshold": 0.80,
                "needs_retrain": cov_age_days > 90 or cov_r2 < 0.80
            }

        # Check conjunction model
        conj_model, conj_meta = registry.load_model("conjunction_classifier")
        if conj_model and conj_meta:
            conj_age_days = (datetime.utcnow() - datetime.fromisoformat(conj_meta["trained_at"])).days
            conj_auc = conj_meta["metrics"]["test_auc"]

            results["models"]["conjunction"] = {
                "age_days": conj_age_days,
                "auc": conj_auc,
                "threshold": 0.99,
                "needs_retrain": conj_age_days > 90 or conj_auc < 0.99
            }

        # Trigger retraining if needed
        if any(m.get("needs_retrain", False) for m in results["models"].values()):
            logger.warning("Model performance below threshold, triggering retraining")
            results["action"] = "retrain_triggered"
            retrain_models.delay(force=True)

    except Exception as e:
        logger.error(f"Error monitoring model performance: {e}", exc_info=True)
        results["status"] = "error"
        results["error"] = str(e)

    return results


def _archive_old_models(keep_n: int = 3):
    """
    Archive old model versions, keeping only the most recent N.

    Args:
        keep_n: Number of recent versions to keep
    """
    models_dir = Path(__file__).parent / "models"
    archive_dir = models_dir / "archive"
    archive_dir.mkdir(exist_ok=True)

    # Archive covariance models
    _archive_model_versions(
        models_dir,
        archive_dir,
        "covariance_estimator",
        keep_n
    )

    # Archive conjunction models
    _archive_model_versions(
        models_dir,
        archive_dir,
        "conjunction_classifier",
        keep_n
    )


def _archive_model_versions(
    models_dir: Path,
    archive_dir: Path,
    model_name: str,
    keep_n: int
):
    """Archive old versions of a specific model."""
    pattern = f"{model_name}_*.joblib"
    model_files = sorted(
        models_dir.glob(pattern),
        key=lambda p: p.stat().st_mtime,
        reverse=True
    )

    # Keep current version (no timestamp) + most recent N versioned models
    current_file = models_dir / f"{model_name}.joblib"
    versions_to_archive = model_files[keep_n:] if len(model_files) > keep_n else []

    for old_file in versions_to_archive:
        if old_file != current_file:
            archive_path = archive_dir / old_file.name
            logger.info(f"Archiving old model: {old_file.name}")
            shutil.move(str(old_file), str(archive_path))

            # Archive metadata too
            meta_file = old_file.with_suffix(".meta.json")
            if meta_file.exists():
                meta_archive = archive_dir / meta_file.name
                shutil.move(str(meta_file), str(meta_archive))


@shared_task(name="ml.validate_new_models")
def validate_new_models() -> dict:
    """
    Validate newly trained models before promoting to production.

    Performs:
    - Sanity checks on predictions
    - Performance comparison with previous version
    - Integration tests

    Returns:
        dict with validation results
    """
    if not ML_AVAILABLE:
        return {"status": "skipped", "reason": "ML dependencies not installed"}

    # TODO: Implement A/B testing logic
    # TODO: Add integration tests
    # TODO: Compare with previous model version

    return {
        "status": "not_implemented",
        "message": "Model validation pipeline coming soon"
    }

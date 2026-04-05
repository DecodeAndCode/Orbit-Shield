"""Training script for the Covariance Estimator model.

Can train from:
1. Real TLE ensemble data in the database (when enough TLEs exist)
2. Synthetic data as fallback

Usage:
    python -m src.ml.training.train_covariance
"""

from __future__ import annotations

import logging
import math
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from src.config import settings
from src.db.models import OrbitalElement, Satellite
from src.ml.config import ml_settings
from src.ml.features.orbital import (
    ORBITAL_FEATURE_NAMES,
    OBJECT_TYPE_MAP,
    RCS_SIZE_MAP,
    compute_derived_orbital_features,
)
from src.ml.models.covariance import CovarianceEstimator
from src.ml.registry import ModelRegistry
from src.ml.training.synthetic import (
    generate_synthetic_covariance_targets,
    generate_synthetic_orbital_features,
)
from src.propagation.sgp4_engine import datetime_to_jd

logger = logging.getLogger(__name__)


def generate_training_data_from_db(
    session: Session,
    min_tles: int = 5,
    reference_time: datetime | None = None,
) -> tuple[np.ndarray, np.ndarray] | None:
    """Generate training data from TLE ensemble scatter in the database.

    For satellites with enough historical TLEs, propagates all TLEs to the
    same epoch and measures the position scatter (sigma). This sigma becomes
    the training target.

    Args:
        session: Synchronous SQLAlchemy session.
        min_tles: Minimum number of TLEs required per satellite.
        reference_time: Epoch for propagation (defaults to now).

    Returns:
        (X, y) tuple of feature matrix and log10(sigma_km) targets,
        or None if insufficient data.
    """
    if reference_time is None:
        reference_time = datetime.now(timezone.utc)

    # Find satellites with enough TLEs
    tle_counts = (
        select(
            OrbitalElement.norad_id,
            func.count().label("tle_count"),
        )
        .group_by(OrbitalElement.norad_id)
        .having(func.count() >= min_tles)
        .subquery()
    )

    norad_ids = [
        row[0] for row in session.execute(select(tle_counts.c.norad_id)).all()
    ]

    if len(norad_ids) < 50:
        logger.info(
            "Only %d satellites with >= %d TLEs, insufficient for DB training",
            len(norad_ids),
            min_tles,
        )
        return None

    jd, fr = datetime_to_jd(reference_time)
    features_list = []
    targets = []

    cutoff_30d = reference_time - timedelta(days=30)

    for nid in norad_ids:
        # Load all TLEs for this satellite
        stmt = (
            select(OrbitalElement)
            .where(OrbitalElement.norad_id == nid)
            .order_by(OrbitalElement.epoch.desc())
        )
        rows = session.execute(stmt).scalars().all()

        # Propagate all to reference time, compute scatter
        from sgp4.api import Satrec, WGS72OLD

        positions = []
        for row in rows:
            try:
                if row.tle_line1 and row.tle_line2:
                    sat = Satrec.twoline2rv(row.tle_line1, row.tle_line2)
                else:
                    continue
                e, r, _ = sat.sgp4(jd, fr)
                if e == 0:
                    positions.append(r)
            except Exception:
                continue

        if len(positions) < 3:
            continue

        pos_arr = np.array(positions)
        sigma = float(np.std(pos_arr, axis=0).max())
        if sigma <= 0:
            continue

        target = math.log10(sigma)

        # Extract features for this satellite
        latest = rows[0]
        mean_motion = latest.mean_motion or 15.0
        eccentricity = latest.eccentricity or 0.001
        inclination = latest.inclination or 0.0
        bstar = latest.bstar or 0.0

        derived = compute_derived_orbital_features(
            mean_motion, eccentricity, inclination, bstar
        )

        tle_age_hours = (reference_time - latest.epoch).total_seconds() / 3600.0

        # Count TLEs in last 30 days
        tle_count_30d = sum(1 for r in rows if r.epoch >= cutoff_30d)

        sat_meta = session.get(Satellite, nid)
        obj_type = sat_meta.object_type if sat_meta else None
        rcs_size = sat_meta.rcs_size if sat_meta else None

        feat = {
            "mean_motion": mean_motion,
            "eccentricity": eccentricity,
            "inclination": inclination,
            "bstar": bstar,
            **derived,
            "object_type_encoded": float(OBJECT_TYPE_MAP.get(obj_type, 3)),
            "rcs_size_encoded": float(RCS_SIZE_MAP.get(rcs_size, 1)),
            "tle_age_hours": tle_age_hours,
            "tle_count_30d": float(tle_count_30d),
        }

        features_list.append([feat[name] for name in ORBITAL_FEATURE_NAMES])
        targets.append(target)

    if len(features_list) < 50:
        logger.info("Only %d valid samples from DB, insufficient", len(features_list))
        return None

    X = np.array(features_list, dtype=np.float64)
    y = np.array(targets, dtype=np.float64)

    logger.info("Generated %d training samples from TLE ensemble data", len(y))
    return X, y


def train_covariance_model(
    X: np.ndarray,
    y: np.ndarray,
) -> dict[str, float]:
    """Train and save the covariance estimator model.

    Args:
        X: Feature matrix (n_samples, 14).
        y: Target array of log10(sigma_km).

    Returns:
        Training metrics dict.
    """
    model = CovarianceEstimator()
    metrics = model.train(X, y)

    registry = ModelRegistry()
    registry.save_model(
        model.get_model(),
        ml_settings.covariance_model_name,
        metadata={
            "name": model.name,
            "version": model.version,
            "feature_names": model.feature_names,
            "metrics": metrics,
            "n_samples": len(y),
        },
    )

    return metrics


def main() -> None:
    """CLI entry point for training the covariance model."""
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
        logger.info("Falling back to synthetic training data")
        features_df = generate_synthetic_orbital_features(n_samples=5000)
        X = features_df.values
        y = generate_synthetic_covariance_targets(features_df)

    metrics = train_covariance_model(X, y)
    logger.info("Training complete: %s", metrics)


if __name__ == "__main__":
    main()

"""Backfill pc_ml for existing Conjunctions using the trained ML risk model.

Run once after training models if demo data was seeded before training,
or any time conjunctions exist without pc_ml populated.

Usage:
    uv run python scripts/backfill_ml.py
"""

from __future__ import annotations

import logging
import math

from sqlalchemy import create_engine, select, update
from sqlalchemy.orm import Session

from src.config import settings
from src.db.models import Conjunction, OrbitalElement, Satellite  # noqa: F401
from src.ml.features.conjunction import CONJUNCTION_FEATURE_NAMES
from src.ml.inference import MLInferenceEngine

logger = logging.getLogger(__name__)


def _synthesize_features(conj: Conjunction, session: Session) -> dict[str, float] | None:
    """Build a 22-feature vector for a Conjunction row from stored metadata.

    For demo/backfill use when we don't have screening-time position/velocity vectors.
    Uses miss_distance + relative_velocity + orbital element lookups.
    """
    # Grab latest orbital elements for each side
    def _elem(nid: int) -> OrbitalElement | None:
        return session.execute(
            select(OrbitalElement)
            .where(OrbitalElement.norad_id == nid)
            .order_by(OrbitalElement.epoch.desc())
            .limit(1)
        ).scalar_one_or_none()

    pri = _elem(conj.primary_norad_id)
    sec = _elem(conj.secondary_norad_id)

    miss = conj.miss_distance_km or 0.1
    relv = conj.relative_velocity_kms or 10.0

    def _orbital(el: OrbitalElement | None) -> tuple[float, ...]:
        if el is None:
            return (15.0, 0.001, 51.6, 400.0, 420.0, 1e-4)
        # crude perigee/apogee from mean_motion + ecc
        n = el.mean_motion or 15.0
        e = el.eccentricity or 0.001
        n_rad_s = n * 2.0 * math.pi / 86400.0
        mu = 398600.4418
        a = (mu / (n_rad_s**2)) ** (1.0 / 3.0) if n_rad_s > 0 else 7000.0
        peri = a * (1.0 - e) - 6378.137
        apo = a * (1.0 + e) - 6378.137
        return (n, e, el.inclination or 0.0, peri, apo, el.bstar or 0.0)

    pri_orb = _orbital(pri)
    sec_orb = _orbital(sec)

    # approach angle: use rel velocity magnitude vs head-on default 180°
    approach_angle = 90.0
    b_plane_x = miss  # proxy: miss projected
    b_plane_y = 0.0

    # covariance proxy
    combined_sigma = 1.0  # km default
    sigma_ratio = 1.0
    mahalanobis = miss / combined_sigma if combined_sigma > 0 else 0.0

    # weather defaults
    f107 = 120.0
    kp = 2.0

    values = [
        miss, relv, b_plane_x, b_plane_y, approach_angle,
        *pri_orb,
        *sec_orb,
        combined_sigma, sigma_ratio, mahalanobis,
        f107, kp,
    ]
    return dict(zip(CONJUNCTION_FEATURE_NAMES, values))


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    engine = MLInferenceEngine()
    engine.initialize()
    if not engine.has_conjunction_risk_model:
        logger.error("Conjunction risk model not loaded. Train first with src.ml.training.train_conjunction.")
        return

    db_engine = create_engine(settings.database_url_sync)
    with Session(db_engine) as session:
        rows = session.execute(
            select(Conjunction).where(Conjunction.pc_ml.is_(None))
        ).scalars().all()

        logger.info("Backfilling pc_ml for %d conjunctions", len(rows))
        updated = 0
        for conj in rows:
            feat = _synthesize_features(conj, session)
            if feat is None:
                continue
            pc_ml = engine.predict_conjunction_risk(feat)
            if pc_ml is None:
                continue
            session.execute(
                update(Conjunction)
                .where(Conjunction.id == conj.id)
                .values(pc_ml=float(pc_ml))
            )
            updated += 1
            logger.info(
                "  conj#%d: %d vs %d — pc_classical=%.2e pc_ml=%.2e",
                conj.id, conj.primary_norad_id, conj.secondary_norad_id,
                conj.pc_classical or 0, pc_ml,
            )

        session.commit()
        logger.info("Backfill complete: %d updated", updated)


if __name__ == "__main__":
    main()

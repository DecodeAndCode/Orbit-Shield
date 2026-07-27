"""Celery task for conjunction screening.

Periodic task that propagates the satellite catalog and screens
for close approaches using the SGP4 engine and screening pipeline.
After screening, computes classical collision probability (Pc)
for each detected conjunction using the B-plane method, then
optionally enhances predictions with ML models.
"""

import logging
import math
from datetime import datetime, timedelta, timezone

import numpy as np
from sgp4.api import Satrec, WGS72OLD
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from src.config import settings
from src.ingestion.tasks import celery_app, _get_sync_session

logger = logging.getLogger(__name__)


def _load_recent_satrecs(
    session: Session,
    norad_id: int,
    n: int = 10,
) -> list[Satrec]:
    """Load N most recent TLEs for a satellite and build Satrec objects.

    Args:
        session: Synchronous SQLAlchemy session.
        norad_id: NORAD catalog ID.
        n: Number of recent TLEs to load.

    Returns:
        List of Satrec objects built from historical TLEs.
    """
    from src.db.models import OrbitalElement
    from src.propagation.sgp4_engine import _satrec_from_elements

    stmt = (
        select(OrbitalElement)
        .where(OrbitalElement.norad_id == norad_id)
        .order_by(OrbitalElement.epoch.desc())
        .limit(n)
    )
    rows = session.execute(stmt).scalars().all()

    satrecs: list[Satrec] = []
    for row in rows:
        try:
            if row.tle_line1 and row.tle_line2:
                satrecs.append(Satrec.twoline2rv(row.tle_line1, row.tle_line2))
            elif row.mean_motion is not None and row.eccentricity is not None:
                satrecs.append(_satrec_from_elements(row))
        except Exception:
            continue

    return satrecs


def _init_ml_engine():
    """Try to initialize the ML inference engine.

    Returns:
        MLInferenceEngine instance or None if ML is unavailable.
    """
    try:
        from src.ml import ML_AVAILABLE

        if not ML_AVAILABLE:
            return None

        from src.ml.inference import MLInferenceEngine

        engine = MLInferenceEngine()
        engine.initialize()
        if engine.is_available:
            return engine
    except Exception:
        logger.debug("ML engine initialization failed", exc_info=True)

    return None


@celery_app.task(bind=True, max_retries=2, default_retry_delay=600)
def run_conjunction_screening(self):
    """Propagate catalog and screen for conjunctions.

    Pipeline:
    1. Load latest TLEs from the database
    2. Propagate all satellites over the configured time window
    3. Run the 4-stage screening pipeline
    4. Compute classical Pc for each detected conjunction
    5. Optionally predict ML-enhanced Pc (pc_ml) for each event
    6. Upsert detected conjunctions with screening_source='COMPUTED'
    """
    from src.db.models import Conjunction
    from src.propagation.sgp4_engine import load_catalog
    from src.propagation.screening import screen_conjunctions_streaming
    from src.propagation.probability import (
        compute_collision_probability,
        estimate_covariance_from_tles,
        default_covariance_km2,
    )

    session = _get_sync_session()
    try:
        # Initialize ML engine (gracefully returns None if unavailable)
        ml_engine = _init_ml_engine()
        if ml_engine:
            logger.info("ML inference engine initialized")

        # 1. Load catalog
        catalog = load_catalog(session)
        if len(catalog) < 2:
            logger.warning("Fewer than 2 satellites in catalog, skipping screening")
            return {"status": "skipped", "reason": "insufficient_catalog"}

        # 2-3. Streaming propagation + screening (memory-bounded for full catalog)
        now = datetime.now(timezone.utc)
        end = now + timedelta(hours=settings.propagation_window_hours)

        logger.info(
            "Streaming propagation+screening: %d sats from %s to %s (step=%ds)",
            len(catalog),
            now.isoformat(),
            end.isoformat(),
            settings.propagation_step_seconds,
        )

        events = screen_conjunctions_streaming(
            catalog,
            start=now,
            end=end,
            step_seconds=settings.propagation_step_seconds,
            screening_radius_km=settings.screening_radius_km,
            altitude_margin_km=settings.altitude_overlap_margin_km,
            inclination_threshold_deg=settings.inclination_filter_deg,
        )

        # Screening can run for many minutes with no DB traffic; serverless
        # Postgres may have culled the idle connection. Reset transaction
        # state so the write phase starts on a clean connection.
        session.rollback()

        # 4. Compute Pc for each event
        # Build covariance cache: norad_id -> (3x3 covariance, source)
        norad_ids_needed: set[int] = set()
        for event in events:
            norad_ids_needed.add(event.primary_norad_id)
            norad_ids_needed.add(event.secondary_norad_id)

        # Build a lookup from norad_id to catalog entry for altitude info
        norad_to_entry = {entry.norad_id: entry for entry in catalog}

        # Cache orbital features in bulk (3 queries for the whole set rather
        # than 3 per satellite — the per-satellite form made full-catalog runs
        # unusable against a remote database).
        orbital_features_cache: dict[int, dict[str, float]] = {}
        try:
            from src.ml.features.orbital import extract_features_bulk

            orbital_features_cache = extract_features_bulk(
                list(norad_ids_needed), session, now
            )
        except Exception:
            logger.debug("Bulk orbital feature extraction failed", exc_info=True)

        # Build covariance cache with ML as priority 1
        covariance_cache: dict[int, tuple[np.ndarray, str]] = {}
        for nid in norad_ids_needed:
            feats = orbital_features_cache.get(nid)

            # Priority 1: ML covariance prediction
            if ml_engine and feats is not None:
                ml_result = ml_engine.predict_covariance(feats)
                if ml_result is not None:
                    covariance_cache[nid] = ml_result
                    continue

            # Priority 2: TLE ensemble — needs at least 3 recent TLEs. Skip the
            # per-satellite query entirely when the bulk counts already show
            # there aren't enough (retention keeps only the latest epochs).
            enough_tles = feats is None or feats.get("tle_count_30d", 0) >= 3
            cov = None
            if enough_tles:
                satrecs = _load_recent_satrecs(session, nid, n=10)
                cov = estimate_covariance_from_tles(satrecs, now)

            if cov is not None:
                covariance_cache[nid] = (cov, "tle_ensemble")
            else:
                # Priority 3: Altitude-based default
                entry = norad_to_entry.get(nid)
                alt = entry.perigee_alt_km if entry else 500.0
                covariance_cache[nid] = (default_covariance_km2(alt), "default")

        pc_computed = 0
        for event in events:
            if event.relative_position_km is None or event.relative_velocity_kms_vec is None:
                continue

            pri_cov, pri_src = covariance_cache[event.primary_norad_id]
            sec_cov, sec_src = covariance_cache[event.secondary_norad_id]

            result = compute_collision_probability(
                relative_position_km=event.relative_position_km,
                relative_velocity_kms=event.relative_velocity_kms_vec,
                primary_cov=pri_cov,
                secondary_cov=sec_cov,
            )
            result.covariance_source = pri_src if pri_src == sec_src else f"{pri_src}/{sec_src}"
            event.pc_classical = result.pc
            pc_computed += 1

        logger.info(
            "Pc computed for %d/%d events",
            pc_computed,
            len(events),
        )

        # 5. ML-enhanced risk prediction (pc_ml)
        pc_ml_computed = 0
        pc_ml_cache: dict[int, float | None] = {}  # event index -> pc_ml
        if ml_engine and ml_engine.has_conjunction_risk_model:
            try:
                from src.ml.features.conjunction import extract_conjunction_features
                from src.ml.features.weather import get_current_weather

                weather = get_current_weather(settings.redis_url)

                for idx, event in enumerate(events):
                    if event.relative_position_km is None or event.relative_velocity_kms_vec is None:
                        continue

                    pri_feat = orbital_features_cache.get(event.primary_norad_id, {})
                    sec_feat = orbital_features_cache.get(event.secondary_norad_id, {})
                    pri_cov, _ = covariance_cache.get(event.primary_norad_id, (None, ""))
                    sec_cov, _ = covariance_cache.get(event.secondary_norad_id, (None, ""))

                    conj_features = extract_conjunction_features(
                        miss_distance_km=event.miss_distance_km,
                        relative_velocity_kms=event.relative_velocity_kms,
                        relative_position_km=event.relative_position_km,
                        relative_velocity_vec=event.relative_velocity_kms_vec,
                        primary_features=pri_feat,
                        secondary_features=sec_feat,
                        primary_cov=pri_cov,
                        secondary_cov=sec_cov,
                        weather=weather,
                    )

                    pc_ml = ml_engine.predict_conjunction_risk(conj_features)
                    if pc_ml is not None:
                        pc_ml_cache[idx] = pc_ml
                        pc_ml_computed += 1
            except Exception:
                logger.debug("ML risk prediction failed", exc_info=True)

        if pc_ml_computed > 0:
            logger.info("ML risk predicted for %d events", pc_ml_computed)

        # 6. Upsert conjunctions
        inserted = 0
        for idx, event in enumerate(events):
            pc_val = event.pc_classical
            pc_ml_val = pc_ml_cache.get(idx)

            values = {
                "primary_norad_id": event.primary_norad_id,
                "secondary_norad_id": event.secondary_norad_id,
                "tca": event.tca,
                "miss_distance_km": event.miss_distance_km,
                "relative_velocity_kms": event.relative_velocity_kms,
                "pc_classical": pc_val,
                "pc_ml": pc_ml_val,
                "screening_source": "COMPUTED",
            }

            update_set = {
                "miss_distance_km": event.miss_distance_km,
                "relative_velocity_kms": event.relative_velocity_kms,
                "pc_classical": pc_val,
                "pc_ml": pc_ml_val,
                "screening_source": "COMPUTED",
            }

            stmt = (
                pg_insert(Conjunction.__table__)
                .values(**values)
                .on_conflict_do_update(
                    constraint="uq_conjunction_pair_tca",
                    set_=update_set,
                )
            )
            session.execute(stmt)
            inserted += 1

        session.commit()

        # 7. Evaluate alerts on freshly upserted conjunctions
        alerts_fired = 0
        try:
            from src.alerts.evaluator import evaluate as evaluate_alerts
            from src.db.models import Conjunction as _Conj
            from sqlalchemy import select as _select

            # Re-fetch persisted rows for evaluator
            tcas = [e.tca for e in events]
            if tcas:
                rows = session.execute(
                    _select(_Conj).where(_Conj.tca.in_(tcas))
                ).scalars().all()
                alerts_fired = evaluate_alerts(session, rows)
                if alerts_fired:
                    logger.info("alerts dispatched: %d", alerts_fired)
        except Exception:
            logger.exception("alert evaluation failed")

        logger.info(
            "Screening complete: %d conjunctions detected, %d upserted, %d with Pc, %d with ML, %d alerts",
            len(events),
            inserted,
            pc_computed,
            pc_ml_computed,
            alerts_fired,
        )

        return {
            "status": "ok",
            "satellites_propagated": len(catalog),
            "conjunctions_detected": len(events),
            "pc_computed": pc_computed,
            "pc_ml_computed": pc_ml_computed,
            "alerts_fired": alerts_fired,
        }

    except Exception as exc:
        session.rollback()
        logger.error("Conjunction screening failed: %s", exc)
        raise self.retry(exc=exc)
    finally:
        session.close()

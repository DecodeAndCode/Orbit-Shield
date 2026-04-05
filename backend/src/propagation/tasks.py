"""Celery task for conjunction screening.

Periodic task that propagates the satellite catalog and screens
for close approaches using the SGP4 engine and screening pipeline.
After screening, computes classical collision probability (Pc)
for each detected conjunction using the B-plane method.
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


@celery_app.task(bind=True, max_retries=2, default_retry_delay=600)
def run_conjunction_screening(self):
    """Propagate catalog and screen for conjunctions.

    Pipeline:
    1. Load latest TLEs from the database
    2. Propagate all satellites over the configured time window
    3. Run the 4-stage screening pipeline
    4. Compute classical Pc for each detected conjunction
    5. Upsert detected conjunctions with screening_source='COMPUTED'
    """
    from src.db.models import Conjunction
    from src.propagation.sgp4_engine import load_catalog, propagate_catalog
    from src.propagation.screening import screen_conjunctions
    from src.propagation.probability import (
        compute_collision_probability,
        estimate_covariance_from_tles,
        default_covariance_km2,
    )

    session = _get_sync_session()
    try:
        # 1. Load catalog
        catalog = load_catalog(session)
        if len(catalog) < 2:
            logger.warning("Fewer than 2 satellites in catalog, skipping screening")
            return {"status": "skipped", "reason": "insufficient_catalog"}

        # 2. Propagate
        now = datetime.now(timezone.utc)
        end = now + timedelta(hours=settings.propagation_window_hours)

        logger.info(
            "Propagating %d satellites from %s to %s (step=%ds)",
            len(catalog),
            now.isoformat(),
            end.isoformat(),
            settings.propagation_step_seconds,
        )

        prop_result = propagate_catalog(
            catalog,
            start=now,
            end=end,
            step_seconds=settings.propagation_step_seconds,
        )

        # 3. Screen
        events = screen_conjunctions(
            catalog,
            prop_result,
            screening_radius_km=settings.screening_radius_km,
            altitude_margin_km=settings.altitude_overlap_margin_km,
            inclination_threshold_deg=settings.inclination_filter_deg,
        )

        # 4. Compute Pc for each event
        # Build covariance cache: norad_id -> 3x3 covariance
        norad_ids_needed: set[int] = set()
        for event in events:
            norad_ids_needed.add(event.primary_norad_id)
            norad_ids_needed.add(event.secondary_norad_id)

        # Build a lookup from norad_id to catalog entry for altitude info
        norad_to_entry = {entry.norad_id: entry for entry in catalog}

        covariance_cache: dict[int, tuple[np.ndarray, str]] = {}
        for nid in norad_ids_needed:
            satrecs = _load_recent_satrecs(session, nid, n=10)
            cov = estimate_covariance_from_tles(satrecs, now)
            if cov is not None:
                covariance_cache[nid] = (cov, "tle_ensemble")
            else:
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

        # 5. Upsert conjunctions
        inserted = 0
        for event in events:
            pc_val = getattr(event, "pc_classical", None)
            stmt = (
                pg_insert(Conjunction.__table__)
                .values(
                    primary_norad_id=event.primary_norad_id,
                    secondary_norad_id=event.secondary_norad_id,
                    tca=event.tca,
                    miss_distance_km=event.miss_distance_km,
                    relative_velocity_kms=event.relative_velocity_kms,
                    pc_classical=pc_val,
                    screening_source="COMPUTED",
                )
                .on_conflict_do_update(
                    constraint="uq_conjunction_pair_tca",
                    set_={
                        "miss_distance_km": event.miss_distance_km,
                        "relative_velocity_kms": event.relative_velocity_kms,
                        "pc_classical": pc_val,
                        "screening_source": "COMPUTED",
                    },
                )
            )
            session.execute(stmt)
            inserted += 1

        session.commit()
        logger.info(
            "Screening complete: %d conjunctions detected, %d upserted, %d with Pc",
            len(events),
            inserted,
            pc_computed,
        )

        return {
            "status": "ok",
            "satellites_propagated": int(prop_result.valid_mask.sum()),
            "conjunctions_detected": len(events),
            "pc_computed": pc_computed,
        }

    except Exception as exc:
        session.rollback()
        logger.error("Conjunction screening failed: %s", exc)
        raise self.retry(exc=exc)
    finally:
        session.close()

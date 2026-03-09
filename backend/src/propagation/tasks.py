"""Celery task for conjunction screening.

Periodic task that propagates the satellite catalog and screens
for close approaches using the SGP4 engine and screening pipeline.
"""

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy.dialects.postgresql import insert as pg_insert

from src.config import settings
from src.ingestion.tasks import celery_app, _get_sync_session

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=2, default_retry_delay=600)
def run_conjunction_screening(self):
    """Propagate catalog and screen for conjunctions.

    Pipeline:
    1. Load latest TLEs from the database
    2. Propagate all satellites over the configured time window
    3. Run the 4-stage screening pipeline
    4. Upsert detected conjunctions with screening_source='COMPUTED'
    """
    from src.db.models import Conjunction
    from src.propagation.sgp4_engine import load_catalog, propagate_catalog
    from src.propagation.screening import screen_conjunctions

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

        # 4. Upsert conjunctions
        inserted = 0
        for event in events:
            stmt = (
                pg_insert(Conjunction.__table__)
                .values(
                    primary_norad_id=event.primary_norad_id,
                    secondary_norad_id=event.secondary_norad_id,
                    tca=event.tca,
                    miss_distance_km=event.miss_distance_km,
                    relative_velocity_kms=event.relative_velocity_kms,
                    screening_source="COMPUTED",
                )
                .on_conflict_do_update(
                    constraint="uq_conjunction_pair_tca",
                    set_={
                        "miss_distance_km": event.miss_distance_km,
                        "relative_velocity_kms": event.relative_velocity_kms,
                        "screening_source": "COMPUTED",
                    },
                )
            )
            session.execute(stmt)
            inserted += 1

        session.commit()
        logger.info(
            "Screening complete: %d conjunctions detected, %d upserted",
            len(events),
            inserted,
        )

        return {
            "status": "ok",
            "satellites_propagated": int(prop_result.valid_mask.sum()),
            "conjunctions_detected": len(events),
        }

    except Exception as exc:
        session.rollback()
        logger.error("Conjunction screening failed: %s", exc)
        raise self.retry(exc=exc)
    finally:
        session.close()

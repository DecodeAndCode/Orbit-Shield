"""Celery task definitions for data ingestion.

Periodic tasks that fetch orbital data from external sources
and persist it to the database.

Worker: celery -A src.ingestion.tasks worker --loglevel=info
Beat:   celery -A src.ingestion.tasks beat --loglevel=info
"""

import asyncio
import json
import logging
from datetime import datetime, timezone

import redis as redis_lib
from celery import Celery
from celery.schedules import crontab
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from src.config import settings

logger = logging.getLogger(__name__)

# ── Celery app ──────────────────────────────────────────────

celery_app = Celery(
    "collider",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    beat_schedule={
        "fetch-celestrak-tles": {
            "task": "src.ingestion.tasks.fetch_celestrak_tles",
            "schedule": crontab(minute=0, hour="*/6"),
        },
        "fetch-spacetrack-catalog": {
            "task": "src.ingestion.tasks.fetch_spacetrack_catalog",
            "schedule": crontab(minute=30, hour=3),
        },
        "fetch-socrates-conjunctions": {
            "task": "src.ingestion.tasks.fetch_socrates_conjunctions",
            "schedule": crontab(minute=15, hour="*/8"),
        },
        "fetch-space-weather": {
            "task": "src.ingestion.tasks.fetch_space_weather",
            "schedule": crontab(minute=45, hour="*/3"),
        },
        "run-conjunction-screening": {
            "task": "src.propagation.tasks.run_conjunction_screening",
            "schedule": crontab(minute=0, hour="*/8"),
        },
    },
)


def _run_async(coro):
    """Run an async coroutine from a sync Celery task."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _get_sync_session() -> Session:
    """Create a synchronous SQLAlchemy session for Celery tasks."""
    engine = create_engine(settings.database_url_sync)
    return Session(engine)


# ── Tasks ───────────────────────────────────────────────────


@celery_app.task(bind=True, max_retries=3, default_retry_delay=300)
def fetch_celestrak_tles(self):
    """Fetch TLEs from CelesTrak active group and upsert into database."""
    from src.db.models import OrbitalElement, Satellite
    from src.ingestion.celestrak import CelesTrakClient

    async def _fetch():
        client = CelesTrakClient()
        return await client.fetch_group("active")

    try:
        records = _run_async(_fetch())
        logger.info(f"Fetched {len(records)} GP records from CelesTrak")

        session = _get_sync_session()
        try:
            for record in records:
                stmt = (
                    pg_insert(Satellite.__table__)
                    .values(
                        norad_id=record.norad_id,
                        name=record.name,
                        object_type=record.object_type,
                    )
                    .on_conflict_do_update(
                        index_elements=["norad_id"],
                        set_={
                            "name": record.name,
                            "object_type": record.object_type,
                            "updated_at": datetime.now(timezone.utc),
                        },
                    )
                )
                session.execute(stmt)

                elem = OrbitalElement(
                    norad_id=record.norad_id,
                    epoch=record.epoch,
                    tle_line1=record.tle_line1,
                    tle_line2=record.tle_line2,
                    mean_motion=record.mean_motion,
                    eccentricity=record.eccentricity,
                    inclination=record.inclination,
                    raan=record.raan,
                    arg_perigee=record.arg_perigee,
                    mean_anomaly=record.mean_anomaly,
                    bstar=record.bstar,
                )
                session.add(elem)

            session.commit()
            logger.info(f"Upserted {len(records)} satellites and orbital elements")
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    except Exception as exc:
        logger.error(f"CelesTrak fetch failed: {exc}")
        raise self.retry(exc=exc)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=600)
def fetch_spacetrack_catalog(self):
    """Daily full catalog sync from Space-Track.org (~47,000 objects)."""
    from src.db.models import OrbitalElement, Satellite
    from src.ingestion.spacetrack import SpaceTrackClient

    async def _fetch():
        client = SpaceTrackClient()
        try:
            return await client.fetch_gp_catalog(epoch_days_ago=30)
        finally:
            await client.close()

    try:
        records = _run_async(_fetch())
        logger.info(f"Fetched {len(records)} GP records from Space-Track")

        session = _get_sync_session()
        try:
            for record in records:
                stmt = (
                    pg_insert(Satellite.__table__)
                    .values(
                        norad_id=int(record["NORAD_CAT_ID"]),
                        name=record.get("OBJECT_NAME"),
                        object_type=record.get("OBJECT_TYPE"),
                        country=record.get("COUNTRY_CODE"),
                        launch_date=record.get("LAUNCH_DATE"),
                        decay_date=record.get("DECAY_DATE"),
                        rcs_size=record.get("RCS_SIZE"),
                    )
                    .on_conflict_do_update(
                        index_elements=["norad_id"],
                        set_={
                            "name": record.get("OBJECT_NAME"),
                            "object_type": record.get("OBJECT_TYPE"),
                            "country": record.get("COUNTRY_CODE"),
                            "rcs_size": record.get("RCS_SIZE"),
                            "updated_at": datetime.now(timezone.utc),
                        },
                    )
                )
                session.execute(stmt)

                elem = OrbitalElement(
                    norad_id=int(record["NORAD_CAT_ID"]),
                    epoch=datetime.fromisoformat(record["EPOCH"]),
                    tle_line1=record.get("TLE_LINE1"),
                    tle_line2=record.get("TLE_LINE2"),
                    mean_motion=float(record["MEAN_MOTION"]),
                    eccentricity=float(record["ECCENTRICITY"]),
                    inclination=float(record["INCLINATION"]),
                    raan=float(record["RA_OF_ASC_NODE"]),
                    arg_perigee=float(record["ARG_OF_PERICENTER"]),
                    mean_anomaly=float(record["MEAN_ANOMALY"]),
                    bstar=float(record["BSTAR"]),
                )
                session.add(elem)

            session.commit()
            logger.info(f"Synced {len(records)} objects from Space-Track catalog")
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    except Exception as exc:
        logger.error(f"Space-Track catalog sync failed: {exc}")
        raise self.retry(exc=exc)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=300)
def fetch_socrates_conjunctions(self):
    """Fetch SOCRATES conjunction reports from CelesTrak (every 8 hours)."""
    from src.db.models import Conjunction, Satellite
    from src.ingestion.socrates import SOCRATESClient

    async def _fetch():
        client = SOCRATESClient()
        return await client.fetch_conjunctions(sort_by="min_range")

    try:
        records = _run_async(_fetch())
        logger.info(f"Fetched {len(records)} SOCRATES conjunction records")

        session = _get_sync_session()
        try:
            for record in records:
                # Ensure both satellites exist
                for nid, name in [
                    (record.primary_norad_id, record.primary_name),
                    (record.secondary_norad_id, record.secondary_name),
                ]:
                    stmt = (
                        pg_insert(Satellite.__table__)
                        .values(norad_id=nid, name=name)
                        .on_conflict_do_nothing()
                    )
                    session.execute(stmt)

                # Upsert conjunction
                stmt = (
                    pg_insert(Conjunction.__table__)
                    .values(
                        primary_norad_id=record.primary_norad_id,
                        secondary_norad_id=record.secondary_norad_id,
                        tca=record.tca,
                        miss_distance_km=record.miss_distance_km,
                        relative_velocity_kms=record.relative_velocity_kms,
                        pc_classical=record.max_probability,
                        screening_source="SOCRATES",
                    )
                    .on_conflict_do_update(
                        constraint="uq_conjunction_pair_tca",
                        set_={
                            "miss_distance_km": record.miss_distance_km,
                            "relative_velocity_kms": record.relative_velocity_kms,
                            "pc_classical": record.max_probability,
                        },
                    )
                )
                session.execute(stmt)

            session.commit()
            logger.info(f"Stored {len(records)} SOCRATES conjunctions")
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    except Exception as exc:
        logger.error(f"SOCRATES fetch failed: {exc}")
        raise self.retry(exc=exc)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=300)
def fetch_space_weather(self):
    """Fetch space weather data from NOAA SWPC, store latest in Redis."""
    from src.ingestion.weather import SpaceWeatherClient

    async def _fetch():
        client = SpaceWeatherClient()
        flux = await client.fetch_f107_flux()
        kp = await client.fetch_kp_index()
        return flux, kp

    try:
        flux_records, kp_records = _run_async(_fetch())
        logger.info(
            f"Fetched {len(flux_records)} F10.7 and {len(kp_records)} Kp records"
        )

        r = redis_lib.from_url(settings.redis_url)
        if flux_records:
            latest_flux = flux_records[-1]
            r.set(
                "space_weather:f107_flux",
                json.dumps(
                    {
                        "time_tag": latest_flux.time_tag.isoformat(),
                        "flux": latest_flux.flux,
                    }
                ),
            )
        if kp_records:
            latest_kp = kp_records[-1]
            r.set(
                "space_weather:kp_index",
                json.dumps(
                    {
                        "time_tag": latest_kp.time_tag.isoformat(),
                        "kp": latest_kp.kp,
                    }
                ),
            )

        logger.info("Updated space weather data in Redis")

    except Exception as exc:
        logger.error(f"Space weather fetch failed: {exc}")
        raise self.retry(exc=exc)

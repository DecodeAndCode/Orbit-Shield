"""Bulk-download historical Space-Track CDMs into cdm_history.

Space-Track's cdm_public class covers the active / recent window (not a
deep archive). This script slides a per-day window back N days and upserts
everything it finds, so running it weekly builds a labeled dataset over
time without hammering the API.

Usage:
    uv run python -m backend.scripts.download_cdms --days 14
    uv run python -m backend.scripts.download_cdms --days 30 --dry-run

Env:
    Requires SPACETRACK_USERNAME and SPACETRACK_PASSWORD in settings.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from src.config import settings
from src.ingestion.cdm_parser import parse_cdm
from src.ingestion.cdm_store import upsert_cdm
from src.ingestion.spacetrack import SpaceTrackClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s - %(message)s",
)
logger = logging.getLogger("download_cdms")


async def _fetch_window(
    client: SpaceTrackClient,
    start: datetime,
    end: datetime,
) -> list[dict]:
    return await client.fetch_cdms_between(start=start, end=end)


async def main(days: int, dry_run: bool) -> int:
    if not settings.spacetrack_username or not settings.spacetrack_password:
        logger.error("SPACETRACK_USERNAME / SPACETRACK_PASSWORD not configured")
        return 2

    engine = create_engine(settings.database_url_sync)
    client = SpaceTrackClient()
    total_fetched = 0
    total_upserted = 0

    try:
        now = datetime.now(timezone.utc).replace(microsecond=0)
        for i in range(days):
            end = now - timedelta(days=i)
            start = end - timedelta(days=1)
            logger.info(f"Fetching CDMs for window {start.isoformat()} → {end.isoformat()}")
            try:
                records = await _fetch_window(client, start, end)
            except Exception as exc:
                logger.warning(f"Window fetch failed ({start.date()}): {exc}")
                continue

            total_fetched += len(records)
            logger.info(f"  fetched {len(records)} records")

            if dry_run or not records:
                continue

            with Session(engine) as session:
                try:
                    for rec in records:
                        parsed = parse_cdm(rec)
                        if parsed is None:
                            continue
                        upsert_cdm(session, parsed)
                        total_upserted += 1
                    session.commit()
                except Exception:
                    session.rollback()
                    raise

    finally:
        await client.close()

    logger.info(
        f"Done. Fetched={total_fetched} Upserted={total_upserted} "
        f"(dry_run={dry_run})"
    )
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--days", type=int, default=7, help="Days of history to pull")
    ap.add_argument("--dry-run", action="store_true", help="Fetch only, no DB writes")
    args = ap.parse_args()
    sys.exit(asyncio.run(main(days=args.days, dry_run=args.dry_run)))

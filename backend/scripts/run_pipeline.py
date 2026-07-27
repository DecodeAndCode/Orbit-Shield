"""Full ingestion + screening pipeline for scheduled (CI) execution.

This is the entry point used by the daily GitHub Actions run. It replaces
the always-on Celery worker + beat pair: everything the beat schedule used
to trigger happens here, once, in one process, then exits.

Steps:
  1. Ingest fresh TLEs (Space-Track when credentials are present, otherwise
     CelesTrak, which needs no authentication).
  2. Stream-propagate the full catalog, screen for conjunctions, compute
     classical Pc, run the XGBoost ML layer, and upsert results.
  3. Prune expired rows so the database stays inside free-tier limits.

Every step is optional-failure tolerant except screening: ingestion or
pruning problems are logged and the run continues, because stale TLEs still
produce useful screening output. Screening failure exits non-zero so the
scheduled run is visibly red.

Usage:
    python scripts/run_pipeline.py                 # all steps
    python scripts/run_pipeline.py --skip-ingest   # screen existing catalog
    python scripts/run_pipeline.py --only prune
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from datetime import datetime, timezone

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(message)s",
    datefmt="%H:%M:%S",
    stream=sys.stdout,
)
logger = logging.getLogger("pipeline")

STEPS = ("ingest", "screen", "prune")

# Substrings that identify a provider-side capacity block rather than a fault
# in this code. Serverless Postgres plans suspend the database when a monthly
# allowance runs out and resume it when the billing period rolls over, so a
# scheduled run that lands inside that window should report "skipped", not
# "broken" — otherwise every night until the reset looks like a regression.
# Kept deliberately narrow: ordinary connection failures must still fail loudly.
PROVIDER_QUOTA_SIGNATURES = (
    "exceeded the data transfer quota",
    "exceeded the logical size limit",
    "exceeded the compute time quota",
    "reaching its monthly free plan limit",
    "project is paused",
    "project has been suspended",
)


def database_quota_block() -> str | None:
    """Return the provider's message if the database is capacity-blocked.

    Returns None when the database is reachable, or when it is unreachable
    for any reason other than a recognised quota block — those must surface
    as genuine failures.
    """
    from sqlalchemy import create_engine, text

    from src.config import settings

    try:
        engine = create_engine(settings.database_url_sync, pool_pre_ping=True)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return None
    except Exception as exc:
        message = str(exc)
        lowered = message.lower()
        if any(sig in lowered for sig in PROVIDER_QUOTA_SIGNATURES):
            return message.strip().splitlines()[0]
        return None


def _run_step(name: str, fn) -> tuple[bool, object]:
    """Execute one pipeline step, timing it and trapping exceptions."""
    logger.info("=" * 62)
    logger.info("STEP: %s", name)
    logger.info("=" * 62)
    started = time.monotonic()
    try:
        result = fn()
        elapsed = time.monotonic() - started
        logger.info("STEP %s OK in %.1fs -> %s", name, elapsed, result)
        return True, result
    except Exception as exc:
        elapsed = time.monotonic() - started
        logger.error("STEP %s FAILED after %.1fs: %s", name, elapsed, exc, exc_info=True)
        return False, None


def _ingest() -> str:
    """Fetch fresh TLEs. Prefers Space-Track (full catalog) when configured."""
    from src.config import settings
    from src.ingestion.tasks import fetch_celestrak_tles, fetch_spacetrack_catalog

    if settings.spacetrack_username and settings.spacetrack_password:
        logger.info("Space-Track credentials present, fetching full catalog")
        fetch_spacetrack_catalog()
        return "spacetrack"

    logger.info("No Space-Track credentials, falling back to CelesTrak")
    fetch_celestrak_tles()
    return "celestrak"


def _screen() -> dict:
    """Run streaming screening + classical Pc + ML enhancement."""
    from src.propagation.tasks import run_conjunction_screening

    return run_conjunction_screening()


def _prune() -> str:
    """Delete expired conjunctions and surplus TLE history."""
    from src.ingestion.tasks import prune_storage

    prune_storage()
    return "pruned"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--only",
        choices=STEPS,
        help="Run a single step instead of the whole pipeline.",
    )
    parser.add_argument(
        "--skip-ingest",
        action="store_true",
        help="Screen the existing catalog without fetching new TLEs.",
    )
    parser.add_argument(
        "--check-db",
        action="store_true",
        help=(
            "Probe the database and print 'available' or 'blocked' without "
            "running any step. Always exits 0 so a caller can branch on the "
            "printed value rather than on the exit status."
        ),
    )
    args = parser.parse_args()

    if args.check_db:
        blocked = database_quota_block()
        if blocked:
            logger.warning("Database is capacity-blocked: %s", blocked)
        # Printed last and on its own line: callers read this with `tail -1`,
        # so nothing may follow it on stdout.
        print("blocked" if blocked else "available")
        return 0

    if args.only:
        selected = (args.only,)
    else:
        selected = tuple(s for s in STEPS if not (args.skip_ingest and s == "ingest"))

    from src.config import settings

    # Never log the password: show only the host we are pointed at.
    db_host = settings.database_url.split("@")[-1].split("/")[0]
    logger.info("Pipeline start %s UTC", datetime.now(timezone.utc).isoformat())
    logger.info("Database host: %s", db_host)
    logger.info("Steps: %s", ", ".join(selected))

    blocked = database_quota_block()
    if blocked:
        logger.warning("Database is capacity-blocked by the provider: %s", blocked)
        logger.warning(
            "Skipping this run. It will resume automatically once the "
            "allowance resets — no code change or manual step required."
        )
        # A GitHub Actions notice keeps the run green while making the reason
        # visible in the workflow summary.
        print(f"::notice title=Screening skipped::Database unavailable: {blocked}")
        return 0

    handlers = {"ingest": _ingest, "screen": _screen, "prune": _prune}
    outcomes: dict[str, bool] = {}
    screen_result: object = None
    overall_start = time.monotonic()

    for step in selected:
        ok, result = _run_step(step, handlers[step])
        outcomes[step] = ok
        if step == "screen":
            screen_result = result

    total = time.monotonic() - overall_start
    logger.info("=" * 62)
    logger.info("SUMMARY (%.1fs total)", total)
    for step in selected:
        logger.info("  %-7s %s", step, "OK" if outcomes[step] else "FAILED")
    if isinstance(screen_result, dict):
        for key in (
            "satellites_propagated",
            "conjunctions_detected",
            "pc_computed",
            "pc_ml_computed",
            "alerts_fired",
        ):
            if key in screen_result:
                logger.info("  %-22s %s", key, screen_result[key])
    logger.info("=" * 62)

    # Only screening failure is fatal; stale TLEs still screen usefully.
    if "screen" in outcomes and not outcomes["screen"]:
        logger.error("Screening failed — marking run as failed")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

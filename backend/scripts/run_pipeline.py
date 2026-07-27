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
    args = parser.parse_args()

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

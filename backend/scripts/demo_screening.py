"""One-shot demo screening with sliced catalog for sub-1-min runs.

Monkey-patches load_catalog to return only N LEO sats so the 66M-pair
explosion at full catalog never happens.

Env:
  DEMO_N_SATS (default 2000)
  PROPAGATION_WINDOW_HOURS (default 24)
  PROPAGATION_STEP_SECONDS (default 60)
"""
from __future__ import annotations

import logging
import os

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

N_SATS = int(os.environ.get("DEMO_N_SATS", "2000"))

# ── Monkey-patch load_catalog BEFORE importing the task ────────────
from src.propagation import sgp4_engine  # noqa: E402

_original_load_catalog = sgp4_engine.load_catalog


def sliced_load_catalog(session):
    catalog = _original_load_catalog(session)
    leo = [c for c in catalog if c.perigee_alt_km and c.perigee_alt_km < 2000]
    leo.sort(key=lambda c: c.perigee_alt_km)
    sliced = leo[:N_SATS]
    logger.info(
        "DEMO SLICE: %d sats → %d LEO → top %d by altitude",
        len(catalog),
        len(leo),
        len(sliced),
    )
    return sliced


sgp4_engine.load_catalog = sliced_load_catalog

# Also patch in the tasks module (it imports inside the function)
from src.propagation import tasks as prop_tasks  # noqa: E402

# Run
result = prop_tasks.run_conjunction_screening()
print("RESULT:", result)

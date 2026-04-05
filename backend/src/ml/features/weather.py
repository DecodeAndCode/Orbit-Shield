"""Space weather feature extraction from Redis."""

from __future__ import annotations

import json
import logging

logger = logging.getLogger(__name__)

# Default values when Redis data is unavailable
DEFAULT_F107_FLUX = 150.0
DEFAULT_KP_INDEX = 3.0


def get_current_weather(redis_url: str) -> dict[str, float]:
    """Fetch current space weather data from Redis.

    Args:
        redis_url: Redis connection URL.

    Returns:
        Dict with f107_flux and kp_index.
        Returns defaults if Redis is unavailable or data is missing.
    """
    try:
        import redis

        r = redis.from_url(redis_url, decode_responses=True)
        raw = r.get("space_weather:current")
        if raw:
            data = json.loads(raw)
            return {
                "f107_flux": float(data.get("f107_flux", DEFAULT_F107_FLUX)),
                "kp_index": float(data.get("kp_index", DEFAULT_KP_INDEX)),
            }
    except Exception:
        logger.debug("Could not fetch weather from Redis, using defaults")

    return {
        "f107_flux": DEFAULT_F107_FLUX,
        "kp_index": DEFAULT_KP_INDEX,
    }

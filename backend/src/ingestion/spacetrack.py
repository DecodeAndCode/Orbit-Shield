"""Space-Track.org API client.

Authenticated REST client for the Space-Track.org API. Handles cookie-based
session auth, rate limiting, and data fetching for GP (TLE/OMM) and CDM classes.

API docs: https://www.space-track.org/documentation
Rate limits: 30 req/min, 300 req/hr. Full GP pull max once/hour.
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime

import httpx

from src.config import settings

logger = logging.getLogger(__name__)

LOGIN_URL = "https://www.space-track.org/ajaxauth/login"
BASE_QUERY_URL = "https://www.space-track.org/basicspacedata/query"


@dataclass
class RateLimiter:
    """Sliding window rate limiter for Space-Track API compliance."""

    max_per_minute: int = 30
    _timestamps: list[float] = field(default_factory=list)

    async def acquire(self) -> None:
        now = time.monotonic()
        self._timestamps = [t for t in self._timestamps if now - t < 60.0]
        if len(self._timestamps) >= self.max_per_minute:
            sleep_time = 60.0 - (now - self._timestamps[0])
            if sleep_time > 0:
                logger.info(f"Rate limit: sleeping {sleep_time:.1f}s")
                await asyncio.sleep(sleep_time)
        self._timestamps.append(time.monotonic())


class SpaceTrackClient:
    """Async client for Space-Track.org REST API."""

    def __init__(
        self,
        username: str | None = None,
        password: str | None = None,
    ):
        self.username = username or settings.spacetrack_username
        self.password = password or settings.spacetrack_password
        self._client: httpx.AsyncClient | None = None
        self._rate_limiter = RateLimiter()

    async def _ensure_authenticated(self) -> httpx.AsyncClient:
        """Login and return authenticated httpx client with session cookie."""
        if self._client is not None:
            return self._client

        self._client = httpx.AsyncClient(timeout=120.0)
        response = await self._client.post(
            LOGIN_URL,
            data={"identity": self.username, "password": self.password},
        )
        response.raise_for_status()

        if "Login Failed" in response.text:
            raise RuntimeError("Space-Track login failed. Check credentials.")

        logger.info("Authenticated with Space-Track.org")
        return self._client

    async def _query(self, path: str) -> list[dict]:
        """Execute a query against the Space-Track REST API."""
        client = await self._ensure_authenticated()
        await self._rate_limiter.acquire()

        url = f"{BASE_QUERY_URL}{path}"
        response = await client.get(url)
        response.raise_for_status()
        return response.json()

    async def fetch_gp_catalog(
        self,
        epoch_days_ago: int = 30,
        object_type: str | None = None,
    ) -> list[dict]:
        """Fetch the full GP catalog from Space-Track.

        Args:
            epoch_days_ago: Only fetch objects with epoch within this many days.
            object_type: Filter by PAYLOAD, ROCKET BODY, DEBRIS, or None for all.
        """
        path = f"/class/gp/EPOCH/>now-{epoch_days_ago}/orderby/NORAD_CAT_ID/format/json"
        if object_type:
            path = f"/class/gp/EPOCH/>now-{epoch_days_ago}/OBJECT_TYPE/{object_type}/orderby/NORAD_CAT_ID/format/json"
        return await self._query(path)

    async def fetch_gp_by_norad_id(self, norad_id: int) -> dict | None:
        """Fetch latest GP data for a single NORAD ID."""
        path = f"/class/gp/NORAD_CAT_ID/{norad_id}/orderby/EPOCH desc/limit/1/format/json"
        results = await self._query(path)
        return results[0] if results else None

    async def fetch_cdm_public(self, days: int = 7) -> list[dict]:
        """Fetch public CDM records from the last N days."""
        path = f"/class/cdm_public/CREATED/>now-{days}/orderby/TCA/format/json"
        return await self._query(path)

    async def fetch_cdms_between(
        self,
        start: datetime,
        end: datetime,
        limit: int | None = None,
    ) -> list[dict]:
        """Fetch CDMs with CREATION_DATE in [start, end).

        Space-Track date predicates use 'YYYY-MM-DD HH:MM:SS' with '--' for ranges.
        """
        s = start.strftime("%Y-%m-%d%%20%H:%M:%S")
        e = end.strftime("%Y-%m-%d%%20%H:%M:%S")
        path = (
            f"/class/cdm_public/CREATED/{s}--{e}"
            f"/orderby/CREATED/format/json"
        )
        if limit:
            path += f"/limit/{limit}"
        return await self._query(path)

    async def close(self) -> None:
        """Close the HTTP client session."""
        if self._client:
            await self._client.aclose()
            self._client = None

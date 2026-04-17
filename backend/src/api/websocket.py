"""WebSocket endpoint for real-time conjunction updates."""

import asyncio
import json
import logging
from datetime import datetime, timezone

from fastapi import WebSocket, WebSocketDisconnect
from sqlalchemy import select

from src.db.models import Conjunction, Satellite
from src.db.session import async_session_factory

logger = logging.getLogger(__name__)

clients: set[WebSocket] = set()


async def _fetch_latest_conjunctions(limit: int = 10) -> list[dict]:
    """Fetch latest upcoming conjunctions ordered by Pc."""
    async with async_session_factory() as session:
        now = datetime.now(timezone.utc)
        query = (
            select(Conjunction)
            .where(Conjunction.tca >= now)
            .order_by(Conjunction.pc_classical.desc().nulls_last())
            .limit(limit)
        )
        result = await session.execute(query)
        conjunctions = result.scalars().all()

        norad_ids: set[int] = set()
        for c in conjunctions:
            norad_ids.add(c.primary_norad_id)
            norad_ids.add(c.secondary_norad_id)

        names: dict[int, str | None] = {}
        if norad_ids:
            sat_q = select(Satellite.norad_id, Satellite.name).where(
                Satellite.norad_id.in_(norad_ids)
            )
            for row in (await session.execute(sat_q)).all():
                names[row[0]] = row[1]

        return [
            {
                "id": c.id,
                "primary_norad_id": c.primary_norad_id,
                "secondary_norad_id": c.secondary_norad_id,
                "primary_name": names.get(c.primary_norad_id),
                "secondary_name": names.get(c.secondary_norad_id),
                "tca": c.tca.isoformat(),
                "miss_distance_km": c.miss_distance_km,
                "pc_classical": c.pc_classical,
                "pc_ml": c.pc_ml,
            }
            for c in conjunctions
        ]


async def conjunction_websocket(websocket: WebSocket) -> None:
    """Handle a WebSocket connection for conjunction updates."""
    await websocket.accept()
    clients.add(websocket)
    logger.info("WebSocket client connected (%d total)", len(clients))

    try:
        latest = await _fetch_latest_conjunctions()
        await websocket.send_json({"type": "initial", "data": latest})

        while True:
            await asyncio.sleep(30)
            latest = await _fetch_latest_conjunctions()
            await websocket.send_json({"type": "update", "data": latest})
    except WebSocketDisconnect:
        pass
    finally:
        clients.discard(websocket)
        logger.info("WebSocket client disconnected (%d remaining)", len(clients))


async def broadcast_conjunction_update(conjunction_data: dict) -> None:
    """Broadcast a conjunction update to all connected clients."""
    message = json.dumps({"type": "new_conjunction", "data": conjunction_data})
    disconnected: set[WebSocket] = set()
    for ws in clients:
        try:
            await ws.send_text(message)
        except Exception:
            disconnected.add(ws)
    clients.difference_update(disconnected)

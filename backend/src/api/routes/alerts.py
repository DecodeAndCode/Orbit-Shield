"""CRUD /api/alerts — alert configuration management."""

import logging

import httpx
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.schemas import AlertConfigCreate, AlertConfigResponse, AlertConfigUpdate
from src.config import settings
from src.db.models import AlertConfig
from src.db.session import get_session

logger = logging.getLogger(__name__)
router = APIRouter()


async def _send_confirmation(email: str, threshold: float, watched: list[int] | None) -> None:
    """Fire-and-forget confirmation email when a new alert is configured."""
    if not settings.resend_api_key or not email:
        return
    recipient = email.strip().lower()
    watched_str = ", ".join(map(str, watched)) if watched else "all objects"
    body = (
        f"Your Orbit-Shield alert is active.\n\n"
        f"Pc threshold: {threshold:.2e}\n"
        f"Watching: {watched_str}\n\n"
        f"You'll receive an email whenever a tracked conjunction crosses the Pc threshold.\n"
        f"Conjunction screening runs every 8 hours."
    )
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {settings.resend_api_key}"},
                json={
                    "from": settings.resend_from,
                    "to": [recipient],
                    "subject": "[Orbit-Shield] Alert Configured",
                    "text": body,
                },
            )
            r.raise_for_status()
            logger.info("alert-confirm sent -> %s", recipient)
    except Exception:
        logger.exception("alert confirmation send failed for %s", recipient)


@router.get("/alerts")
async def list_alerts(
    session: AsyncSession = Depends(get_session),
) -> list[AlertConfigResponse]:
    result = await session.execute(select(AlertConfig))
    configs = result.scalars().all()
    return [AlertConfigResponse.model_validate(c) for c in configs]


@router.post("/alerts", status_code=201)
async def create_alert(
    body: AlertConfigCreate,
    session: AsyncSession = Depends(get_session),
) -> AlertConfigResponse:
    config = AlertConfig(
        watched_norad_ids=body.watched_norad_ids,
        pc_threshold=body.pc_threshold,
        notification_channels=body.notification_channels,
        enabled=body.enabled,
    )
    session.add(config)
    await session.flush()
    await session.refresh(config)
    # Send confirmation email so user gets instant feedback that alert is wired
    channels = body.notification_channels or {}
    email = channels.get("email") if isinstance(channels, dict) else None
    if email:
        await _send_confirmation(email, body.pc_threshold, body.watched_norad_ids)
    return AlertConfigResponse.model_validate(config)


@router.put("/alerts/{alert_id}")
async def update_alert(
    alert_id: int,
    body: AlertConfigUpdate,
    session: AsyncSession = Depends(get_session),
) -> AlertConfigResponse:
    result = await session.execute(
        select(AlertConfig).where(AlertConfig.id == alert_id)
    )
    config = result.scalar_one_or_none()
    if config is None:
        raise HTTPException(status_code=404, detail="Alert config not found")

    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(config, field, value)

    await session.flush()
    await session.refresh(config)
    return AlertConfigResponse.model_validate(config)


@router.delete("/alerts/{alert_id}", status_code=204)
async def delete_alert(
    alert_id: int,
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(AlertConfig).where(AlertConfig.id == alert_id)
    )
    config = result.scalar_one_or_none()
    if config is None:
        raise HTTPException(status_code=404, detail="Alert config not found")

    await session.delete(config)
    return Response(status_code=204)

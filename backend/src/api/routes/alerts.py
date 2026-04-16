"""CRUD /api/alerts — alert configuration management."""

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.schemas import AlertConfigCreate, AlertConfigResponse, AlertConfigUpdate
from src.db.models import AlertConfig
from src.db.session import get_session

router = APIRouter()


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

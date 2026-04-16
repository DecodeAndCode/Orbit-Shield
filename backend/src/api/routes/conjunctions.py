"""Conjunctions API: list and detail endpoints."""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.api.schemas import (
    CDMHistoryItem,
    ConjunctionDetailResponse,
    ConjunctionResponse,
)
from src.db.models import Conjunction, Satellite
from src.db.session import get_session

router = APIRouter()


@router.get("/conjunctions")
async def list_conjunctions(
    min_pc: float | None = Query(None, ge=0),
    hours_ahead: int = Query(72, ge=1, le=720),
    limit: int = Query(50, ge=1, le=500),
    session: AsyncSession = Depends(get_session),
) -> list[ConjunctionResponse]:
    now = datetime.now(timezone.utc)
    cutoff = now + timedelta(hours=hours_ahead)

    query = (
        select(Conjunction)
        .where(Conjunction.tca >= now, Conjunction.tca <= cutoff)
        .order_by(Conjunction.pc_classical.desc().nulls_last())
        .limit(limit)
    )

    if min_pc is not None:
        query = query.where(Conjunction.pc_classical >= min_pc)

    result = await session.execute(query)
    conjunctions = result.scalars().all()

    # Batch-load satellite names
    norad_ids = set()
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
        ConjunctionResponse(
            id=c.id,
            primary_norad_id=c.primary_norad_id,
            secondary_norad_id=c.secondary_norad_id,
            primary_name=names.get(c.primary_norad_id),
            secondary_name=names.get(c.secondary_norad_id),
            tca=c.tca,
            miss_distance_km=c.miss_distance_km,
            relative_velocity_kms=c.relative_velocity_kms,
            pc_classical=c.pc_classical,
            pc_ml=c.pc_ml,
            screening_source=c.screening_source,
            created_at=c.created_at,
        )
        for c in conjunctions
    ]


@router.get("/conjunctions/{conjunction_id}")
async def get_conjunction(
    conjunction_id: int,
    session: AsyncSession = Depends(get_session),
) -> ConjunctionDetailResponse:
    query = (
        select(Conjunction)
        .options(selectinload(Conjunction.cdm_history))
        .where(Conjunction.id == conjunction_id)
    )
    result = await session.execute(query)
    conj = result.scalar_one_or_none()

    if conj is None:
        raise HTTPException(status_code=404, detail="Conjunction not found")

    # Get satellite names
    sat_q = select(Satellite.norad_id, Satellite.name).where(
        Satellite.norad_id.in_([conj.primary_norad_id, conj.secondary_norad_id])
    )
    names = {row[0]: row[1] for row in (await session.execute(sat_q)).all()}

    return ConjunctionDetailResponse(
        id=conj.id,
        primary_norad_id=conj.primary_norad_id,
        secondary_norad_id=conj.secondary_norad_id,
        primary_name=names.get(conj.primary_norad_id),
        secondary_name=names.get(conj.secondary_norad_id),
        tca=conj.tca,
        miss_distance_km=conj.miss_distance_km,
        relative_velocity_kms=conj.relative_velocity_kms,
        pc_classical=conj.pc_classical,
        pc_ml=conj.pc_ml,
        screening_source=conj.screening_source,
        created_at=conj.created_at,
        cdm_history=[
            CDMHistoryItem(
                id=cdm.id,
                cdm_timestamp=cdm.cdm_timestamp,
                tca=cdm.tca,
                miss_distance_km=cdm.miss_distance_km,
                pc=cdm.pc,
            )
            for cdm in conj.cdm_history
        ],
    )

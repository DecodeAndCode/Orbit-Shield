"""GET /api/ml/compare/{conjunction_id} — classical vs ML Pc comparison."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.schemas import MLCompareResponse
from src.db.models import Conjunction
from src.db.session import get_session

router = APIRouter()


def _risk_label(pc: float | None) -> str:
    if pc is None:
        return "low"
    if pc >= 1e-4:
        return "high"
    elif pc >= 1e-6:
        return "medium"
    return "low"


@router.get("/ml/compare/{conjunction_id}")
async def ml_compare(
    conjunction_id: int,
    session: AsyncSession = Depends(get_session),
) -> MLCompareResponse:
    result = await session.execute(
        select(Conjunction).where(Conjunction.id == conjunction_id)
    )
    conj = result.scalar_one_or_none()

    if conj is None:
        raise HTTPException(status_code=404, detail="Conjunction not found")

    # Use the higher of classical/ML Pc for risk label
    effective_pc = max(
        conj.pc_classical or 0,
        conj.pc_ml or 0,
    ) or None

    # Confidence: how close ML and classical agree (1.0 = perfect match)
    confidence = None
    if conj.pc_classical and conj.pc_ml and conj.pc_classical > 0 and conj.pc_ml > 0:
        import math
        log_ratio = abs(math.log10(conj.pc_ml) - math.log10(conj.pc_classical))
        confidence = round(max(0.0, 1.0 - log_ratio / 3.0), 3)

    return MLCompareResponse(
        conjunction_id=conj.id,
        pc_classical=conj.pc_classical,
        pc_ml=conj.pc_ml,
        confidence=confidence,
        risk_label=_risk_label(effective_pc),
        feature_importances={},
    )

"""Persistence helpers for parsed CDMs → satellites + conjunctions + cdm_history."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from src.db.models import CDMHistory, Conjunction, Satellite
from src.ingestion.cdm_parser import ParsedCDM

logger = logging.getLogger(__name__)


def upsert_cdm(session: Session, parsed: ParsedCDM) -> tuple[int, bool]:
    """Upsert one parsed CDM into satellites / conjunctions / cdm_history.

    Returns (conjunction_id, is_new_cdm_history_row).
    """
    # 1. Ensure both satellites exist (minimal upsert — catalog task fills rest).
    for nid, name, otype, rcs in [
        (parsed.primary_norad_id, parsed.primary_name, parsed.primary_object_type, parsed.primary_rcs),
        (parsed.secondary_norad_id, parsed.secondary_name, parsed.secondary_object_type, parsed.secondary_rcs),
    ]:
        stmt = (
            pg_insert(Satellite.__table__)
            .values(norad_id=nid, name=name, object_type=otype, rcs_size=rcs)
            .on_conflict_do_update(
                index_elements=["norad_id"],
                set_={
                    "name": name or Satellite.__table__.c.name,
                    "object_type": otype or Satellite.__table__.c.object_type,
                    "rcs_size": rcs or Satellite.__table__.c.rcs_size,
                    "updated_at": datetime.now(timezone.utc),
                },
            )
        )
        session.execute(stmt)

    # 2. Upsert conjunction (primary, secondary, tca).
    conj_stmt = (
        pg_insert(Conjunction.__table__)
        .values(
            primary_norad_id=parsed.primary_norad_id,
            secondary_norad_id=parsed.secondary_norad_id,
            tca=parsed.tca,
            miss_distance_km=parsed.miss_distance_km,
            relative_velocity_kms=parsed.relative_velocity_kms,
            pc_classical=parsed.pc,
            screening_source="SPACE-TRACK-CDM",
        )
        .on_conflict_do_update(
            constraint="uq_conjunction_pair_tca",
            set_={
                "miss_distance_km": parsed.miss_distance_km,
                "relative_velocity_kms": parsed.relative_velocity_kms,
                # Keep the lowest (most recent CDM often has tighter Pc).
                "pc_classical": parsed.pc,
            },
        )
        .returning(Conjunction.__table__.c.id)
    )
    result = session.execute(conj_stmt)
    conj_id = result.scalar_one()

    # 3. Upsert cdm_history on cdm_id.
    cdm_stmt = (
        pg_insert(CDMHistory.__table__)
        .values(
            conjunction_id=conj_id,
            cdm_id=parsed.cdm_id,
            cdm_timestamp=parsed.creation_date,
            tca=parsed.tca,
            miss_distance_km=parsed.miss_distance_km,
            pc=parsed.pc,
            primary_covariance=parsed.primary_covariance or None,
            secondary_covariance=parsed.secondary_covariance or None,
            raw_cdm=parsed.raw,
        )
        .on_conflict_do_update(
            constraint="uq_cdm_history_cdm_id",
            set_={
                "miss_distance_km": parsed.miss_distance_km,
                "pc": parsed.pc,
                "primary_covariance": parsed.primary_covariance or None,
                "secondary_covariance": parsed.secondary_covariance or None,
                "raw_cdm": parsed.raw,
            },
        )
    )
    session.execute(cdm_stmt)
    return conj_id, True

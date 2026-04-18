"""Add cdm_id to cdm_history for Space-Track upserts.

Revision ID: 002
Revises: 001
Create Date: 2026-04-18
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "cdm_history",
        sa.Column("cdm_id", sa.String(length=64), nullable=True),
    )
    op.create_unique_constraint("uq_cdm_history_cdm_id", "cdm_history", ["cdm_id"])
    op.create_index(
        "ix_cdm_history_tca", "cdm_history", ["tca"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_cdm_history_tca", table_name="cdm_history")
    op.drop_constraint("uq_cdm_history_cdm_id", "cdm_history", type_="unique")
    op.drop_column("cdm_history", "cdm_id")

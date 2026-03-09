"""Initial schema.

Revision ID: 001
Revises:
Create Date: 2026-03-09
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "satellites",
        sa.Column("norad_id", sa.Integer(), autoincrement=False, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=True),
        sa.Column("object_type", sa.String(length=50), nullable=True),
        sa.Column("country", sa.String(length=100), nullable=True),
        sa.Column("launch_date", sa.Date(), nullable=True),
        sa.Column("decay_date", sa.Date(), nullable=True),
        sa.Column("rcs_size", sa.String(length=20), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("norad_id"),
    )

    op.create_table(
        "orbital_elements",
        sa.Column(
            "id", sa.BigInteger(), autoincrement=True, nullable=False
        ),
        sa.Column("norad_id", sa.Integer(), nullable=False),
        sa.Column("epoch", sa.DateTime(timezone=True), nullable=False),
        sa.Column("tle_line1", sa.Text(), nullable=True),
        sa.Column("tle_line2", sa.Text(), nullable=True),
        sa.Column("mean_motion", sa.Float(), nullable=True),
        sa.Column("eccentricity", sa.Float(), nullable=True),
        sa.Column("inclination", sa.Float(), nullable=True),
        sa.Column("raan", sa.Float(), nullable=True),
        sa.Column("arg_perigee", sa.Float(), nullable=True),
        sa.Column("mean_anomaly", sa.Float(), nullable=True),
        sa.Column("bstar", sa.Float(), nullable=True),
        sa.Column(
            "fetched_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["norad_id"], ["satellites.norad_id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("norad_id", "epoch", name="uq_orbital_element_norad_epoch"),
    )
    op.create_index(op.f("ix_orbital_elements_norad_id"), "orbital_elements", ["norad_id"])
    op.create_index(op.f("ix_orbital_elements_epoch"), "orbital_elements", ["epoch"])

    op.create_table(
        "conjunctions",
        sa.Column(
            "id", sa.BigInteger(), autoincrement=True, nullable=False
        ),
        sa.Column("primary_norad_id", sa.Integer(), nullable=False),
        sa.Column("secondary_norad_id", sa.Integer(), nullable=False),
        sa.Column("tca", sa.DateTime(timezone=True), nullable=False),
        sa.Column("miss_distance_km", sa.Float(), nullable=True),
        sa.Column("relative_velocity_kms", sa.Float(), nullable=True),
        sa.Column("pc_classical", sa.Float(), nullable=True),
        sa.Column("pc_ml", sa.Float(), nullable=True),
        sa.Column("screening_source", sa.String(length=50), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["primary_norad_id"], ["satellites.norad_id"]),
        sa.ForeignKeyConstraint(["secondary_norad_id"], ["satellites.norad_id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "primary_norad_id",
            "secondary_norad_id",
            "tca",
            name="uq_conjunction_pair_tca",
        ),
    )
    op.create_index(
        op.f("ix_conjunctions_primary_norad_id"), "conjunctions", ["primary_norad_id"]
    )
    op.create_index(
        op.f("ix_conjunctions_secondary_norad_id"),
        "conjunctions",
        ["secondary_norad_id"],
    )
    op.create_index(op.f("ix_conjunctions_tca"), "conjunctions", ["tca"])

    op.create_table(
        "cdm_history",
        sa.Column(
            "id", sa.BigInteger(), autoincrement=True, nullable=False
        ),
        sa.Column("conjunction_id", sa.BigInteger(), nullable=False),
        sa.Column("cdm_timestamp", sa.DateTime(timezone=True), nullable=True),
        sa.Column("tca", sa.DateTime(timezone=True), nullable=True),
        sa.Column("miss_distance_km", sa.Float(), nullable=True),
        sa.Column("pc", sa.Float(), nullable=True),
        sa.Column("primary_covariance", postgresql.JSONB(), nullable=True),
        sa.Column("secondary_covariance", postgresql.JSONB(), nullable=True),
        sa.Column("raw_cdm", postgresql.JSONB(), nullable=True),
        sa.ForeignKeyConstraint(["conjunction_id"], ["conjunctions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_cdm_history_conjunction_id"), "cdm_history", ["conjunction_id"]
    )

    op.create_table(
        "alert_configs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "watched_norad_ids", postgresql.ARRAY(sa.Integer()), nullable=True
        ),
        sa.Column("pc_threshold", sa.Float(), nullable=False),
        sa.Column("notification_channels", postgresql.JSONB(), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("alert_configs")
    op.drop_table("cdm_history")
    op.drop_table("conjunctions")
    op.drop_table("orbital_elements")
    op.drop_table("satellites")

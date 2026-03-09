"""SQLAlchemy ORM models for the Collider database.

Tables:
    satellites       -- Satellite catalog (NORAD objects)
    orbital_elements -- TLE/OMM orbital element history (time-series)
    conjunctions     -- Conjunction events
    cdm_history      -- Conjunction Data Message history (for ML training)
    alert_configs    -- User alert configurations
"""

from datetime import date, datetime

from sqlalchemy import (
    ARRAY,
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Satellite(Base):
    __tablename__ = "satellites"

    norad_id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=False
    )
    name: Mapped[str | None] = mapped_column(String(255))
    object_type: Mapped[str | None] = mapped_column(String(50))
    country: Mapped[str | None] = mapped_column(String(100))
    launch_date: Mapped[date | None] = mapped_column(Date)
    decay_date: Mapped[date | None] = mapped_column(Date)
    rcs_size: Mapped[str | None] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    orbital_elements: Mapped[list["OrbitalElement"]] = relationship(
        back_populates="satellite", cascade="all, delete-orphan"
    )


class OrbitalElement(Base):
    __tablename__ = "orbital_elements"
    __table_args__ = (
        UniqueConstraint("norad_id", "epoch", name="uq_orbital_element_norad_epoch"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    norad_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("satellites.norad_id"), index=True
    )
    epoch: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    tle_line1: Mapped[str | None] = mapped_column(Text)
    tle_line2: Mapped[str | None] = mapped_column(Text)
    mean_motion: Mapped[float | None] = mapped_column(Float)
    eccentricity: Mapped[float | None] = mapped_column(Float)
    inclination: Mapped[float | None] = mapped_column(Float)
    raan: Mapped[float | None] = mapped_column(Float)
    arg_perigee: Mapped[float | None] = mapped_column(Float)
    mean_anomaly: Mapped[float | None] = mapped_column(Float)
    bstar: Mapped[float | None] = mapped_column(Float)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    satellite: Mapped["Satellite"] = relationship(back_populates="orbital_elements")


class Conjunction(Base):
    __tablename__ = "conjunctions"
    __table_args__ = (
        UniqueConstraint(
            "primary_norad_id",
            "secondary_norad_id",
            "tca",
            name="uq_conjunction_pair_tca",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    primary_norad_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("satellites.norad_id"), index=True
    )
    secondary_norad_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("satellites.norad_id"), index=True
    )
    tca: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    miss_distance_km: Mapped[float | None] = mapped_column(Float)
    relative_velocity_kms: Mapped[float | None] = mapped_column(Float)
    pc_classical: Mapped[float | None] = mapped_column(Float)
    pc_ml: Mapped[float | None] = mapped_column(Float)
    screening_source: Mapped[str | None] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    primary_satellite: Mapped["Satellite"] = relationship(
        foreign_keys=[primary_norad_id]
    )
    secondary_satellite: Mapped["Satellite"] = relationship(
        foreign_keys=[secondary_norad_id]
    )
    cdm_history: Mapped[list["CDMHistory"]] = relationship(
        back_populates="conjunction", cascade="all, delete-orphan"
    )


class CDMHistory(Base):
    __tablename__ = "cdm_history"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    conjunction_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("conjunctions.id"), index=True
    )
    cdm_timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    tca: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    miss_distance_km: Mapped[float | None] = mapped_column(Float)
    pc: Mapped[float | None] = mapped_column(Float)
    primary_covariance: Mapped[dict | None] = mapped_column(JSONB)
    secondary_covariance: Mapped[dict | None] = mapped_column(JSONB)
    raw_cdm: Mapped[dict | None] = mapped_column(JSONB)

    conjunction: Mapped["Conjunction"] = relationship(back_populates="cdm_history")


class AlertConfig(Base):
    __tablename__ = "alert_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    watched_norad_ids: Mapped[list[int] | None] = mapped_column(ARRAY(Integer))
    pc_threshold: Mapped[float] = mapped_column(Float, default=1e-4)
    notification_channels: Mapped[dict | None] = mapped_column(JSONB)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)

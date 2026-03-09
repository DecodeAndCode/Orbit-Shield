"""Pydantic schemas for request/response validation."""

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class SatelliteResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    norad_id: int
    name: str | None = None
    object_type: str | None = None
    country: str | None = None
    launch_date: date | None = None
    decay_date: date | None = None
    rcs_size: str | None = None
    created_at: datetime
    updated_at: datetime


class OrbitalElementResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    norad_id: int
    epoch: datetime
    tle_line1: str | None = None
    tle_line2: str | None = None
    mean_motion: float | None = None
    eccentricity: float | None = None
    inclination: float | None = None
    raan: float | None = None
    arg_perigee: float | None = None
    mean_anomaly: float | None = None
    bstar: float | None = None
    fetched_at: datetime


class ConjunctionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    primary_norad_id: int
    secondary_norad_id: int
    tca: datetime
    miss_distance_km: float | None = None
    relative_velocity_kms: float | None = None
    pc_classical: float | None = None
    pc_ml: float | None = None
    screening_source: str | None = None
    created_at: datetime

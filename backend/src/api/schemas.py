"""Pydantic schemas for API request/response validation."""

from datetime import date, datetime

from pydantic import BaseModel, Field


class SatelliteResponse(BaseModel):
    norad_id: int
    name: str | None
    object_type: str | None
    country: str | None
    launch_date: date | None
    rcs_size: str | None
    inclination: float | None = None
    perigee_alt_km: float | None = None
    apogee_alt_km: float | None = None
    regime: str | None = None

    model_config = {"from_attributes": True}


class ConjunctionResponse(BaseModel):
    id: int
    primary_norad_id: int
    secondary_norad_id: int
    primary_name: str | None = None
    secondary_name: str | None = None
    tca: datetime
    miss_distance_km: float | None
    relative_velocity_kms: float | None
    pc_classical: float | None
    pc_ml: float | None
    screening_source: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class CDMHistoryItem(BaseModel):
    id: int
    cdm_timestamp: datetime | None
    tca: datetime | None
    miss_distance_km: float | None
    pc: float | None

    model_config = {"from_attributes": True}


class ConjunctionDetailResponse(ConjunctionResponse):
    cdm_history: list[CDMHistoryItem] = []


class PropagateRequest(BaseModel):
    norad_ids: list[int] = Field(..., min_length=1, max_length=100)
    duration_hours: float = Field(default=2.0, gt=0, le=72)
    step_minutes: float = Field(default=1.0, gt=0, le=60)


class SatellitePosition(BaseModel):
    epoch: datetime
    x_km: float
    y_km: float
    z_km: float
    lat_deg: float
    lon_deg: float
    alt_km: float


class PropagateResponse(BaseModel):
    norad_id: int
    positions: list[SatellitePosition]


class MLCompareResponse(BaseModel):
    conjunction_id: int
    pc_classical: float | None
    pc_ml: float | None
    confidence: float | None
    risk_label: str
    feature_importances: dict[str, float] = {}


class AlertConfigBase(BaseModel):
    watched_norad_ids: list[int] | None = None
    pc_threshold: float = Field(default=1e-4, gt=0, le=1)
    notification_channels: dict | None = None
    enabled: bool = True


class AlertConfigCreate(AlertConfigBase):
    pass


class AlertConfigUpdate(AlertConfigBase):
    pass


class AlertConfigResponse(AlertConfigBase):
    id: int

    model_config = {"from_attributes": True}


class PaginatedResponse(BaseModel):
    items: list
    total: int
    limit: int
    offset: int

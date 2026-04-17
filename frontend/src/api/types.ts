export interface SatelliteResponse {
  norad_id: number;
  name: string | null;
  object_type: string | null;
  country: string | null;
  launch_date: string | null;
  rcs_size: string | null;
  inclination: number | null;
  perigee_alt_km: number | null;
  apogee_alt_km: number | null;
  regime: string | null;
}

export interface ConjunctionResponse {
  id: number;
  primary_norad_id: number;
  secondary_norad_id: number;
  primary_name: string | null;
  secondary_name: string | null;
  tca: string;
  miss_distance_km: number | null;
  relative_velocity_kms: number | null;
  pc_classical: number | null;
  pc_ml: number | null;
  screening_source: string | null;
  created_at: string;
}

export interface CDMHistoryItem {
  id: number;
  cdm_timestamp: string | null;
  tca: string | null;
  miss_distance_km: number | null;
  pc: number | null;
}

export interface ConjunctionDetailResponse extends ConjunctionResponse {
  cdm_history: CDMHistoryItem[];
}

export interface SatellitePosition {
  epoch: string;
  x_km: number;
  y_km: number;
  z_km: number;
  lat_deg: number;
  lon_deg: number;
  alt_km: number;
}

export interface PropagateResponse {
  norad_id: number;
  positions: SatellitePosition[];
}

export interface MLCompareResponse {
  conjunction_id: number;
  pc_classical: number | null;
  pc_ml: number | null;
  confidence: number | null;
  risk_label: "low" | "medium" | "high";
  feature_importances: Record<string, number>;
}

export interface AlertConfigResponse {
  id: number;
  watched_norad_ids: number[] | null;
  pc_threshold: number;
  notification_channels: Record<string, string> | null;
  enabled: boolean;
}

export type RiskLevel = "low" | "medium" | "high";

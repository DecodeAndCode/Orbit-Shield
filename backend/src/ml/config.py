"""ML configuration settings."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class MLSettings(BaseSettings):
    """Configuration for ML models and inference."""

    model_config = SettingsConfigDict(
        env_prefix="ML_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    model_dir: Path = Path("models")
    ml_inference_enabled: bool = True
    covariance_model_name: str = "covariance_estimator"
    conjunction_risk_model_name: str = "conjunction_risk_classifier"
    pc_ml_confidence_threshold: float = 0.5
    maneuver_pc_threshold: float = 1e-4


ml_settings = MLSettings()

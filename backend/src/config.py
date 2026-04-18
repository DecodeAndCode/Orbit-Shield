"""Application configuration via pydantic-settings."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Database
    database_url: str = "postgresql+asyncpg://collider:collider@localhost:5432/collider"

    @property
    def database_url_sync(self) -> str:
        """Synchronous database URL for Alembic migrations."""
        return self.database_url.replace("+asyncpg", "")

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Space-Track.org
    spacetrack_username: str = ""
    spacetrack_password: str = ""
    spacetrack_base_url: str = "https://www.space-track.org"

    # CelesTrak
    celestrak_base_url: str = "https://celestrak.org"

    # NOAA Space Weather Prediction Center
    noaa_swpc_base_url: str = "https://services.swpc.noaa.gov"

    # Celery
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/1"

    # Alerts: SMTP (email)
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "alerts@collider.local"
    smtp_use_tls: bool = True

    # Alerts: default webhooks (optional global fallback)
    slack_webhook_url: str = ""
    discord_webhook_url: str = ""

    # Propagation
    propagation_step_seconds: int = 60
    propagation_window_hours: int = 72
    screening_radius_km: float = 5.0
    inclination_filter_deg: float = 15.0
    altitude_overlap_margin_km: float = 50.0


settings = Settings()

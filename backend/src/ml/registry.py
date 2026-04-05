"""Model registry for saving, loading, and listing trained models."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import joblib

from src.ml.config import ml_settings

logger = logging.getLogger(__name__)


class ModelRegistry:
    """Manages persistence and caching of trained ML models.

    Models are saved as joblib files with a companion .meta.json
    containing metadata (name, version, trained_at, metrics, feature_names).
    """

    def __init__(self, model_dir: Path | None = None) -> None:
        self.model_dir = model_dir or ml_settings.model_dir
        self.model_dir.mkdir(parents=True, exist_ok=True)
        self._cache: dict[str, Any] = {}

    def save_model(
        self,
        model: Any,
        name: str,
        metadata: dict[str, Any] | None = None,
    ) -> Path:
        """Save a model and its metadata to disk.

        Args:
            model: Trained model object (sklearn/xgboost).
            name: Model name (used as filename base).
            metadata: Optional dict of metadata (version, metrics, etc.).

        Returns:
            Path to the saved model file.
        """
        model_path = self.model_dir / f"{name}.joblib"
        meta_path = self.model_dir / f"{name}.meta.json"

        joblib.dump(model, model_path)

        meta = metadata or {}
        meta.setdefault("name", name)
        meta.setdefault("saved_at", datetime.now(timezone.utc).isoformat())
        meta_path.write_text(json.dumps(meta, indent=2, default=str))

        # Update cache
        self._cache[name] = model

        logger.info("Saved model '%s' to %s", name, model_path)
        return model_path

    def load_model(self, name: str) -> Any:
        """Load a model from disk, using cache if available.

        Args:
            name: Model name.

        Returns:
            The loaded model object.

        Raises:
            FileNotFoundError: If the model file doesn't exist.
        """
        if name in self._cache:
            return self._cache[name]

        model_path = self.model_dir / f"{name}.joblib"
        if not model_path.exists():
            raise FileNotFoundError(f"Model '{name}' not found at {model_path}")

        model = joblib.load(model_path)
        self._cache[name] = model

        logger.info("Loaded model '%s' from %s", name, model_path)
        return model

    def get_metadata(self, name: str) -> dict[str, Any]:
        """Load metadata for a model.

        Args:
            name: Model name.

        Returns:
            Metadata dict.

        Raises:
            FileNotFoundError: If the metadata file doesn't exist.
        """
        meta_path = self.model_dir / f"{name}.meta.json"
        if not meta_path.exists():
            raise FileNotFoundError(f"Metadata for '{name}' not found at {meta_path}")

        return json.loads(meta_path.read_text())

    def list_models(self) -> list[str]:
        """List all saved model names.

        Returns:
            List of model name strings.
        """
        return [
            p.stem for p in self.model_dir.glob("*.joblib")
        ]

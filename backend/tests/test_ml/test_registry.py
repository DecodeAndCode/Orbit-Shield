"""Tests for ML model registry."""

import json
from pathlib import Path

import numpy as np
import pytest
from sklearn.linear_model import LinearRegression

from src.ml.registry import ModelRegistry


@pytest.fixture
def tmp_registry(tmp_path):
    """Create a registry using a temporary directory."""
    return ModelRegistry(model_dir=tmp_path)


@pytest.fixture
def dummy_model():
    """A simple trained sklearn model."""
    model = LinearRegression()
    model.fit([[1], [2], [3]], [1, 2, 3])
    return model


class TestModelRegistry:
    def test_save_and_load(self, tmp_registry, dummy_model):
        """Model can be saved and loaded."""
        tmp_registry.save_model(dummy_model, "test_model")
        loaded = tmp_registry.load_model("test_model")
        assert isinstance(loaded, LinearRegression)
        np.testing.assert_allclose(loaded.predict([[4]]), [4.0], atol=1e-6)

    def test_save_creates_meta_json(self, tmp_registry, dummy_model):
        """save_model creates a .meta.json file."""
        tmp_registry.save_model(
            dummy_model,
            "test_model",
            metadata={"version": "1.0", "metrics": {"rmse": 0.1}},
        )
        meta_path = tmp_registry.model_dir / "test_model.meta.json"
        assert meta_path.exists()
        meta = json.loads(meta_path.read_text())
        assert meta["version"] == "1.0"
        assert meta["metrics"]["rmse"] == 0.1
        assert "saved_at" in meta

    def test_get_metadata(self, tmp_registry, dummy_model):
        """Metadata can be retrieved by name."""
        tmp_registry.save_model(
            dummy_model, "test_model", metadata={"version": "2.0"}
        )
        meta = tmp_registry.get_metadata("test_model")
        assert meta["version"] == "2.0"

    def test_load_nonexistent_raises(self, tmp_registry):
        """Loading a missing model raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            tmp_registry.load_model("does_not_exist")

    def test_metadata_nonexistent_raises(self, tmp_registry):
        """Getting metadata for missing model raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            tmp_registry.get_metadata("does_not_exist")

    def test_list_models(self, tmp_registry, dummy_model):
        """list_models returns saved model names."""
        assert tmp_registry.list_models() == []
        tmp_registry.save_model(dummy_model, "model_a")
        tmp_registry.save_model(dummy_model, "model_b")
        names = sorted(tmp_registry.list_models())
        assert names == ["model_a", "model_b"]

    def test_cache_hit(self, tmp_registry, dummy_model):
        """Second load_model call uses cache (no file read)."""
        tmp_registry.save_model(dummy_model, "cached_model")
        loaded1 = tmp_registry.load_model("cached_model")
        loaded2 = tmp_registry.load_model("cached_model")
        assert loaded1 is loaded2  # Same object from cache

    def test_save_overwrites(self, tmp_registry, dummy_model):
        """Saving with the same name overwrites the old model."""
        tmp_registry.save_model(dummy_model, "overwrite_me")

        model2 = LinearRegression()
        model2.fit([[1], [2], [3]], [10, 20, 30])
        tmp_registry.save_model(model2, "overwrite_me")

        loaded = tmp_registry.load_model("overwrite_me")
        pred = loaded.predict([[4]])[0]
        assert abs(pred - 40.0) < 1e-6

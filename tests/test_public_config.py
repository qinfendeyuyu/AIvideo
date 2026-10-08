from pathlib import Path

import pytest

from app.core import config as config_module
from app.core.config import AppConfig


def test_public_example_has_no_personal_paths():
    config = AppConfig.load("configs/models.example.yaml")
    assert config.get("llm", "model") == "qwen2.5:7b"
    assert config.get("project", "demo_mode") is False
    assert not Path(config.get("image", "local_diffusers", "model_path")).is_absolute()


def test_default_config_falls_back_only_when_private_profile_absent(tmp_path, monkeypatch):
    root = tmp_path / "checkout"
    (root / "configs").mkdir(parents=True)
    example = root / "configs/models.example.yaml"
    example.write_text("project:\n  demo_mode: false\n", encoding="utf-8")
    monkeypatch.setattr(config_module, "__file__", str(root / "app/core/config.py"))
    monkeypatch.chdir(tmp_path)
    config = AppConfig.load()
    assert config.source_path == example.resolve()
    assert config.get("project", "demo_mode") is False
    private = root / "configs/models.yaml"
    private.write_text("project:\n  seed: 123\n", encoding="utf-8")
    assert AppConfig.load().get("project", "seed") == 123


def test_explicit_missing_config_is_not_silently_replaced(tmp_path):
    with pytest.raises(FileNotFoundError):
        AppConfig.load(str(tmp_path / "not_found.yaml"))

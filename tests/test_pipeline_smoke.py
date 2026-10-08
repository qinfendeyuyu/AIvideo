from app.core.config import AppConfig


def test_config_load() -> None:
    config = AppConfig.load("configs/models.yaml")
    assert config.get("llm", "model") == "qwen2.5:7b"
    assert config.get("image", "backend") == "local_diffusers"
    assert config.get("tts", "backend") == "powershell_sapi"
    assert config.get("video", "backend") == "sadtalker"
    assert config.get("project", "max_scene_count") > 0
    assert (config.get("project", "width"), config.get("project", "height")) == (768, 432)
    assert config.get("project", "demo_mode") is False

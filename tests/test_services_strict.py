import asyncio
from pathlib import Path

import pytest

from app.core.config import AppConfig
from app.services.image_service import ImageService
from app.services.llm_service import LLMService
from app.services.tts_service import TTSService


def config(tmp_path: Path) -> AppConfig:
    path = tmp_path / "configs" / "models.yaml"
    path.parent.mkdir(parents=True)
    path.write_text("project: {}\n", encoding="utf-8")
    return AppConfig(
        source_path=path,
        raw={
            "project": {"demo_mode": False},
            "llm": {"base_url": "", "model": ""},
            "image": {"base_url": "", "txt2img_path": ""},
            "tts": {"base_url": "", "synthesize_path": ""},
        },
    )


def test_real_mode_never_silently_creates_placeholder_assets(tmp_path: Path) -> None:
    app_config = config(tmp_path)
    with pytest.raises(RuntimeError, match="llm.base_url"):
        asyncio.run(
            LLMService(app_config).plan_episode(
                title="测试", premise="足够长的严谨剧情设定文本。", style_prompt="cinematic comic", max_scene_count=1, characters=[]
            )
        )
    with pytest.raises(RuntimeError, match="image.base_url"):
        asyncio.run(
            ImageService(app_config).render_scene(
                "cinematic comic scene", tmp_path / "image.png", width=32, height=32, seed=1
            )
        )
    with pytest.raises(RuntimeError, match="tts.base_url"):
        asyncio.run(TTSService(app_config).synthesize("旁白", tmp_path / "audio.wav"))
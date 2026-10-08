import asyncio
import json
from pathlib import Path

from app.core.config import AppConfig
from app.pipeline.episode_pipeline import EpisodePipeline
from app.schemas.project import EpisodeRequest


def demo_config(tmp_path: Path) -> AppConfig:
    config_path = tmp_path / "configs" / "models.yaml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text("project: {}\n", encoding="utf-8")
    return AppConfig(
        source_path=config_path,
        raw={
            "project": {
                "output_root": "outputs",
                "demo_mode": True,
                "max_scene_count": 2,
                "width": 320,
                "height": 180,
                "fps": 8,
                "seed": 42,
            },
            "llm": {"base_url": "http://127.0.0.1:1/v1", "model": "offline"},
            "image": {"base_url": "http://127.0.0.1:1", "txt2img_path": "/txt2img"},
            "tts": {"base_url": "http://127.0.0.1:1", "synthesize_path": "/synthesize"},
            "video": {"ffmpeg_bin": "ffmpeg", "ffprobe_bin": "ffprobe", "preset": "ultrafast", "crf": 28, "burn_subtitles": True},
        },
    )


def test_demo_pipeline_creates_resumable_episode(tmp_path: Path) -> None:
    request = EpisodeRequest(
        title="测试集",
        premise="一名年轻调查员在雨夜发现城市记忆正被未知裂缝吞噬。",
        run_id="smoke_demo_001",
        seed=100,
    )
    pipeline = EpisodePipeline(demo_config(tmp_path))
    result = asyncio.run(pipeline.run(request))

    video = Path(result.output_video)
    manifest = Path(result.manifest_file)
    subtitles = Path(result.subtitle_file or "")
    assert video.is_file() and video.stat().st_size > 10_000
    assert manifest.is_file()
    assert subtitles.is_file()
    saved = json.loads(manifest.read_text(encoding="utf-8"))
    assert saved["status"] == "completed"
    assert saved["artifacts"]["episode_video"] == "episode.mp4"
    assert len(saved["scenes"]) == 2
    assert "local-key" not in manifest.read_text(encoding="utf-8")

    resumed = request.model_copy(update={"resume": True})
    resumed_result = asyncio.run(EpisodePipeline(demo_config(tmp_path)).run(resumed))
    assert resumed_result.output_video == result.output_video
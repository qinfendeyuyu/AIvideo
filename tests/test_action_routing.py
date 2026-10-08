from pathlib import Path

import pytest

from app.core.config import AppConfig
from app.schemas.project import Scene
from app.services.video_service import VideoService


def test_scene_keeps_action_direction_and_hybrid_selects_the_right_backend(tmp_path: Path) -> None:
    config_path = tmp_path / "configs" / "models.yaml"
    config_path.parent.mkdir(parents=True)
    config_path.write_text("project: {}\n", encoding="utf-8")
    config = AppConfig(
        source_path=config_path,
        raw={
            "project": {"fps": 12, "width": 768, "height": 432},
            "video": {
                "backend": "hybrid",
                "hybrid": {"dialogue_backend": "sadtalker", "action_backend": "wan"},
            },
        },
    )
    scene = Scene(
        index=1,
        visual_prompt="full-body hero in an alley at night, cinematic lighting",
        narration="她侧身躲开攻击。",
        motion_kind="action",
        motion_prompt="hero dodges left, then counterattacks, handheld tracking camera",
    )

    service = VideoService(config)
    assert service.motion_enabled is True
    assert service._motion_backend_for("dialogue") == "sadtalker"
    assert service._motion_backend_for(scene.motion_kind) == "wan"
    assert scene.motion_prompt.startswith("hero dodges")


def test_wan_action_never_falls_back_to_a_static_or_talking_head_clip(tmp_path: Path) -> None:
    config_path = tmp_path / "configs" / "models.yaml"
    config_path.parent.mkdir(parents=True)
    config_path.write_text("project: {}\n", encoding="utf-8")
    config = AppConfig(
        source_path=config_path,
        raw={
            "project": {"fps": 12, "width": 768, "height": 432},
            "video": {"backend": "wan", "wan": {"model_path": "missing-wan-model"}},
        },
    )

    with pytest.raises(RuntimeError, match="Wan action backend is not ready"):
        VideoService(config).render_motion(
            tmp_path / "unused.png",
            "full-body heroine walks forward",
            tmp_path / "action.mp4",
            audio_file=tmp_path / "unused.wav",
            seed=7,
            motion_kind="action",
            motion_prompt="tracking camera pushes in",
        )


def test_vace_action_requires_local_reference_model_instead_of_falling_back(tmp_path: Path) -> None:
    config_path = tmp_path / "configs" / "models.yaml"
    config_path.parent.mkdir(parents=True)
    config_path.write_text("project: {}\n", encoding="utf-8")
    config = AppConfig(
        source_path=config_path,
        raw={
            "project": {"fps": 12, "width": 768, "height": 432},
            "video": {"backend": "vace", "vace": {"model_path": "missing-vace-model"}},
        },
    )

    with pytest.raises(RuntimeError, match="VACE reference action backend is not ready"):
        VideoService(config).render_motion(
            tmp_path / "unused.png",
            "full-body heroine walks forward",
            tmp_path / "action.mp4",
            audio_file=tmp_path / "unused.wav",
            seed=7,
            motion_kind="action",
            motion_prompt="tracking camera pulls back",
        )

from __future__ import annotations

import json
import secrets
from asyncio import to_thread
from datetime import datetime
from pathlib import Path

from PIL import Image

from app.core.config import AppConfig
from app.core.run_store import RunStore
from app.schemas.project import EpisodePlan, EpisodeRequest, EpisodeResult, Scene
from app.services.image_service import ImageService
from app.services.llm_service import LLMService
from app.services.tts_service import TTSService
from app.services.video_service import VideoService


class EpisodePipeline:
    """A local, restartable episode-production pipeline.

    A run is a directory containing prompts, rendered assets, subtitles and a manifest.
    Existing valid assets are reused only when ``resume`` is explicit.
    """

    def __init__(self, config: AppConfig):
        self.config = config
        self.llm = LLMService(config)
        self.image = ImageService(config)
        self.tts = TTSService(config)
        self.video = VideoService(config)

    @staticmethod
    def _new_run_id() -> str:
        return f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{secrets.token_hex(3)}"

    @staticmethod
    def _valid_image(path: Path) -> bool:
        if not path.exists() or path.stat().st_size == 0:
            return False
        try:
            with Image.open(path) as image:
                image.verify()
            return True
        except (OSError, ValueError):
            return False

    def _valid_media(self, path: Path) -> bool:
        if not path.exists() or path.stat().st_size == 0:
            return False
        try:
            return self.video.media_duration(path) > 0
        except RuntimeError:
            return False

    @staticmethod
    def _character_prompt(request: EpisodeRequest) -> str:
        # The scene prompt itself has the active character's appearance. Appending
        # every character here exhausts SD 1.x's short text-encoder context.
        return ""

    @staticmethod
    def _read_plan(plan_file: Path) -> EpisodePlan:
        try:
            payload = json.loads(plan_file.read_text(encoding="utf-8"))
            return EpisodePlan.model_validate(payload)
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            raise RuntimeError(f"Saved storyboard is invalid: {plan_file}: {exc}") from exc

    @staticmethod
    def _write_json(path: Path, payload: dict) -> None:
        temp_path = path.with_suffix(path.suffix + ".tmp")
        temp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        temp_path.replace(path)

    def _open_run(self, request: EpisodeRequest) -> tuple[str, Path, RunStore]:
        output_root = self.config.resolve_path(
            self.config.get("project", "output_root", default="data/outputs")
        )
        output_root.mkdir(parents=True, exist_ok=True)
        if request.resume and not request.run_id:
            raise ValueError("resume requires an explicit run_id")
        run_id = request.run_id or self._new_run_id()
        run_dir = output_root / run_id

        if run_dir.exists():
            if not request.resume:
                raise FileExistsError(
                    f"Run directory already exists: {run_dir}. Use the same run_id with resume=true to continue."
                )
            store = RunStore.open(run_dir)
            recorded = store.manifest.get("request", {})
            if recorded.get("title") != request.title or recorded.get("premise") != request.premise:
                raise ValueError("Resume request title/premise do not match the existing run manifest")
            return run_id, run_dir, store

        run_dir.mkdir(parents=True)
        initial = {
            "schema_version": 1,
            "run_id": run_id,
            "status": "planning",
            "request": request.model_dump(mode="json"),
            "config": self.config.public_snapshot(),
            "artifacts": {},
            "scenes": {},
        }
        return run_id, run_dir, RunStore.create(run_dir, initial)

    async def run(self, request: EpisodeRequest) -> EpisodeResult:
        max_scene_count = int(self.config.get("project", "max_scene_count", default=8))
        width = int(self.config.get("project", "width", default=1024))
        height = int(self.config.get("project", "height", default=576))
        base_seed = request.seed
        if base_seed is None:
            configured_seed = self.config.get("project", "seed", default=None)
            base_seed = int(configured_seed) if configured_seed is not None else None

        run_id, run_dir, store = self._open_run(request)
        images_dir = run_dir / "images"
        audio_dir = run_dir / "audio"
        clips_dir = run_dir / "clips"
        for directory in (images_dir, audio_dir, clips_dir):
            directory.mkdir(parents=True, exist_ok=True)
        plan_file = run_dir / "storyboard.json"
        subtitle_file = run_dir / "subtitles.srt"
        master_file = run_dir / "episode_master.mp4"
        output_video = run_dir / "episode.mp4"

        try:
            if plan_file.exists():
                plan = self._read_plan(plan_file)
                if len(plan.scenes) != max_scene_count:
                    raise RuntimeError(
                        f"Saved storyboard has {len(plan.scenes)} scenes but config requires {max_scene_count}"
                    )
            else:
                plan = await self.llm.plan_episode(
                    title=request.title,
                    premise=request.premise,
                    style_prompt=request.style_prompt,
                    max_scene_count=max_scene_count,
                    characters=request.characters,
                )
                self._write_json(plan_file, plan.model_dump(mode="json"))
            store.manifest["artifacts"]["storyboard"] = plan_file.name
            store.set_status("rendering")

            scene_videos: list[Path] = []
            subtitle_cues: list[tuple[float, float, str]] = []
            cursor = 0.0
            character_prompt = self._character_prompt(request)

            for scene in sorted(plan.scenes, key=lambda item: item.index):
                image_file = images_dir / f"scene_{scene.index:02d}.png"
                audio_file = audio_dir / f"scene_{scene.index:02d}.wav"
                motion_file = clips_dir / f"motion_{scene.index:02d}.mp4"
                clip_file = clips_dir / f"scene_{scene.index:02d}.mp4"
                scene_seed = base_seed + scene.index if base_seed is not None else None
                full_prompt = f"{request.style_prompt}, {scene.visual_prompt}{character_prompt}"
                store.update_scene(
                    scene.index,
                    status="rendering",
                    visual_prompt=scene.visual_prompt,
                    narration=scene.narration,
                    camera=scene.camera,
                    motion_kind=scene.motion_kind,
                    motion_prompt=scene.motion_prompt,
                    seed=scene_seed,
                )

                if not self._valid_image(image_file):
                    await self.image.render_scene(
                        full_prompt,
                        image_file,
                        width=width,
                        height=height,
                        seed=scene_seed,
                    )
                    if not self._valid_image(image_file):
                        raise RuntimeError(f"Image output is invalid after render: {image_file}")

                if not self._valid_media(audio_file):
                    await self.tts.synthesize(scene.narration, audio_file)
                    if not self._valid_media(audio_file):
                        raise RuntimeError(f"Audio output is invalid after synthesis: {audio_file}")

                if self.video.motion_enabled:
                    if not self._valid_media(motion_file):
                        await to_thread(
                            self.video.render_motion,
                            image_file,
                            full_prompt,
                            motion_file,
                            audio_file=audio_file,
                            seed=scene_seed,
                            motion_kind=scene.motion_kind,
                            motion_prompt=scene.motion_prompt,
                        )
                    if not self._valid_media(motion_file):
                        raise RuntimeError(f"Motion output is invalid after render: {motion_file}")
                    if not self._valid_media(clip_file):
                        duration = self.video.stitch_motion_scene(motion_file, audio_file, clip_file)
                    else:
                        duration = self.video.media_duration(clip_file)
                else:
                    if not self._valid_media(clip_file):
                        duration = self.video.stitch_scene(image_file, audio_file, clip_file)
                    else:
                        duration = self.video.media_duration(clip_file)

                scene_videos.append(clip_file)
                subtitle_cues.append((cursor, cursor + duration, scene.narration))
                cursor += duration
                store.update_scene(
                    scene.index,
                    status="completed",
                    image=str(image_file.relative_to(run_dir)),
                    audio=str(audio_file.relative_to(run_dir)),
                    clip=str(clip_file.relative_to(run_dir)),
                    motion=(str(motion_file.relative_to(run_dir)) if self.video.motion_enabled else None),
                    motion_kind=scene.motion_kind,
                    motion_prompt=scene.motion_prompt,
                    duration_seconds=round(duration, 3),
                )

            if not self._valid_media(master_file):
                self.video.concat_scenes(scene_videos, master_file)
            self.video.write_subtitles(subtitle_cues, subtitle_file)

            subtitles_enabled = bool(self.config.get("video", "burn_subtitles", default=True))
            if subtitles_enabled:
                if not self._valid_media(output_video):
                    self.video.burn_subtitles(master_file, subtitle_file, output_video)
            else:
                output_video = master_file

            if not self._valid_media(output_video):
                raise RuntimeError(f"Final video is invalid: {output_video}")

            store.manifest["artifacts"].update(
                {
                    "subtitle": subtitle_file.name,
                    "master_video": master_file.name,
                    "episode_video": output_video.name,
                    "duration_seconds": round(self.video.media_duration(output_video), 3),
                }
            )
            store.set_status("completed")
            return EpisodeResult(
                title=plan.title,
                scene_count=len(plan.scenes),
                output_video=str(output_video.resolve()),
                output_dir=str(run_dir.resolve()),
                manifest_file=str(store.path.resolve()),
                subtitle_file=str(subtitle_file.resolve()),
                status="completed",
            )
        except Exception as exc:
            store.set_status("failed", error=f"{type(exc).__name__}: {exc}")
            raise

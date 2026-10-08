from __future__ import annotations

import json
import math
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Iterable

from app.core.config import AppConfig


class VideoService:
    def __init__(self, config: AppConfig):
        self.backend = str(config.get("video", "backend", default="static"))
        self.demo_mode = bool(config.get("project", "demo_mode", default=False))
        self.ffmpeg_bin = str(config.get("video", "ffmpeg_bin", default="ffmpeg"))
        self.ffprobe_bin = str(config.get("video", "ffprobe_bin", default="ffprobe"))
        self.crf = int(config.get("video", "crf", default=18))
        self.preset = str(config.get("video", "preset", default="slow"))
        if self.demo_mode:
            # Diagnostic packs prioritize turnaround over encode quality.
            self.preset = "ultrafast"
            self.crf = max(self.crf, 28)
        self.pix_fmt = str(config.get("video", "pix_fmt", default="yuv420p"))
        self.fps = int(config.get("project", "fps", default=12))
        self.width = int(config.get("project", "width", default=1024))
        self.height = int(config.get("project", "height", default=576))
        self.motion_python = str(config.get("video", "animatediff", "python_bin", default=""))
        self.motion_base_model = config.resolve_path(
            config.get("video", "animatediff", "base_model_path", default="")
        )
        self.motion_adapter = config.resolve_path(
            config.get("video", "animatediff", "motion_adapter_path", default="models/animatediff/motion_adapter")
        )
        self.motion_ip_adapter = config.resolve_path(
            config.get("video", "animatediff", "ip_adapter_path", default="models/animatediff/ip_adapter")
        )
        self.motion_worker = config.resolve_path(
            config.get("video", "animatediff", "worker_path", default="app/workers/animatediff_worker.py")
        )
        self.motion_timeout = float(config.get("video", "animatediff", "timeout_seconds", default=1800))
        self.motion_width = int(config.get("video", "animatediff", "width", default=512))
        self.motion_height = int(config.get("video", "animatediff", "height", default=288))
        self.motion_fps = int(config.get("video", "animatediff", "fps", default=8))
        self.motion_frames = int(config.get("video", "animatediff", "num_frames", default=16))
        self.motion_steps = int(config.get("video", "animatediff", "steps", default=20))
        self.motion_guidance = float(config.get("video", "animatediff", "guidance_scale", default=7.0))
        self.motion_ip_scale = float(config.get("video", "animatediff", "ip_adapter_scale", default=0.65))
        self.motion_reference_mode = bool(
            config.get("video", "animatediff", "reference_mode", default=False)
        )
        self.motion_cpu_offload = bool(
            config.get("video", "animatediff", "cpu_offload", default=True)
        )
        self.motion_negative = str(config.get("video", "animatediff", "negative_prompt", default=""))
        self.motion_suffix = str(config.get("video", "animatediff", "prompt_suffix", default=""))
        self.hybrid_dialogue_backend = str(
            config.get("video", "hybrid", "dialogue_backend", default="sadtalker")
        )
        self.hybrid_action_backend = str(
            config.get("video", "hybrid", "action_backend", default="wan")
        )
        self.wan_python = config.resolve_path(
            config.get("video", "wan", "python_bin", default=".venv-wan/Scripts/python.exe")
        )
        self.wan_model_path = config.resolve_path(
            config.get("video", "wan", "model_path", default="models/wan/t2v_1.3b")
        )
        self.wan_worker = config.resolve_path(
            config.get("video", "wan", "worker_path", default="app/workers/wan_worker.py")
        )
        self.wan_width = int(config.get("video", "wan", "width", default=640))
        self.wan_height = int(config.get("video", "wan", "height", default=352))
        self.wan_fps = int(config.get("video", "wan", "fps", default=15))
        self.wan_frames = int(config.get("video", "wan", "num_frames", default=33))
        self.wan_steps = int(config.get("video", "wan", "steps", default=30))
        self.wan_guidance = float(config.get("video", "wan", "guidance_scale", default=5.0))
        self.wan_flow_shift = float(config.get("video", "wan", "flow_shift", default=3.0))
        self.wan_offload_mode = str(config.get("video", "wan", "offload_mode", default="sequential"))
        self.wan_gpu_memory_limit = str(
            config.get("video", "wan", "gpu_memory_limit", default="7GiB")
        )
        self.wan_cpu_memory_limit = str(
            config.get("video", "wan", "cpu_memory_limit", default="14GiB")
        )
        self.wan_vae_tiling = bool(config.get("video", "wan", "vae_tiling", default=False))
        self.wan_temporal_output_scale = int(
            config.get("video", "wan", "temporal_output_scale", default=1)
        )
        self.wan_max_sequence_length = int(
            config.get("video", "wan", "max_sequence_length", default=512)
        )
        self.wan_timeout = float(config.get("video", "wan", "timeout_seconds", default=10800))
        self.wan_negative = str(config.get("video", "wan", "negative_prompt", default=""))
        self.wan_suffix = str(config.get("video", "wan", "prompt_suffix", default=""))
        self.vace_python = config.resolve_path(
            config.get("video", "vace", "python_bin", default=".venv-vace/Scripts/python.exe")
        )
        self.vace_source_root = config.resolve_path(
            config.get("video", "vace", "source_root", default="third_party/Wan2.1")
        )
        self.vace_model_path = config.resolve_path(
            config.get("video", "vace", "model_path", default="models/vace/1.3b")
        )
        self.vace_worker = config.resolve_path(
            config.get("video", "vace", "worker_path", default="app/workers/vace_worker.py")
        )
        self.vace_width = int(config.get("video", "vace", "width", default=480))
        self.vace_height = int(config.get("video", "vace", "height", default=832))
        self.vace_fps = int(config.get("video", "vace", "fps", default=16))
        self.vace_frames = int(config.get("video", "vace", "num_frames", default=33))
        self.vace_steps = int(config.get("video", "vace", "steps", default=50))
        self.vace_guidance = float(config.get("video", "vace", "guidance_scale", default=5.0))
        self.vace_flow_shift = float(config.get("video", "vace", "flow_shift", default=16.0))
        self.vace_timeout = float(config.get("video", "vace", "timeout_seconds", default=21600))
        self.vace_suffix = str(config.get("video", "vace", "prompt_suffix", default=""))
        self.sadtalker_root = config.resolve_path(
            config.get("video", "sadtalker", "root_path", default="E:/SadTalker")
        )
        self.sadtalker_python = config.resolve_path(
            config.get("video", "sadtalker", "python_bin", default="E:/SadTalker/venv/Scripts/python.exe")
        )
        self.sadtalker_script = config.resolve_path(
            config.get("video", "sadtalker", "inference_script", default="E:/SadTalker/inference.py")
        )
        self.sadtalker_stage_root = config.resolve_path(
            config.get("video", "sadtalker", "stage_root", default="E:/SadTalker/results/ai_comic_drama")
        )
        self.sadtalker_timeout = float(config.get("video", "sadtalker", "timeout_seconds", default=1800))
        self.sadtalker_size = int(config.get("video", "sadtalker", "size", default=256))
        self.sadtalker_batch_size = int(config.get("video", "sadtalker", "batch_size", default=1))
        self.sadtalker_expression_scale = float(
            config.get("video", "sadtalker", "expression_scale", default=0.8)
        )
        self.sadtalker_preprocess = str(config.get("video", "sadtalker", "preprocess", default="full"))
        self.sadtalker_fallback_preprocess = str(
            config.get("video", "sadtalker", "fallback_preprocess", default="crop")
        )
        self.sadtalker_chunk_seconds = float(
            config.get("video", "sadtalker", "chunk_seconds", default=2.4)
        )

    @property
    def motion_enabled(self) -> bool:
        # Offline diagnostic runs must never invoke SadTalker / Wan / VACE workers.
        if self.demo_mode:
            return False
        return self.backend in {"animatediff", "sadtalker", "wan", "vace", "hybrid"}

    def _motion_backend_for(self, motion_kind: str) -> str:
        """Select the renderer without turning action shots into fake dialogue."""
        if self.backend != "hybrid":
            return self.backend
        if motion_kind == "dialogue":
            return self.hybrid_dialogue_backend
        if motion_kind == "action":
            return self.hybrid_action_backend
        raise ValueError(f"Unsupported motion kind: {motion_kind}")

    @staticmethod
    def _text(value: bytes | str | None) -> str:
        if isinstance(value, bytes):
            return value.decode("utf-8", errors="replace")
        return value or ""

    def _run(self, command: list[str], operation: str) -> None:
        try:
            completed = subprocess.run(command, check=True, capture_output=True)
        except FileNotFoundError as exc:
            raise RuntimeError(f"{operation} failed: executable not found: {command[0]}") from exc
        except subprocess.CalledProcessError as exc:
            detail = self._text(exc.stderr or exc.stdout).strip()[-3000:] or "unknown ffmpeg error"
            raise RuntimeError(f"{operation} failed: {detail}") from exc
        if completed.returncode != 0:
            raise RuntimeError(f"{operation} failed with exit code {completed.returncode}")

    def media_duration(self, media_file: Path) -> float:
        command = [
            self.ffprobe_bin,
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(media_file),
        ]
        try:
            completed = subprocess.run(command, check=True, capture_output=True)
            duration = float(self._text(completed.stdout).strip())
        except (FileNotFoundError, subprocess.CalledProcessError, ValueError) as exc:
            raise RuntimeError(f"Cannot read media duration for {media_file}: {exc}") from exc
        if duration <= 0:
            raise RuntimeError(f"Invalid non-positive media duration for {media_file}: {duration}")
        return duration

    def stitch_scene(self, image_file: Path, audio_file: Path, out_file: Path) -> float:
        """Create a constant-specification clip whose exact length follows the narration."""
        duration = self.media_duration(audio_file)
        vf = (
            f"scale={self.width}:{self.height}:force_original_aspect_ratio=decrease,"
            f"pad={self.width}:{self.height}:(ow-iw)/2:(oh-ih)/2,setsar=1"
        )
        command = [
            self.ffmpeg_bin, "-y",
            "-loop", "1", "-framerate", str(self.fps), "-i", str(image_file),
            "-i", str(audio_file),
            "-t", f"{duration:.3f}",
            "-vf", vf,
            "-map", "0:v:0", "-map", "1:a:0",
            "-r", str(self.fps),
            "-c:v", "libx264", "-preset", self.preset, "-crf", str(self.crf),
            "-c:a", "aac", "-b:a", "192k", "-pix_fmt", self.pix_fmt,
            "-shortest", "-movflags", "+faststart", str(out_file),
        ]
        self._run(command, f"scene video render ({out_file.name})")
        return self.media_duration(out_file)

    def render_motion(
        self,
        image_file: Path,
        prompt: str,
        out_file: Path,
        *,
        audio_file: Path,
        seed: int | None,
        motion_kind: str = "dialogue",
        motion_prompt: str = "",
    ) -> None:
        """Render a real image-to-video shot with a separate low-VRAM worker."""
        backend = self._motion_backend_for(motion_kind)
        if backend == "sadtalker":
            self._render_sadtalker(image_file, audio_file, out_file)
            return
        if backend == "wan":
            self._render_wan(prompt, motion_prompt, out_file, seed=seed)
            return
        if backend == "vace":
            self._render_vace(image_file, prompt, motion_prompt, out_file, seed=seed)
            return
        if not self.motion_enabled:
            raise RuntimeError("render_motion called while video.backend has no motion renderer")
        if backend != "animatediff":
            raise RuntimeError(f"Unsupported motion backend: {backend}")
        paths = {
            "video.animatediff.python_bin": Path(self.motion_python),
            "video.animatediff.base_model_path": self.motion_base_model,
            "video.animatediff.motion_adapter_path": self.motion_adapter,
            "video.animatediff.worker_path": self.motion_worker,
        }
        if self.motion_reference_mode:
            paths["video.animatediff.ip_adapter_path"] = self.motion_ip_adapter
            paths["source image"] = image_file
        missing = [f"{label} ({path})" for label, path in paths.items() if not path.exists()]
        if missing:
            raise RuntimeError("AnimateDiff motion backend is not ready: " + "; ".join(missing))
        if self.motion_width % 8 or self.motion_height % 8:
            raise RuntimeError("video.animatediff.width and height must be multiples of 8")
        if self.motion_frames < 8:
            raise RuntimeError("video.animatediff.num_frames must be at least 8")

        out_file.parent.mkdir(parents=True, exist_ok=True)
        request_file = out_file.with_suffix(".animatediff_request.json")
        result_file = out_file.with_suffix(".animatediff_result.json")
        directed_prompt = ", ".join(piece for piece in (prompt, motion_prompt) if piece)
        render_prompt = ", ".join(piece for piece in (directed_prompt, self.motion_suffix) if piece)
        request = {
            "base_model_path": str(self.motion_base_model),
            "motion_adapter_path": str(self.motion_adapter),
            "ip_adapter_path": str(self.motion_ip_adapter),
            "source_image": str(image_file.resolve()),
            "output_path": str(out_file.resolve()),
            "prompt": render_prompt,
            "negative_prompt": self.motion_negative,
            "width": self.motion_width,
            "height": self.motion_height,
            "fps": self.motion_fps,
            "num_frames": self.motion_frames,
            "steps": self.motion_steps,
            "guidance_scale": self.motion_guidance,
            "ip_adapter_scale": self.motion_ip_scale,
            "reference_mode": self.motion_reference_mode,
            "cpu_offload": self.motion_cpu_offload,
            "seed": seed,
            "motion_kind": motion_kind,
            "dtype": "float16",
        }
        request_file.write_text(json.dumps(request, ensure_ascii=False), encoding="utf-8")
        command = [
            self.motion_python,
            str(self.motion_worker),
            "--request",
            str(request_file),
            "--result",
            str(result_file),
        ]
        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                check=False,
                timeout=self.motion_timeout,
            )
            result = json.loads(result_file.read_text(encoding="utf-8")) if result_file.exists() else {}
            if completed.returncode != 0 or not result.get("ok"):
                detail = result.get("error") or self._text(completed.stderr)[-2000:]
                raise RuntimeError(f"AnimateDiff motion render failed: {detail}")
            if self.media_duration(out_file) <= 0:
                raise RuntimeError(f"AnimateDiff wrote an invalid motion clip: {out_file}")
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(f"AnimateDiff motion render timed out after {self.motion_timeout:.0f}s") from exc
        finally:
            request_file.unlink(missing_ok=True)
            result_file.unlink(missing_ok=True)

    def _render_wan(
        self,
        prompt: str,
        motion_prompt: str,
        out_file: Path,
        *,
        seed: int | None,
    ) -> None:
        """Render a text-to-video action shot with Wan in an isolated process.

        Wan 1.3B is used only for broad action shots in hybrid mode. Dialogue
        close-ups stay on SadTalker to preserve the generated character face.
        """
        required = {
            "video.wan.python_bin": self.wan_python,
            "video.wan.worker_path": self.wan_worker,
            "video.wan.model_index": self.wan_model_path / "model_index.json",
            "video.wan.text_encoder": self.wan_model_path / "text_encoder" / "model.safetensors.index.json",
            "video.wan.transformer": self.wan_model_path / "transformer" / "diffusion_pytorch_model.safetensors.index.json",
            "video.wan.vae": self.wan_model_path / "vae" / "diffusion_pytorch_model.safetensors",
        }
        missing = [f"{label} ({path})" for label, path in required.items() if not path.is_file()]
        if missing:
            raise RuntimeError(
                "Wan action backend is not ready; resume the model download first: " + "; ".join(missing)
            )
        if self.wan_width % 16 or self.wan_height % 16:
            raise RuntimeError("video.wan.width and height must be multiples of 16")
        if self.wan_frames < 5 or (self.wan_frames - 1) % 4:
            raise RuntimeError("video.wan.num_frames must use the form 4*k+1")
        if self.wan_temporal_output_scale < 1:
            raise RuntimeError("video.wan.temporal_output_scale must be at least 1")
        if self.wan_offload_mode not in {"sequential", "model", "balanced", "none"}:
            raise RuntimeError("video.wan.offload_mode must be sequential, model, balanced or none")

        directed_prompt = ", ".join(piece.strip() for piece in (prompt, motion_prompt, self.wan_suffix) if piece.strip())
        if not directed_prompt:
            raise RuntimeError("Wan action prompt is empty")
        out_file.parent.mkdir(parents=True, exist_ok=True)
        request_file = out_file.with_suffix(".wan_request.json")
        result_file = out_file.with_suffix(".wan_result.json")
        request = {
            "model_path": str(self.wan_model_path),
            "output_path": str(out_file.resolve()),
            "prompt": directed_prompt,
            "negative_prompt": self.wan_negative,
            "width": self.wan_width,
            "height": self.wan_height,
            "fps": self.wan_fps,
            "num_frames": self.wan_frames,
            "steps": self.wan_steps,
            "guidance_scale": self.wan_guidance,
            "flow_shift": self.wan_flow_shift,
            "offload_mode": self.wan_offload_mode,
            "gpu_memory_limit": self.wan_gpu_memory_limit,
            "cpu_memory_limit": self.wan_cpu_memory_limit,
            "vae_tiling": self.wan_vae_tiling,
            "temporal_output_scale": self.wan_temporal_output_scale,
            "max_sequence_length": self.wan_max_sequence_length,
            "seed": seed,
        }
        request_file.write_text(json.dumps(request, ensure_ascii=False), encoding="utf-8")
        command = [
            str(self.wan_python),
            str(self.wan_worker),
            "--request",
            str(request_file),
            "--result",
            str(result_file),
        ]
        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                check=False,
                timeout=self.wan_timeout,
            )
            result = json.loads(result_file.read_text(encoding="utf-8")) if result_file.exists() else {}
            if completed.returncode != 0 or not result.get("ok"):
                detail = result.get("error") or self._text(completed.stderr)[-2000:]
                raise RuntimeError(f"Wan action render failed: {detail}")
            if self.media_duration(out_file) <= 0:
                raise RuntimeError(f"Wan wrote an invalid action clip: {out_file}")
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(f"Wan action render timed out after {self.wan_timeout:.0f}s") from exc
        finally:
            request_file.unlink(missing_ok=True)
            result_file.unlink(missing_ok=True)

    def _render_vace(
        self,
        image_file: Path,
        prompt: str,
        motion_prompt: str,
        out_file: Path,
        *,
        seed: int | None,
    ) -> None:
        """Render a reference-locked action shot with the official Wan VACE source.

        Unlike the earlier text-only Wan backend, VACE receives the rendered
        scene image as its reference input, which is required for preserving a
        character's face and costume through walking or fighting shots.
        """
        required = {
            "video.vace.python_bin": self.vace_python,
            "video.vace.worker_path": self.vace_worker,
            "video.vace.source_root": self.vace_source_root / "generate.py",
            "video.vace.config": self.vace_model_path / "config.json",
            "video.vace.transformer": self.vace_model_path / "diffusion_pytorch_model.safetensors",
            "video.vace.text_encoder": self.vace_model_path / "models_t5_umt5-xxl-enc-bf16.pth",
            "video.vace.vae": self.vace_model_path / "Wan2.1_VAE.pth",
            "source image": image_file,
        }
        missing = [f"{label} ({path})" for label, path in required.items() if not path.is_file()]
        if missing:
            raise RuntimeError(
                "VACE reference action backend is not ready; resume the model download first: "
                + "; ".join(missing)
            )
        if (self.vace_width, self.vace_height) not in {(480, 832), (832, 480)}:
            raise RuntimeError("video.vace must use the official 480x832 or 832x480 size")
        if self.vace_fps != 16:
            raise RuntimeError("video.vace.fps must remain 16 to match the official VACE sampler")
        if self.vace_frames < 5 or (self.vace_frames - 1) % 4:
            raise RuntimeError("video.vace.num_frames must use the form 4*k+1")

        directed_prompt = ", ".join(
            piece.strip() for piece in (prompt, motion_prompt, self.vace_suffix) if piece.strip()
        )
        if not directed_prompt:
            raise RuntimeError("VACE action prompt is empty")
        out_file.parent.mkdir(parents=True, exist_ok=True)
        request_file = out_file.with_suffix(".vace_request.json")
        result_file = out_file.with_suffix(".vace_result.json")
        request = {
            "source_root": str(self.vace_source_root),
            "model_path": str(self.vace_model_path),
            "reference_image": str(image_file.resolve()),
            "output_path": str(out_file.resolve()),
            "prompt": directed_prompt,
            "width": self.vace_width,
            "height": self.vace_height,
            "fps": self.vace_fps,
            "num_frames": self.vace_frames,
            "steps": self.vace_steps,
            "guidance_scale": self.vace_guidance,
            "flow_shift": self.vace_flow_shift,
            "seed": seed,
        }
        request_file.write_text(json.dumps(request, ensure_ascii=False), encoding="utf-8")
        command = [
            str(self.vace_python),
            str(self.vace_worker),
            "--request",
            str(request_file),
            "--result",
            str(result_file),
        ]
        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                check=False,
                timeout=self.vace_timeout,
            )
            result = json.loads(result_file.read_text(encoding="utf-8")) if result_file.exists() else {}
            if completed.returncode != 0 or not result.get("ok"):
                detail = result.get("error") or self._text(completed.stderr)[-3000:]
                raise RuntimeError(f"VACE reference action render failed: {detail}")
            if self.media_duration(out_file) <= 0:
                raise RuntimeError(f"VACE wrote an invalid action clip: {out_file}")
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(
                f"VACE reference action render timed out after {self.vace_timeout:.0f}s"
            ) from exc
        finally:
            request_file.unlink(missing_ok=True)
            result_file.unlink(missing_ok=True)

    def _render_sadtalker(self, image_file: Path, audio_file: Path, out_file: Path) -> None:
        """Animate a dialogue close-up using the user's already-installed SadTalker weights."""
        required = {
            "video.sadtalker.python_bin": self.sadtalker_python,
            "video.sadtalker.inference_script": self.sadtalker_script,
            "source image": image_file,
            "driving audio": audio_file,
        }
        missing = [f"{label} ({path})" for label, path in required.items() if not path.is_file()]
        if missing:
            raise RuntimeError("SadTalker motion backend is not ready: " + "; ".join(missing))
        if self.sadtalker_chunk_seconds <= 0:
            raise RuntimeError("video.sadtalker.chunk_seconds must be positive")
        stage_root = self.sadtalker_stage_root.resolve()
        stage_root.mkdir(parents=True, exist_ok=True)
        stage_dir = Path(tempfile.mkdtemp(prefix="shot_", dir=stage_root))
        source_stage = stage_dir / "source.png"
        source_face_stage = stage_dir / "source_face.png"
        audio_stage = stage_dir / "voice.wav"
        out_file.parent.mkdir(parents=True, exist_ok=True)
        try:
            # SadTalker's legacy OpenCV stack cannot open a Chinese absolute path.
            # Stage all inputs under its existing ASCII-only directory.
            shutil.copy2(image_file, source_stage)
            self._write_face_biased_crop(source_stage, source_face_stage)
            source_detected = stage_dir / "source_detected.png"
            detected = self._detect_and_crop_face(source_stage, source_detected)
            shutil.copy2(audio_file, audio_stage)
            duration = self.media_duration(audio_stage)
            # Evenly distribute the duration. A tiny trailing fragment causes
            # SadTalker's Savitzky-Golay smoother to fail, while a long single
            # fragment can exhaust memory in its legacy full-frame renderer.
            chunk_count = max(1, math.ceil(duration / self.sadtalker_chunk_seconds))
            chunk_duration = duration / chunk_count
            chunk_outputs: list[Path] = []
            for index in range(chunk_count):
                start = index * chunk_duration
                remaining = duration - start
                if remaining <= 0:
                    break
                chunk_audio = stage_dir / f"voice_{index:02d}.wav"
                split_command = [
                    self.ffmpeg_bin, "-y", "-ss", f"{start:.3f}", "-i", str(audio_stage),
                    "-t", f"{min(chunk_duration, remaining):.3f}",
                    "-c:a", "pcm_s16le", str(chunk_audio),
                ]
                self._run(split_command, f"SadTalker audio split ({index + 1}/{chunk_count})")
                render_dir = stage_dir / f"render_{index:02d}"
                attempts = [
                    (source_stage, self.sadtalker_preprocess),
                    (source_stage, self.sadtalker_fallback_preprocess),
                    (source_face_stage, "crop"),
                ]
                if detected:
                    attempts.insert(0, (source_detected, "crop"))
                    attempts.insert(1, (source_detected, self.sadtalker_fallback_preprocess))
                # Deduplicate identical attempts while preserving order.
                unique_attempts: list[tuple[Path, str]] = []
                seen: set[tuple[str, str]] = set()
                for source, preprocess in attempts:
                    key = (str(source), preprocess)
                    if key in seen:
                        continue
                    seen.add(key)
                    unique_attempts.append((source, preprocess))

                completed: subprocess.CompletedProcess[bytes] | None = None
                last_detail = ""
                for attempt_index, (source, preprocess) in enumerate(unique_attempts, start=1):
                    if render_dir.exists():
                        shutil.rmtree(render_dir, ignore_errors=True)
                    render_dir.mkdir(parents=True, exist_ok=True)
                    command = [
                        str(self.sadtalker_python),
                        str(self.sadtalker_script),
                        "--source_image", str(source),
                        "--driven_audio", str(chunk_audio),
                        "--result_dir", str(render_dir),
                        "--preprocess", preprocess,
                        "--still",
                        "--size", str(self.sadtalker_size),
                        "--batch_size", str(self.sadtalker_batch_size),
                        "--expression_scale", str(self.sadtalker_expression_scale),
                    ]
                    completed = subprocess.run(
                        command,
                        cwd=self.sadtalker_root,
                        capture_output=True,
                        check=False,
                        timeout=self.sadtalker_timeout,
                    )
                    if completed.returncode == 0:
                        break
                    last_detail = self._text(completed.stderr or completed.stdout)[-2000:]
                    print(
                        f"[sadtalker] chunk {index + 1} attempt {attempt_index} "
                        f"({preprocess}/{source.name}) failed; trying next fallback."
                    )
                if completed is None or completed.returncode != 0:
                    raise RuntimeError(
                        f"SadTalker motion render failed in chunk {index + 1}: {last_detail}"
                    )
                candidates = list(render_dir.glob("*.mp4"))
                if not candidates:
                    raise RuntimeError(f"SadTalker produced no MP4 for chunk {index + 1}")
                chunk_outputs.append(max(candidates, key=lambda item: item.stat().st_mtime))
            if not chunk_outputs:
                raise RuntimeError("SadTalker received no usable audio chunks")
            if len(chunk_outputs) == 1:
                shutil.copy2(chunk_outputs[0], out_file)
            else:
                self.concat_scenes(chunk_outputs, out_file)
            if self.media_duration(out_file) <= 0:
                raise RuntimeError(f"SadTalker wrote an invalid motion clip: {out_file}")
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(f"SadTalker timed out after {self.sadtalker_timeout:.0f}s") from exc
        finally:
            shutil.rmtree(stage_dir, ignore_errors=True)

    @staticmethod
    def _write_face_biased_crop(source: Path, destination: Path) -> None:
        """Create an upper-center square crop that keeps mouths/eyes for landmark retry."""
        from PIL import Image

        with Image.open(source) as image:
            rgb = image.convert("RGB")
            width, height = rgb.size
            side = min(width, height)
            left = max(0, (width - side) // 2)
            # Bias upward so distant standing shots still keep the face.
            top = max(0, int((height - side) * 0.15))
            if top + side > height:
                top = max(0, height - side)
            crop = rgb.crop((left, top, left + side, top + side))
            crop.save(destination, format="PNG")

    def _detect_and_crop_face(self, source: Path, destination: Path) -> bool:
        """Crop a detected face with margin using SadTalker's OpenCV environment."""
        helper = self.sadtalker_stage_root / "_face_crop_helper.py"
        helper.parent.mkdir(parents=True, exist_ok=True)
        helper.write_text(
            "\n".join(
                [
                    "import sys",
                    "from pathlib import Path",
                    "import cv2",
                    "src, dst = Path(sys.argv[1]), Path(sys.argv[2])",
                    "image = cv2.imread(str(src))",
                    "if image is None or image.size == 0:",
                    "    raise SystemExit(2)",
                    "height, width = image.shape[:2]",
                    "gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)",
                    "cascade = cv2.CascadeClassifier(str(Path(cv2.data.haarcascades) / 'haarcascade_frontalface_default.xml'))",
                    "faces = cascade.detectMultiScale(gray, scaleFactor=1.08, minNeighbors=4, minSize=(64, 64))",
                    "if len(faces) == 0:",
                    "    faces = cascade.detectMultiScale(gray, scaleFactor=1.05, minNeighbors=3, minSize=(48, 48))",
                    "if len(faces) == 0:",
                    "    raise SystemExit(3)",
                    "x, y, w, h = max(faces, key=lambda box: box[2] * box[3])",
                    "margin_x, margin_y = int(w * 0.45), int(h * 0.55)",
                    "left, top = max(0, x - margin_x), max(0, y - margin_y)",
                    "right, bottom = min(width, x + w + margin_x), min(height, y + h + margin_y)",
                    "side = max(right - left, bottom - top)",
                    "cx, cy = (left + right) // 2, (top + bottom) // 2",
                    "left, top = max(0, cx - side // 2), max(0, cy - side // 2)",
                    "right, bottom = min(width, left + side), min(height, top + side)",
                    "crop = image[top:bottom, left:right]",
                    "if crop.size == 0:",
                    "    raise SystemExit(4)",
                    "crop = cv2.resize(crop, (512, 512), interpolation=cv2.INTER_AREA)",
                    "cv2.imwrite(str(dst), crop)",
                    "print('ok')",
                ]
            ),
            encoding="utf-8",
        )
        completed = subprocess.run(
            [str(self.sadtalker_python), str(helper), str(source), str(destination)],
            cwd=self.sadtalker_root,
            capture_output=True,
            check=False,
            timeout=60,
        )
        return completed.returncode == 0 and destination.is_file() and destination.stat().st_size > 0

    def stitch_motion_scene(self, motion_file: Path, audio_file: Path, out_file: Path) -> float:
        """Fit a generated motion clip to narration while retaining generated video frames."""
        duration = self.media_duration(audio_file)
        vf = (
            f"scale={self.width}:{self.height}:force_original_aspect_ratio=decrease,"
            f"pad={self.width}:{self.height}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps={self.fps}"
        )
        command = [
            self.ffmpeg_bin, "-y", "-stream_loop", "-1", "-i", str(motion_file),
            "-i", str(audio_file), "-t", f"{duration:.3f}", "-vf", vf,
            "-map", "0:v:0", "-map", "1:a:0", "-c:v", "libx264", "-preset", self.preset,
            "-crf", str(self.crf), "-c:a", "aac", "-b:a", "192k", "-pix_fmt", self.pix_fmt,
            "-shortest", "-movflags", "+faststart", str(out_file),
        ]
        self._run(command, f"motion scene video render ({out_file.name})")
        return self.media_duration(out_file)

    def concat_scenes(self, scene_videos: list[Path], out_file: Path) -> None:
        if not scene_videos:
            raise ValueError("At least one scene clip is required")
        list_file = out_file.parent / "concat_list.txt"
        # Concat demuxer expects POSIX-style absolute paths, including on Windows.
        lines = [f"file '{video.resolve().as_posix()}'" for video in scene_videos]
        list_file.write_text("\n".join(lines), encoding="utf-8")
        command = [
            self.ffmpeg_bin, "-y", "-f", "concat", "-safe", "0", "-i", str(list_file),
            "-c:v", "libx264", "-preset", self.preset, "-crf", str(self.crf),
            "-c:a", "aac", "-b:a", "192k", "-pix_fmt", self.pix_fmt,
            "-movflags", "+faststart", str(out_file),
        ]
        self._run(command, "episode clip concatenation")

    @staticmethod
    def _srt_timestamp(seconds: float) -> str:
        millis = max(0, round(seconds * 1000))
        hours, remainder = divmod(millis, 3_600_000)
        minutes, remainder = divmod(remainder, 60_000)
        secs, millis = divmod(remainder, 1000)
        return f"{hours:02}:{minutes:02}:{secs:02},{millis:03}"

    def write_subtitles(self, cues: Iterable[tuple[float, float, str]], out_file: Path) -> None:
        blocks: list[str] = []
        for number, (start, end, text) in enumerate(cues, start=1):
            cleaned = " ".join(text.split())
            if not cleaned or end <= start:
                continue
            blocks.extend([
                str(number),
                f"{self._srt_timestamp(start)} --> {self._srt_timestamp(end)}",
                cleaned,
                "",
            ])
        if not blocks:
            raise ValueError("No valid subtitle cues were generated")
        out_file.write_text("\n".join(blocks), encoding="utf-8")

    def burn_subtitles(self, source_video: Path, subtitle_file: Path, out_file: Path) -> None:
        # ffmpeg's filter grammar needs an escaped drive colon on Windows.
        subtitle_path = subtitle_file.resolve().as_posix().replace("'", r"\'").replace(":", r"\:")
        vf = f"subtitles=filename='{subtitle_path}'"
        command = [
            self.ffmpeg_bin, "-y", "-i", str(source_video), "-vf", vf,
            "-map", "0:v:0", "-map", "0:a?",
            "-c:v", "libx264", "-preset", self.preset, "-crf", str(self.crf),
            "-c:a", "aac", "-b:a", "192k", "-pix_fmt", self.pix_fmt,
            "-movflags", "+faststart", str(out_file),
        ]
        self._run(command, "subtitle burn-in")

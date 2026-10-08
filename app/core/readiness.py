"""Shared local-backend readiness checks for preflight and the health API."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

import httpx

from app.core.config import AppConfig


def local_diffusers_ready(config: AppConfig) -> tuple[bool, dict[str, str]]:
    python_bin = Path(str(config.get("image", "local_diffusers", "python_bin", default="")))
    model_dir = Path(str(config.get("image", "local_diffusers", "model_path", default="")))
    worker = config.resolve_path(
        config.get("image", "local_diffusers", "worker_path", default="app/workers/diffusers_worker.py")
    )
    detail = {"python": str(python_bin), "model": str(model_dir), "worker": str(worker)}
    return python_bin.is_file() and model_dir.is_dir() and worker.is_file(), detail


def sapi_ready(config: AppConfig) -> tuple[bool, dict[str, str]]:
    script = config.resolve_path(config.get("tts", "sapi_script", default="scripts/sapi_tts.ps1"))
    detail = {"powershell": str(shutil.which("powershell.exe") or ""), "script": str(script)}
    return bool(detail["powershell"]) and script.is_file(), detail


def kokoro_ready(config: AppConfig) -> tuple[bool, dict[str, str]]:
    python_bin = config.resolve_path(
        config.get("tts", "kokoro", "python_bin", default=".venv-kokoro/Scripts/python.exe")
    )
    worker = config.resolve_path(
        config.get("tts", "kokoro", "worker_path", default="app/workers/kokoro_worker.py")
    )
    detail = {"python": str(python_bin), "worker": str(worker)}
    return python_bin.is_file() and worker.is_file(), detail


def animatediff_ready(config: AppConfig) -> tuple[bool, dict[str, str]]:
    python_bin = Path(str(config.get("video", "animatediff", "python_bin", default="")))
    base_model = Path(str(config.get("video", "animatediff", "base_model_path", default="")))
    motion_adapter = config.resolve_path(
        config.get("video", "animatediff", "motion_adapter_path", default="models/animatediff/motion_adapter")
    )
    ip_adapter = config.resolve_path(
        config.get("video", "animatediff", "ip_adapter_path", default="models/animatediff/ip_adapter")
    )
    worker = config.resolve_path(
        config.get("video", "animatediff", "worker_path", default="app/workers/animatediff_worker.py")
    )
    motion_weight = motion_adapter / "diffusion_pytorch_model.fp16.safetensors"
    ip_weight = ip_adapter / "models" / "ip-adapter_sd15.bin"
    image_encoder = ip_adapter / "models" / "image_encoder"
    reference_mode = bool(config.get("video", "animatediff", "reference_mode", default=False))
    detail = {
        "python": str(python_bin),
        "base_model": str(base_model),
        "motion_weight": str(motion_weight),
        "ip_adapter_weight": str(ip_weight),
        "image_encoder": str(image_encoder),
        "reference_mode": str(reference_mode),
        "worker": str(worker),
    }
    ready = (
        python_bin.is_file()
        and base_model.is_dir()
        and motion_weight.is_file()
        and worker.is_file()
    )
    if reference_mode:
        ready = ready and ip_weight.is_file() and image_encoder.is_dir()
    return ready, detail


def sadtalker_ready(config: AppConfig) -> tuple[bool, dict[str, str]]:
    root = config.resolve_path(config.get("video", "sadtalker", "root_path", default="E:/SadTalker"))
    python_bin = config.resolve_path(
        config.get("video", "sadtalker", "python_bin", default="E:/SadTalker/venv/Scripts/python.exe")
    )
    script = config.resolve_path(
        config.get("video", "sadtalker", "inference_script", default="E:/SadTalker/inference.py")
    )
    checkpoint = root / "checkpoints" / "facevid2vid_00189-model.pth.tar"
    detail = {
        "root": str(root),
        "python": str(python_bin),
        "inference_script": str(script),
        "checkpoint": str(checkpoint),
    }
    return root.is_dir() and python_bin.is_file() and script.is_file() and checkpoint.is_file(), detail


def wan_ready(config: AppConfig) -> tuple[bool, dict[str, str]]:
    python_bin = config.resolve_path(
        config.get("video", "wan", "python_bin", default=".venv-wan/Scripts/python.exe")
    )
    model_path = config.resolve_path(
        config.get("video", "wan", "model_path", default="models/wan/t2v_1.3b")
    )
    worker = config.resolve_path(
        config.get("video", "wan", "worker_path", default="app/workers/wan_worker.py")
    )
    required = {
        "python": python_bin,
        "model_index": model_path / "model_index.json",
        "scheduler": model_path / "scheduler" / "scheduler_config.json",
        "text_encoder_config": model_path / "text_encoder" / "config.json",
        "text_encoder_index": model_path / "text_encoder" / "model.safetensors.index.json",
        "tokenizer": model_path / "tokenizer" / "tokenizer.json",
        "tokenizer_config": model_path / "tokenizer" / "tokenizer_config.json",
        "tokenizer_sentencepiece": model_path / "tokenizer" / "spiece.model",
        "tokenizer_special_tokens": model_path / "tokenizer" / "special_tokens_map.json",
        "transformer_config": model_path / "transformer" / "config.json",
        "transformer_index": model_path / "transformer" / "diffusion_pytorch_model.safetensors.index.json",
        "vae": model_path / "vae" / "diffusion_pytorch_model.safetensors",
        "worker": worker,
    }
    for index in range(1, 6):
        required[f"text_encoder_shard_{index}"] = (
            model_path / "text_encoder" / f"model-{index:05d}-of-00005.safetensors"
        )
    for index in range(1, 3):
        required[f"transformer_shard_{index}"] = (
            model_path / "transformer" / f"diffusion_pytorch_model-{index:05d}-of-00002.safetensors"
        )
    detail = {label: str(path) for label, path in required.items()}
    return all(path.is_file() for path in required.values()), detail


def vace_ready(config: AppConfig) -> tuple[bool, dict[str, str]]:
    python_bin = config.resolve_path(
        config.get("video", "vace", "python_bin", default=".venv-vace/Scripts/python.exe")
    )
    source_root = config.resolve_path(
        config.get("video", "vace", "source_root", default="third_party/Wan2.1")
    )
    model_path = config.resolve_path(
        config.get("video", "vace", "model_path", default="models/vace/1.3b")
    )
    worker = config.resolve_path(
        config.get("video", "vace", "worker_path", default="app/workers/vace_worker.py")
    )
    required = {
        "python": python_bin,
        "source_entrypoint": source_root / "generate.py",
        "config": model_path / "config.json",
        "transformer": model_path / "diffusion_pytorch_model.safetensors",
        "text_encoder": model_path / "models_t5_umt5-xxl-enc-bf16.pth",
        "vae": model_path / "Wan2.1_VAE.pth",
        "tokenizer": model_path / "google" / "umt5-xxl" / "tokenizer.json",
        "tokenizer_config": model_path / "google" / "umt5-xxl" / "tokenizer_config.json",
        "tokenizer_sentencepiece": model_path / "google" / "umt5-xxl" / "spiece.model",
        "tokenizer_special_tokens": model_path / "google" / "umt5-xxl" / "special_tokens_map.json",
        "worker": worker,
    }
    detail = {label: str(path) for label, path in required.items()}
    return all(path.is_file() for path in required.values()), detail


def service_url(config: AppConfig, section: str) -> str:
    base = str(config.get(section, "base_url", default="")).rstrip("/")
    health = str(config.get(section, "health_path", default=""))
    return f"{base}{health}"


def video_motion_ready(config: AppConfig) -> tuple[bool, dict[str, Any]]:
    video_backend = str(config.get("video", "backend", default="static"))
    if video_backend == "animatediff":
        ok, detail = animatediff_ready(config)
        return ok, {"backend": video_backend, **detail}
    if video_backend == "sadtalker":
        ok, detail = sadtalker_ready(config)
        return ok, {"backend": video_backend, **detail}
    if video_backend == "wan":
        ok, detail = wan_ready(config)
        return ok, {"backend": video_backend, **detail}
    if video_backend == "vace":
        ok, detail = vace_ready(config)
        return ok, {"backend": video_backend, **detail}
    if video_backend == "hybrid":
        dialogue_ready, dialogue_detail = sadtalker_ready(config)
        action_backend = str(config.get("video", "hybrid", "action_backend", default="wan"))
        if action_backend == "wan":
            action_ready, action_detail = wan_ready(config)
        elif action_backend == "vace":
            action_ready, action_detail = vace_ready(config)
        else:
            action_ready, action_detail = False, {"error": f"Unsupported hybrid action backend: {action_backend}"}
        return dialogue_ready and action_ready, {
            "backend": video_backend,
            "dialogue_backend": str(config.get("video", "hybrid", "dialogue_backend", default="sadtalker")),
            "action_backend": action_backend,
            "sadtalker": dialogue_detail,
            action_backend: action_detail,
        }
    if video_backend == "static":
        return True, {"backend": video_backend}
    return False, {"backend": video_backend, "error": "unsupported video backend"}


def build_readiness_report(config: AppConfig, *, check_services: bool = False) -> dict[str, Any]:
    """Return a machine-local readiness report used by CLI preflight and HTTP health."""
    report: dict[str, Any] = {
        "config": str(config.source_path),
        "project_root": str(config.project_root),
        "ready": True,
        "checks": {},
    }
    checks: dict[str, dict[str, Any]] = report["checks"]
    failed = False

    for executable in (
        str(config.get("video", "ffmpeg_bin", default="ffmpeg")),
        str(config.get("video", "ffprobe_bin", default="ffprobe")),
    ):
        exists = shutil.which(executable) is not None
        checks[f"binary:{executable}"] = {"ok": exists}
        failed = failed or not exists

    motion_ok, motion_detail = video_motion_ready(config)
    checks["configured:video_motion"] = {"ok": motion_ok, **motion_detail}
    failed = failed or not motion_ok

    demo_mode = bool(config.get("project", "demo_mode", default=False))
    checks["demo_mode"] = {"ok": True, "value": demo_mode}
    backends = {
        "llm": str(config.get("llm", "backend", default="openai_compat")),
        "image": str(config.get("image", "backend", default="a1111")),
        "tts": str(config.get("tts", "backend", default="http")),
    }
    for section, backend in backends.items():
        if section == "image" and backend == "local_diffusers":
            configured, detail = local_diffusers_ready(config)
            checks[f"configured:{section}"] = {"ok": configured, "backend": backend, **detail}
        elif section == "tts" and backend == "powershell_sapi":
            configured, detail = sapi_ready(config)
            checks[f"configured:{section}"] = {"ok": configured, "backend": backend, **detail}
        elif section == "tts" and backend == "kokoro":
            configured, detail = kokoro_ready(config)
            checks[f"configured:{section}"] = {"ok": configured, "backend": backend, **detail}
        else:
            configured = bool(config.get(section, "base_url", default=""))
            checks[f"configured:{section}"] = {"ok": configured, "backend": backend}
        failed = failed or (not configured and not demo_mode)

    if check_services and not demo_mode:
        with httpx.Client(timeout=10) as client:
            for section, backend in backends.items():
                if section == "image" and backend == "local_diffusers":
                    continue
                if section == "tts" and backend in {"powershell_sapi", "kokoro"}:
                    continue
                url = service_url(config, section)
                try:
                    response = client.get(url)
                    ok = 200 <= response.status_code < 300
                    checks[f"service:{section}"] = {"ok": ok, "url": url, "status": response.status_code}
                except httpx.HTTPError as exc:
                    ok = False
                    checks[f"service:{section}"] = {"ok": ok, "url": url, "error": str(exc)}
                failed = failed or not ok

    report["ready"] = not failed
    report["video_backend"] = str(config.get("video", "backend", default="static"))
    report["llm_model"] = str(config.get("llm", "model", default=""))
    report["demo_mode"] = demo_mode
    return report

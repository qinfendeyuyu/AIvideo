"""Toonflow-compatible local Wan I2V adapter.

Exposes the same HTTP shape that Toonflow's official vendor uses for Wan:
  POST /video/generateVideo   -> { "data": "<taskId>" }
  POST /video/getVideoStatus  -> { "status": "success|failed|running", "data": {...} }

Internally submits ComfyUI API workflows (Wan2.1 I2V 14B FP8) via the existing
Comfy server (default http://127.0.0.1:8188). Cash cost ≈ ¥0; wall time is local GPU.
"""

from __future__ import annotations

import base64
import copy
import json
import re
import threading
import time
import uuid
from pathlib import Path
from typing import Any

import httpx
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_PATH = ROOT / "workflows" / "toonflow_local_wan_i2v_template.json"
COMFY_INPUT = ROOT / "runtime_cache" / "comfy_input"
COMFY_OUTPUT = ROOT / "runtime_cache" / "comfy_output"
TASK_DIR = ROOT / "runtime_cache" / "toonflow_adapter_tasks"
DEFAULT_NEGATIVE = (
    "anime, illustration, painting, cartoon, 3d render, lowres, blurry, "
    "identity change, extra limbs, duplicate person, text, watermark, logo, "
    "scene cut, jump cut, freeze frame, low quality"
)

app = FastAPI(title="Toonflow Local Wan Adapter", version="0.1.0")
_tasks: dict[str, dict[str, Any]] = {}
_lock = threading.Lock()


class GenerateBody(BaseModel):
    model: str = "wan2.1-i2v-14b-local"
    prompt: str = ""
    duration: float = 2.0
    resolution: str = "480p"
    images: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class StatusBody(BaseModel):
    taskICode: str


def _comfy_base() -> str:
    import os

    return os.environ.get("COMFY_SERVER", "http://127.0.0.1:8488").rstrip("/")


def _adapter_token() -> str:
    import os

    return os.environ.get("TOONFLOW_ADAPTER_TOKEN", "local-wan")


def _frames_for_duration(seconds: float, fps: float = 8.0) -> int:
    # Wan prefers 4n+1 frames. Default 8fps → 2s≈17, 4s≈33.
    # Higher fps (e.g. 16) densifies temporal samples so motion feels less stuttery.
    fps = max(4.0, float(fps))
    raw = max(9, int(round(float(seconds) * fps)))
    n = 1 + 4 * max(2, round((raw - 1) / 4))
    return int(min(81, n))


def _strip_data_url(raw: str) -> bytes:
    if "," in raw and raw.strip().lower().startswith("data:"):
        raw = raw.split(",", 1)[1]
    return base64.b64decode(raw)


def _save_start_image(task_id: str, images: list[str], metadata: dict[str, Any]) -> str:
    """Write start frame under Comfy input dir; return LoadImage-relative path."""
    src = None
    if images:
        src = images[0]
    elif metadata.get("img_url"):
        src = metadata["img_url"]
    elif metadata.get("first_frame_url"):
        src = metadata["first_frame_url"]
    if not src:
        raise HTTPException(400, "missing start image (images[0] or metadata.img_url)")

    rel_dir = Path("toonflow_jobs") / task_id
    abs_dir = COMFY_INPUT / rel_dir
    abs_dir.mkdir(parents=True, exist_ok=True)
    out_path = abs_dir / "start.png"

    if isinstance(src, str) and (src.startswith("http://") or src.startswith("https://")):
        with httpx.Client(timeout=60.0) as client:
            r = client.get(src)
            r.raise_for_status()
            out_path.write_bytes(r.content)
    else:
        out_path.write_bytes(_strip_data_url(src))

    # Comfy LoadImage uses path relative to input directory with forward slashes.
    return (rel_dir / "start.png").as_posix()


def _build_workflow(
    *,
    prompt: str,
    start_image: str,
    num_frames: int,
    seed: int,
    task_id: str,
    negative: str | None = None,
    frame_rate: float = 8.0,
) -> dict[str, Any]:
    template = json.loads(TEMPLATE_PATH.read_text(encoding="utf-8"))
    wf = copy.deepcopy(template)
    wf["1"]["inputs"]["positive_prompt"] = prompt
    wf["1"]["inputs"]["negative_prompt"] = negative or DEFAULT_NEGATIVE
    wf["3"]["inputs"]["image"] = start_image
    wf["7"]["inputs"]["num_frames"] = num_frames
    wf["11"]["inputs"]["seed"] = int(seed)
    wf["13"]["inputs"]["filename_prefix"] = f"toonflow_local/{task_id}"
    wf["13"]["inputs"]["frame_rate"] = float(frame_rate)
    return wf


def _find_output_mp4(task_id: str, history: dict[str, Any]) -> Path | None:
    outputs = history.get("outputs") or {}
    for node_out in outputs.values():
        for key in ("gifs", "videos"):
            for item in node_out.get(key) or []:
                full = item.get("fullpath")
                if full and Path(full).exists():
                    return Path(full)
                filename = item.get("filename")
                sub = item.get("subfolder") or ""
                if filename:
                    cand = COMFY_OUTPUT / sub / filename
                    if cand.exists():
                        return cand
    # Fallback: newest file matching prefix
    folder = COMFY_OUTPUT / "toonflow_local"
    if folder.exists():
        matches = sorted(folder.glob(f"{task_id}*.mp4"), key=lambda p: p.stat().st_mtime, reverse=True)
        if matches:
            return matches[0]
    return None


def _run_job(task_id: str, body: GenerateBody) -> None:
    TASK_DIR.mkdir(parents=True, exist_ok=True)
    meta_path = TASK_DIR / f"{task_id}.json"

    def set_state(**kwargs: Any) -> None:
        with _lock:
            _tasks[task_id].update(kwargs)
            meta_path.write_text(json.dumps(_tasks[task_id], ensure_ascii=False, indent=2), encoding="utf-8")

    try:
        set_state(status="running", failReason=None)
        start_rel = _save_start_image(task_id, body.images, body.metadata)
        seed = int(body.metadata.get("seed") or (uuid.uuid4().int % 2_147_483_647))
        target_fps = float(body.metadata.get("target_fps") or body.metadata.get("fps") or 8.0)
        frames = _frames_for_duration(body.duration, fps=target_fps)
        negative = body.metadata.get("negative_prompt")
        workflow = _build_workflow(
            prompt=body.prompt,
            start_image=start_rel,
            num_frames=frames,
            seed=seed,
            task_id=task_id,
            negative=negative,
            frame_rate=target_fps,
        )
        client_id = str(uuid.uuid4())
        with httpx.Client(timeout=60.0) as client:
            queued = client.post(
                f"{_comfy_base()}/prompt",
                json={"prompt": workflow, "client_id": client_id},
            )
            if queued.status_code >= 400:
                raise RuntimeError(f"Comfy submit failed: {queued.status_code} {queued.text[:500]}")
            prompt_id = queued.json().get("prompt_id")
            if not prompt_id:
                raise RuntimeError(f"Comfy submit missing prompt_id: {queued.text[:500]}")
            set_state(prompt_id=prompt_id, frames=frames, seed=seed, target_fps=target_fps)

            deadline = time.monotonic() + float(body.metadata.get("timeout_minutes") or 90) * 60.0
            while time.monotonic() < deadline:
                hist = client.get(f"{_comfy_base()}/history/{prompt_id}").json()
                record = hist.get(prompt_id)
                if record is not None:
                    status = record.get("status") or {}
                    completed = bool(status.get("completed"))
                    status_text = status.get("status_str", "unknown")
                    if completed or status_text == "error":
                        if status_text == "error" or not completed:
                            msgs = status.get("messages") or []
                            raise RuntimeError(f"Comfy execution error: {msgs[-1] if msgs else status_text}")
                        mp4 = _find_output_mp4(task_id, record)
                        if not mp4:
                            raise RuntimeError("Comfy finished but mp4 not found")
                        b64 = base64.b64encode(mp4.read_bytes()).decode("ascii")
                        data_url = f"data:video/mp4;base64,{b64}"
                        set_state(
                            status="success",
                            data=data_url,
                            mp4=str(mp4),
                            bytes=mp4.stat().st_size,
                        )
                        return
                time.sleep(5.0)
            raise RuntimeError("timed out waiting for ComfyUI")
    except Exception as exc:  # noqa: BLE001 - boundary
        set_state(status="failed", failReason=str(exc))


def _auth(authorization: str | None) -> None:
    if not authorization:
        # Allow empty for local-only convenience when token is default
        if _adapter_token() == "local-wan":
            return
        raise HTTPException(401, "missing Authorization")
    token = re.sub(r"(?i)^Bearer\s+", "", authorization.strip())
    if token != _adapter_token():
        raise HTTPException(401, "invalid API key")


@app.get("/")
def root() -> dict[str, Any]:
    return {
        "service": "toonflow-local-wan-adapter",
        "ok": True,
        "hint": "Use GET /health, POST /video/generateVideo, POST /video/getVideoStatus",
        "toonflow": {
            "baseUrl": "http://127.0.0.1:18765",
            "apiKey": "local-wan",
            "vendor": "integrations/toonflow/localWanComfy.ts",
            "model": "wan2.1-i2v-14b-local",
        },
    }


@app.get("/favicon.ico")
def favicon() -> dict[str, str]:
    return {"ok": "no favicon"}


@app.get("/health")
def health() -> dict[str, Any]:
    comfy_ok = False
    try:
        r = httpx.get(f"{_comfy_base()}/system_stats", timeout=3.0)
        comfy_ok = r.status_code == 200
    except Exception:
        comfy_ok = False
    return {
        "ok": True,
        "comfy": comfy_ok,
        "comfy_server": _comfy_base(),
        "template": str(TEMPLATE_PATH),
        "tasks": len(_tasks),
    }


@app.post("/video/generateVideo")
def generate_video(body: GenerateBody, authorization: str | None = Header(default=None)) -> dict[str, Any]:
    _auth(authorization)
    if "wan" not in body.model.lower() and body.metadata.get("force") is not True:
        # Still accept; Toonflow routes by model name containing wan on the client.
        pass
    if not body.prompt.strip():
        raise HTTPException(400, "prompt is required")
    task_id = uuid.uuid4().hex
    with _lock:
        _tasks[task_id] = {
            "status": "queued",
            "model": body.model,
            "prompt": body.prompt[:200],
            "duration": body.duration,
            "created_at": time.time(),
        }
    threading.Thread(target=_run_job, args=(task_id, body), daemon=True).start()
    return {"data": task_id}


@app.post("/video/getVideoStatus")
def get_video_status(body: StatusBody, authorization: str | None = Header(default=None)) -> dict[str, Any]:
    _auth(authorization)
    with _lock:
        task = _tasks.get(body.taskICode)
        if task is None:
            disk = TASK_DIR / f"{body.taskICode}.json"
            if disk.exists():
                task = json.loads(disk.read_text(encoding="utf-8"))
                _tasks[body.taskICode] = task
    if not task:
        raise HTTPException(404, f"unknown taskICode: {body.taskICode}")

    status = task.get("status") or "running"
    if status == "success":
        return {
            "status": "success",
            "data": {"status": "success", "data": task.get("data"), "mp4": task.get("mp4")},
        }
    if status == "failed":
        return {
            "status": "failed",
            "data": {"status": "failed", "failReason": task.get("failReason") or "unknown error"},
        }
    return {"status": "running", "data": {"status": "running"}}


@app.get("/v1/models")
def list_models() -> dict[str, Any]:
    return {
        "data": [
            {"id": "wan2.1-i2v-14b-local", "object": "model"},
            {"id": "wan2.1-local", "object": "model"},
        ]
    }


def main() -> None:
    import os
    import uvicorn

    host = os.environ.get("ADAPTER_HOST", "127.0.0.1")
    port = int(os.environ.get("ADAPTER_PORT", "18765"))
    uvicorn.run(app, host=host, port=port, reload=False)


if __name__ == "__main__":
    main()

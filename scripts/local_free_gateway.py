"""Strictly local, restartable Toonflow gateway; no model download or cloud fallback.

Run: python scripts/local_free_gateway.py (127.0.0.1:18766).
Only this new gateway is governed by this policy; legacy workflows stay unchanged.
"""
from __future__ import annotations

import base64
import binascii
import copy
import io
import json
import os
import re
import secrets
import shutil
import subprocess
import threading
import time
import uuid
from contextlib import asynccontextmanager
from fractions import Fraction
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Literal
from urllib.parse import urlsplit

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel, ConfigDict, Field

ROOT = Path(__file__).resolve().parents[1]
MAX_IMAGE_BYTES = 12 * 1024 * 1024
MAX_IMAGE_PIXELS = 16_777_216
MAX_ASSET_BYTES = 256 * 1024 * 1024
DIMENSIONS = {"9:16": (720, 1280), "16:9": (1280, 720), "1:1": (1024, 1024)}
OLLAMA_MODEL = "qwen2.5:7b"
TERMINAL = {"succeeded", "failed", "needs_attention"}
IMAGE_NEGATIVE = "blurry, low quality, malformed face, extra limbs, bad anatomy, text, subtitles, watermark, logo"
VIDEO_NEGATIVE = "blurry, lowres, identity change, extra limbs, duplicate person, text, watermark, scene cut, jump cut"


def windows_memory_status() -> dict[str, Any]:
    """Read Windows commit headroom without WMI, elevation, or system changes."""
    if os.name != "nt":
        return {"supported": False, "error": "This gateway's memory preflight requires Windows"}
    try:
        import ctypes
        from ctypes import wintypes

        class Status(ctypes.Structure):
            _fields_ = [("length", wintypes.DWORD), ("load", wintypes.DWORD)] + [
                (name, ctypes.c_ulonglong) for name in ("total_phys", "avail_phys", "total_page", "avail_page", "total_virtual", "avail_virtual", "extended")
            ]
        status = Status()
        status.length = ctypes.sizeof(status)
        if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            raise OSError("GlobalMemoryStatusEx failed")
        return {"supported": True, "commit_limit_gib": round(status.total_page / 1024**3, 2),
                "available_commit_gib": round(status.avail_page / 1024**3, 2),
                "available_ram_gib": round(status.avail_phys / 1024**3, 2)}
    except (OSError, AttributeError) as exc:
        return {"supported": True, "error": str(exc)}


class StrictBody(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ImageBody(StrictBody):
    prompt: str = Field(min_length=1, max_length=16000)
    negative_prompt: str | None = Field(default=None, max_length=8000)
    seed: int | None = Field(default=None, ge=0, le=2**63 - 1, strict=True)
    aspect_ratio: Literal["9:16", "16:9", "1:1"] = "9:16"


class VideoBody(StrictBody):
    prompt: str = Field(min_length=1, max_length=16000)
    image: str = Field(min_length=1, max_length=4 * ((MAX_IMAGE_BYTES + 2) // 3) + 100)
    seed: int | None = Field(default=None, ge=0, le=2**63 - 1, strict=True)
    duration: Literal[2, 3, 4] = 2
    aspect_ratio: Literal["9:16"] = "9:16"


class TextBody(StrictBody):
    prompt: str = Field(min_length=1, max_length=16000)
    system: str | None = Field(default=None, max_length=16000)


def local_url(value: str) -> str:
    """Permit numeric loopback only: no DNS, userinfo, path, redirects or proxies."""
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError as exc:
        raise ValueError("Service URL must be an HTTP loopback URL with an explicit port") from exc
    if (
        parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "::1"}
        or parsed.username is not None or parsed.password is not None
        or parsed.path not in {"", "/"} or parsed.query or parsed.fragment
        or port is None or not 1024 <= port <= 65535
    ):
        raise ValueError("Only http://127.0.0.1:PORT or http://[::1]:PORT is allowed")
    return value.rstrip("/")


def canonical_id(value: str) -> str:
    try:
        parsed = uuid.UUID(value)
    except (ValueError, AttributeError) as exc:
        raise HTTPException(400, "Invalid job UUID") from exc
    if parsed.version != 4 or str(parsed) != value:
        raise HTTPException(400, "Expected a canonical UUIDv4")
    return value


def image_png(encoded: str) -> bytes:
    if encoded.startswith("data:"):
        match = re.fullmatch(r"data:image/(png|jpeg|webp);base64,(.*)", encoded, re.DOTALL)
        if not match:
            raise HTTPException(400, "Only PNG/JPEG/WebP base64 images are supported")
        encoded = match.group(2)
    if encoded.lower().startswith(("http:", "https:", "file:", "ftp:")):
        raise HTTPException(400, "Remote URLs and file paths are forbidden; supply image base64")
    try:
        raw = base64.b64decode(encoded, validate=True)
        if not raw or len(raw) > MAX_IMAGE_BYTES:
            raise ValueError("Image exceeds the 12 MiB upload limit")
        with Image.open(io.BytesIO(raw)) as probe:
            if probe.format not in {"PNG", "JPEG", "WEBP"}:
                raise ValueError("Unsupported image format")
            if max(probe.size) > 4096 or min(probe.size) < 32 or probe.width * probe.height > MAX_IMAGE_PIXELS:
                raise ValueError("Image dimensions must be 32–4096 pixels and at most 16 megapixels")
            probe.verify()
        with Image.open(io.BytesIO(raw)) as source:
            result = io.BytesIO()
            source.convert("RGB").save(result, format="PNG")
            if result.tell() > MAX_IMAGE_BYTES:
                raise ValueError("Decoded PNG exceeds the 12 MiB upload limit")
            return result.getvalue()
    except (binascii.Error, ValueError, OSError, UnidentifiedImageError, Image.DecompressionBombError) as exc:
        raise HTTPException(400, f"Invalid image: {exc}") from exc


def output_metadata(item: Any, extension: str) -> dict[str, str]:
    if not isinstance(item, dict):
        raise ValueError("Comfy output metadata must be an object")
    filename, subfolder = item.get("filename"), item.get("subfolder", "")
    if not isinstance(filename, str) or not re.fullmatch(r"[A-Za-z0-9_-]+\.[A-Za-z0-9]+", filename):
        raise ValueError("Unsafe Comfy output filename")
    if not filename.lower().endswith(extension):
        raise ValueError("Unexpected Comfy output extension")
    if not isinstance(subfolder, str) or len(subfolder) > 240 or "\\" in subfolder or ":" in subfolder:
        raise ValueError("Unsafe Comfy output subfolder")
    if subfolder and (
        subfolder.startswith("/") or any(part in {"", ".", ".."} for part in subfolder.split("/"))
        or not re.fullmatch(r"[A-Za-z0-9_/-]+", subfolder)
    ):
        raise ValueError("Unsafe Comfy output subfolder")
    if item.get("type") != "output":
        raise ValueError("Only Comfy output assets are accepted")
    return {"filename": filename, "subfolder": subfolder, "type": "output"}


def validate_video_asset(path: Path, job: dict[str, Any]) -> None:
    """Check real native format/frame count and fully decode; no GPU acceleration."""
    def executable(name: str) -> str:
        found = shutil.which(name)
        fallback = Path(f"E:/FFmpeg/bin/{name}.exe")
        if found:
            return found
        if fallback.is_file():
            return str(fallback)
        raise ValueError(f"{name} is required to validate video; refusing an unchecked result")

    probe, decoder = executable("ffprobe"), executable("ffmpeg")
    options = {"capture_output": True, "text": True, "encoding": "utf-8", "errors": "replace", "timeout": 60, "check": True}
    if os.name == "nt":
        options["creationflags"] = subprocess.CREATE_NO_WINDOW
    try:
        result = subprocess.run([probe, "-v", "error", "-select_streams", "v:0", "-count_frames", "-show_entries",
                                 "stream=width,height,avg_frame_rate,nb_read_frames", "-of", "json", str(path)], **options)
        streams = json.loads(result.stdout).get("streams", [])
        if len(streams) != 1:
            raise ValueError("Expected exactly one selected video stream")
        stream = streams[0]
        if (stream.get("width"), stream.get("height")) != (job["native_width"], job["native_height"]):
            raise ValueError("Video native dimensions do not match the requested workflow")
        if Fraction(str(stream.get("avg_frame_rate"))) != job["fps"] or int(stream.get("nb_read_frames", -1)) != job["frames"]:
            raise ValueError("Video frame rate/count do not match the requested workflow")
        subprocess.run([decoder, "-v", "error", "-xerror", "-nostdin", "-i", str(path), "-map", "0:v:0", "-f", "null", "-"], **options)
    except (subprocess.SubprocessError, OSError, ValueError, TypeError, ZeroDivisionError) as exc:
        raise ValueError(f"Video media validation failed: {exc}") from exc


class Gateway:
    def __init__(self, work_dir: Path, comfy_url: str, ollama_url: str,
                 transport: httpx.BaseTransport | None = None, poll_seconds: float = 3.0,
                 memory_probe: Callable[[], dict[str, Any]] = windows_memory_status):
        self.work_dir = work_dir.resolve()
        self.work_dir.mkdir(parents=True, exist_ok=True)
        self.comfy_url, self.ollama_url = local_url(comfy_url), local_url(ollama_url)
        self.transport, self.poll_seconds = transport, poll_seconds
        self.memory_probe = memory_probe
        self.lock = threading.RLock()
        self.step_lock = threading.Lock()
        self.text_lock = threading.Lock()
        self.stop_event = threading.Event()
        self.wake = threading.Event()
        self.thread: threading.Thread | None = None
        self.worker_lock_file = None
        self.video_validator = validate_video_asset
        self.jobs: dict[str, dict[str, Any]] = {}
        self.last_worker_error: str | None = None
        self._load()

    def client(self, timeout: float = 30) -> httpx.Client:
        return httpx.Client(timeout=timeout, trust_env=False, follow_redirects=False, transport=self.transport)

    def json_call(self, method: str, url: str, **kwargs: Any) -> Any:
        with self.client() as client:
            response = client.request(method, url, **kwargs)
            response.raise_for_status()
            if len(response.content) > 8 * 1024 * 1024:
                raise ValueError("Oversized JSON response")
            return response.json()

    def _save(self, job: dict[str, Any]) -> None:
        job["updated_at"] = time.time()
        path = self.work_dir / f"{job['id']}.json"
        temp = path.with_suffix(".json.tmp")
        temp.write_text(json.dumps(job, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temp, path)

    def _load(self) -> None:
        for path in self.work_dir.glob("*.json"):
            try:
                job_id = canonical_id(path.stem)
                job = json.loads(path.read_text(encoding="utf-8"))
                if not isinstance(job, dict) or job.get("id") != job_id or job.get("kind") not in {"image", "video"}:
                    raise ValueError("Invalid persisted job schema")
                if not isinstance(job.get("created_at"), (int, float)):
                    raise ValueError("Invalid persisted job timestamp")
                if job.get("status") == "queued" and not isinstance(job.get("request"), dict):
                    raise ValueError("Missing queued request")
                if job.get("status") not in TERMINAL | {"queued", "submitting", "running"}:
                    raise ValueError("Unknown persisted job state")
                if job.get("status") in {"submitting", "running"} and not job.get("prompt_id"):
                    job.update(status="needs_attention", error="Submission was interrupted before acknowledgement; automatic resubmission is disabled")
                elif job.get("status") == "submitting":
                    job["status"] = "running"
                self.jobs[job_id] = job
            except (OSError, ValueError, TypeError, HTTPException):
                # Corrupt state is visible, and blocks a blind GPU retry.
                try:
                    job_id = canonical_id(path.stem)
                except HTTPException:
                    continue
                job = {"id": job_id, "kind": "unknown", "status": "needs_attention", "created_at": path.stat().st_mtime,
                       "error": "Persisted job record is corrupt; inspect it before retrying"}
                self.jobs[job_id] = job

    def public(self, job: dict[str, Any]) -> dict[str, Any]:
        fields = ("id", "status", "kind", "prompt_id", "error", "native_width", "native_height", "frames", "fps",
                  "seed", "created_at", "updated_at", "aspect_ratio", "duration", "last_connection_error")
        data = {key: job[key] for key in fields if key in job}
        if job.get("status") == "succeeded":
            data["asset_url"] = f"/jobs/{job['id']}/asset"
        return data

    def update(self, job_id: str, **values: Any) -> None:
        with self.lock:
            self.jobs[job_id].update(values)
            self._save(self.jobs[job_id])

    def create(self, kind: str, body: ImageBody | VideoBody) -> dict[str, Any]:
        if not body.prompt.strip():
            raise HTTPException(400, "Prompt cannot be blank")
        # Validate/decode before allocating a job or making any request.
        png = image_png(body.image) if isinstance(body, VideoBody) else None
        self.require_memory(kind)
        job_id = str(uuid.uuid4())
        values = body.model_dump(exclude={"image"})
        width, height = DIMENSIONS[body.aspect_ratio] if kind == "image" else (480, 832)
        job: dict[str, Any] = {
            "id": job_id, "kind": kind, "status": "queued", "created_at": time.time(),
            "request": values, "seed": body.seed if body.seed is not None else secrets.randbits(31),
            "native_width": width, "native_height": height, "aspect_ratio": body.aspect_ratio,
        }
        if isinstance(body, VideoBody):
            job.update(frames=body.duration * 8 + 1, fps=8, duration=body.duration)
        with self.lock:
            if png is not None:
                input_path = self.work_dir / f"{job_id}.input.png"
                input_path.write_bytes(png)
            self.jobs[job_id] = job
            try:
                self._save(job)
            except OSError:
                self.jobs.pop(job_id, None)
                raise
            result = self.public(job)
        self.wake.set()
        return result

    def memory(self) -> dict[str, Any]:
        value = dict(self.memory_probe())
        available = value.get("available_commit_gib")
        known = isinstance(available, (int, float))
        value.update(text_required_gib=6, image_required_gib=8, video_required_gib=16,
                     text_ready=bool(known and available >= 6), image_ready=bool(known and available >= 8),
                     video_ready=bool(known and available >= 16))
        return value

    def require_memory(self, kind: str) -> None:
        memory = self.memory()
        if not memory[f"{kind}_ready"]:
            required = memory[f"{kind}_required_gib"]
            available = memory.get("available_commit_gib", "unknown")
            label = {"video": "视频", "image": "图片", "text": "文本"}[kind]
            raise HTTPException(503, f"可用提交内存不足：当前 {available} GiB，本地{label}至少需要 {required} GiB。请保存工作并关闭其他占用内存的应用后重试；程序不会关闭应用或修改虚拟内存。")

    def start(self) -> None:
        if self.thread is not None and self.thread.is_alive():
            return
        lock_file = (self.work_dir / ".worker.lock").open("a+b")
        try:
            lock_file.seek(0, 2)
            if lock_file.tell() == 0:
                lock_file.write(b"0")
                lock_file.flush()
            lock_file.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(lock_file.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            lock_file.close()
            raise RuntimeError("Another local gateway worker already owns this job directory") from exc
        self.worker_lock_file = lock_file
        # Reload only after acquiring ownership: another instance may have made
        # progress between factory construction and server startup. Reading a
        # second instance must never rewrite the active worker's state.
        with self.lock:
            self.jobs.clear()
            self._load()
        self.stop_event.clear()
        self.thread = threading.Thread(target=self._worker, name="local-free-single-gpu-worker", daemon=True)
        self.thread.start()

    def close(self) -> None:
        self.stop_event.set()
        self.wake.set()
        if self.thread is not None:
            self.thread.join(timeout=3)
        # Keep the process lock while an HTTP operation is still finishing.
        if self.worker_lock_file is not None and (self.thread is None or not self.thread.is_alive()):
            self.worker_lock_file.close()
            self.worker_lock_file = None

    def _worker(self) -> None:
        while not self.stop_event.is_set():
            try:
                self.process_once()
            except Exception as exc:
                self.last_worker_error = f"{type(exc).__name__}: {exc}"
            self.wake.wait(self.poll_seconds)
            self.wake.clear()

    def process_once(self) -> None:
        """One serial step; also useful for deterministic no-GPU tests."""
        with self.step_lock:
            self._process_once()

    def _process_once(self) -> None:
        with self.lock:
            ordered = sorted(self.jobs.values(), key=lambda item: item.get("created_at", 0))
            active = next((job for job in ordered if job["status"] in {"running", "submitting"}), None)
            if active is None:
                if any(job["status"] == "needs_attention" for job in ordered):
                    return
                active = next((job for job in ordered if job["status"] == "queued"), None)
            if active is None:
                return
            job = copy.deepcopy(active)
        if job["status"] == "queued":
            try:
                self.require_memory(job["kind"])
            except HTTPException as exc:
                self.update(job["id"], error=exc.detail)
                return
            self._submit(job)
        elif job.get("prompt_id"):
            self._poll(job)
        else:
            self.update(job["id"], status="needs_attention", error="Unknown submission outcome; automatic resubmission disabled")

    def _workflow(self, job: dict[str, Any]) -> dict[str, Any]:
        body = job["request"]
        if job["kind"] == "image":
            workflow = json.loads((ROOT / "workflows/realvisxl_v5_vertical_hero_portrait_single_api.json").read_text(encoding="utf-8"))
            workflow["2"]["inputs"].update(width=job["native_width"], height=job["native_height"], batch_size=1)
            workflow["3"]["inputs"]["text"] = body["prompt"]
            workflow["4"]["inputs"]["text"] = body.get("negative_prompt") if body.get("negative_prompt") is not None else IMAGE_NEGATIVE
            workflow["10"]["inputs"].update(seed=job["seed"], steps=40)
            workflow["12"]["inputs"]["filename_prefix"] = f"local_free/{job['id']}"
            return workflow
        png = (self.work_dir / f"{job['id']}.input.png").read_bytes()
        with self.client() as client:
            response = client.post(f"{self.comfy_url}/upload/image", files={"image": (f"{job['id']}.png", png, "image/png")},
                                   data={"type": "input", "subfolder": "local_free", "overwrite": "false"})
            response.raise_for_status()
            uploaded = response.json()
        name, folder = uploaded.get("name"), uploaded.get("subfolder", "")
        # Apply identical path safety, with the different upload endpoint schema.
        safe = output_metadata({"filename": name, "subfolder": folder, "type": "output"}, ".png")
        if uploaded.get("type") != "input":
            raise ValueError("Comfy did not acknowledge an input upload")
        input_name = str(PurePosixPath(safe["subfolder"]) / safe["filename"])
        workflow = json.loads((ROOT / "workflows/toonflow_local_wan_i2v_template.json").read_text(encoding="utf-8"))
        workflow["1"]["inputs"].update(positive_prompt=body["prompt"], negative_prompt=VIDEO_NEGATIVE)
        workflow["3"]["inputs"]["image"] = input_name
        workflow["7"]["inputs"].update(num_frames=job["frames"], width=480, height=832)
        workflow["11"]["inputs"].update(seed=job["seed"], steps=20)
        workflow["13"]["inputs"].update(filename_prefix=f"local_free/{job['id']}", frame_rate=8)
        return workflow

    def _submit(self, job: dict[str, Any]) -> None:
        job_id = job["id"]
        try:
            workflow = self._workflow(job)
        except (httpx.HTTPError, ValueError, OSError, KeyError) as exc:
            self.update(job_id, status="failed", error=f"Preparation failed before GPU submission: {exc}")
            return
        # This write precedes the only GPU-submitting HTTP call. Never re-send an
        # unacknowledged request: a timeout can occur after Comfy accepted it.
        self.update(job_id, status="submitting", workflow=workflow)
        try:
            with self.client() as client:
                response = client.post(f"{self.comfy_url}/prompt", json={"prompt": workflow, "client_id": job_id})
                if response.status_code in {400, 422}:
                    self.update(job_id, status="failed", error=f"Comfy rejected workflow: {response.text[:1200]}")
                    return
                response.raise_for_status()
                payload = response.json()
            prompt_id = payload.get("prompt_id")
            if not isinstance(prompt_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", prompt_id):
                raise ValueError("Comfy returned no valid prompt_id")
            self.update(job_id, status="running", prompt_id=prompt_id, error=None)
        except (httpx.HTTPError, ValueError, OSError) as exc:
            self.update(job_id, status="needs_attention", error=f"Unknown submission outcome; do not resubmit automatically: {exc}")

    def _poll(self, job: dict[str, Any]) -> None:
        job_id, prompt_id = job["id"], job["prompt_id"]
        if not isinstance(prompt_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", prompt_id):
            self.update(job_id, status="needs_attention", error="Invalid persisted prompt_id")
            return
        try:
            history = self.json_call("GET", f"{self.comfy_url}/history/{prompt_id}")
            record = history.get(prompt_id)
            if record is None:
                queue = self.json_call("GET", f"{self.comfy_url}/queue")
                present = any(isinstance(item, list) and len(item) > 1 and item[1] == prompt_id
                              for key in ("queue_running", "queue_pending") for item in queue.get(key, []))
                if not present:
                    # Completion can move a prompt from queue to history between
                    # the two reads; confirm its absence before pausing.
                    record = self.json_call("GET", f"{self.comfy_url}/history/{prompt_id}").get(prompt_id)
                    if record is None:
                        self.update(job_id, status="needs_attention", error="Prompt is absent from Comfy history and queue; inspect before retrying")
                        return
                else:
                    return
            status = record.get("status") or {}
            if status.get("status_str") == "error":
                self.update(job_id, status="failed", error=f"Comfy execution failed: {str(status.get('messages', []))[-1500:]}")
                return
            if not status.get("completed"):
                return
            self._download_result(job, record)
        except httpx.HTTPError as exc:
            # A service restart must not trigger duplicate GPU work. Keep tracking.
            self.update(job_id, last_connection_error=f"Comfy temporarily unavailable: {exc}")
        except (ValueError, KeyError, OSError, TypeError) as exc:
            self.update(job_id, status="failed", error=f"Invalid Comfy result: {exc}")

    def _download_result(self, job: dict[str, Any], record: dict[str, Any]) -> None:
        image_job = job["kind"] == "image"
        node = record.get("outputs", {}).get("12" if image_job else "13", {})
        candidates = node.get("images", []) if image_job else node.get("gifs", []) + node.get("videos", [])
        if not candidates:
            raise ValueError("Comfy completed without the expected saved output")
        extension = ".png" if image_job else ".mp4"
        metadata = output_metadata(candidates[0], extension)
        destination = self.work_dir / f"{job['id']}{extension}"
        partial = destination.with_suffix(extension + ".partial")
        total = 0
        try:
            with self.client(timeout=120) as client:
                with client.stream("GET", f"{self.comfy_url}/view", params=metadata) as response:
                    response.raise_for_status()
                    with partial.open("wb") as output:
                        for chunk in response.iter_bytes(65536):
                            total += len(chunk)
                            if total > MAX_ASSET_BYTES:
                                raise ValueError("Output exceeds 256 MiB")
                            output.write(chunk)
            if image_job:
                with Image.open(partial) as image:
                    if image.format != "PNG" or image.size != (job["native_width"], job["native_height"]):
                        raise ValueError("Output image dimensions or format do not match the job")
                    image.verify()
            else:
                with partial.open("rb") as video:
                    header = video.read(12)
                if len(header) < 12 or header[4:8] != b"ftyp":
                    raise ValueError("Output is not an MP4 container")
                self.video_validator(partial, job)
            os.replace(partial, destination)
            self.update(job["id"], status="succeeded", asset_name=destination.name, asset_bytes=total,
                        error=None, last_connection_error=None)
        finally:
            partial.unlink(missing_ok=True)

    def health(self) -> dict[str, Any]:
        report: dict[str, Any] = {"service": "local-free-gateway", "local_only": True, "cloud_fallback": False,
                                  "comfy_url": self.comfy_url, "ollama_url": self.ollama_url, "text_model": OLLAMA_MODEL}
        comfy = {"reachable": False, "image_ready": False, "video_ready": False}
        ollama = {"reachable": False, "model_available": False}
        try:
            stats = self.json_call("GET", f"{self.comfy_url}/system_stats", timeout=3)
            nodes = self.json_call("GET", f"{self.comfy_url}/object_info", timeout=3)
            comfy["reachable"] = isinstance(stats, dict) and "system" in stats
            image_wf = json.loads((ROOT / "workflows/realvisxl_v5_vertical_hero_portrait_single_api.json").read_text(encoding="utf-8"))
            video_wf = json.loads((ROOT / "workflows/toonflow_local_wan_i2v_template.json").read_text(encoding="utf-8"))
            for label, workflow in (("image", image_wf), ("video", video_wf)):
                missing = []
                for value in workflow.values():
                    name = value["class_type"]
                    if name not in nodes:
                        missing.append(name)
                        continue
                    required = nodes[name].get("input", {}).get("required", {})
                    for key in ("ckpt_name", "model", "model_name"):
                        configured = value.get("inputs", {}).get(key)
                        options = required.get(key)
                        if isinstance(configured, str) and isinstance(options, list) and options and isinstance(options[0], list) and configured not in options[0]:
                            missing.append(f"{name}.{key}: {configured}")
                comfy[f"{label}_ready"] = comfy["reachable"] and not missing
                comfy[f"{label}_missing"] = missing
        except (httpx.HTTPError, ValueError, OSError, KeyError, TypeError) as exc:
            comfy["error"] = str(exc)
        try:
            tags = self.json_call("GET", f"{self.ollama_url}/api/tags", timeout=3)
            ollama["reachable"] = isinstance(tags.get("models"), list)
            ollama["model_available"] = any(item.get("name") == OLLAMA_MODEL or item.get("model") == OLLAMA_MODEL for item in tags.get("models", []))
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
            ollama["error"] = str(exc)
        with self.lock:
            paused = any(job["status"] == "needs_attention" for job in self.jobs.values())
            report.update(jobs=len(self.jobs), queue_paused=paused)
        report.update(comfy=comfy, ollama=ollama, ready=bool(comfy["image_ready"] and comfy["video_ready"] and ollama["model_available"]))
        report["memory"] = self.memory()
        report["ready"] = report["ready"] and report["memory"]["video_ready"] and not paused
        report["ok"] = report["ready"]
        report["worker_error"] = self.last_worker_error
        return report


def create_app(*, work_dir: str | Path | None = None, comfy_url: str = "http://127.0.0.1:8488",
               ollama_url: str = "http://127.0.0.1:11434", transport: httpx.BaseTransport | None = None,
               start_worker: bool = True, poll_seconds: float = 3.0,
               memory_probe: Callable[[], dict[str, Any]] = windows_memory_status) -> FastAPI:
    gateway = Gateway(Path(work_dir) if work_dir is not None else ROOT / "runtime_cache/local_free_jobs",
                      comfy_url, ollama_url, transport, poll_seconds, memory_probe)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        if start_worker:
            gateway.start()
        yield
        gateway.close()

    app = FastAPI(title="Free Local Drama Gateway", version="1.0.0", lifespan=lifespan)
    app.state.gateway = gateway

    @app.get("/")
    def root():
        page = ROOT / "app/static/local_free.html"
        if page.is_file():
            return FileResponse(page, media_type="text/html")
        return {"service": "local-free-gateway", "health": "/health", "jobs": "/jobs"}

    @app.get("/health")
    def health():
        return gateway.health()

    @app.get("/jobs")
    def list_jobs():
        with gateway.lock:
            return {"jobs": [gateway.public(job) for job in sorted(gateway.jobs.values(), key=lambda item: item.get("created_at", 0), reverse=True)]}

    def get_job(job_id: str) -> dict[str, Any]:
        canonical_id(job_id)
        with gateway.lock:
            job = gateway.jobs.get(job_id)
            if job is None:
                raise HTTPException(404, "Unknown job")
            return copy.deepcopy(job)

    @app.get("/jobs/{job_id}")
    def job_status(job_id: str):
        return gateway.public(get_job(job_id))

    @app.get("/jobs/{job_id}/asset")
    def job_asset(job_id: str):
        job = get_job(job_id)
        if job.get("status") != "succeeded":
            raise HTTPException(409, "Job has no completed asset")
        extension = ".png" if job["kind"] == "image" else ".mp4"
        # Never trust a path stored in a task record or returned by Comfy.
        path = gateway.work_dir / f"{job_id}{extension}"
        if path.resolve().parent != gateway.work_dir or not path.is_file():
            raise HTTPException(404, "Completed asset is missing")
        return FileResponse(path, media_type="image/png" if extension == ".png" else "video/mp4")

    @app.post("/jobs/image", status_code=202)
    def image_job(body: ImageBody):
        return gateway.create("image", body)

    @app.post("/jobs/video", status_code=202)
    def video_job(body: VideoBody):
        return gateway.create("video", body)

    @app.post("/text")
    def text_job(body: TextBody):
        if not body.prompt.strip():
            raise HTTPException(400, "Prompt cannot be blank")
        messages = []
        if body.system:
            messages.append({"role": "system", "content": body.system})
        messages.append({"role": "user", "content": body.prompt})
        if not gateway.text_lock.acquire(blocking=False):
            raise HTTPException(409, "本地文本模型正在生成，请等待当前任务完成后再提交。")
        try:
            gateway.require_memory("text")
            with gateway.client(timeout=600) as client:
                response = client.post(f"{gateway.ollama_url}/api/chat", json={
                    "model": OLLAMA_MODEL, "messages": messages, "stream": False, "keep_alive": 0,
                    "options": {"num_gpu": 0, "num_ctx": 4096, "num_predict": 2048, "temperature": 0.45},
                })
                response.raise_for_status()
                value = response.json().get("message", {}).get("content")
            if not isinstance(value, str) or not value.strip():
                raise ValueError("Ollama returned no text")
            return {"text": value, "model": OLLAMA_MODEL, "local_only": True}
        except (httpx.HTTPError, ValueError) as exc:
            raise HTTPException(503, f"Local Ollama failed; no cloud fallback: {exc}") from exc
        finally:
            gateway.text_lock.release()

    return app


def main() -> None:
    import argparse
    import uvicorn

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=18766)
    parser.add_argument("--comfy-url", default="http://127.0.0.1:8488")
    parser.add_argument("--ollama-url", default="http://127.0.0.1:11434")
    args = parser.parse_args()
    uvicorn.run(create_app(comfy_url=args.comfy_url, ollama_url=args.ollama_url), host="127.0.0.1", port=args.port, workers=1)


if __name__ == "__main__":
    main()

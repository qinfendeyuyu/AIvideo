from __future__ import annotations

import base64
import io
import json
import subprocess
import textwrap
from asyncio import to_thread
from pathlib import Path
from typing import Any

import httpx
from PIL import Image, ImageDraw

from app.core.config import AppConfig


class ImageService:
    def __init__(self, config: AppConfig):
        self.backend = str(config.get("image", "backend", default="a1111"))
        self.base_url = str(config.get("image", "base_url", default="")).rstrip("/")
        self.path = str(config.get("image", "txt2img_path", default=""))
        self.steps = int(config.get("image", "steps", default=35))
        self.cfg_scale = float(config.get("image", "cfg_scale", default=7.0))
        self.sampler_name = str(config.get("image", "sampler_name", default="DPM++ 2M Karras"))
        self.negative_prompt = str(config.get("image", "negative_prompt", default=""))
        self.timeout = float(config.get("image", "timeout_seconds", default=300))
        self.extra_payload: dict[str, Any] = config.get("image", "extra_payload", default={}) or {}
        self.local_python = str(config.get("image", "local_diffusers", "python_bin", default=""))
        self.local_model_path = str(config.get("image", "local_diffusers", "model_path", default=""))
        self.local_worker_path = config.resolve_path(
            config.get("image", "local_diffusers", "worker_path", default="app/workers/diffusers_worker.py")
        )
        self.local_device = str(config.get("image", "local_diffusers", "device", default="cuda"))
        self.local_dtype = str(config.get("image", "local_diffusers", "dtype", default="float16"))
        self.local_attention_slicing = bool(
            config.get("image", "local_diffusers", "attention_slicing", default=True)
        )
        self.local_vae_slicing = bool(
            config.get("image", "local_diffusers", "vae_slicing", default=True)
        )
        self.demo_mode = bool(config.get("project", "demo_mode", default=False))

    @staticmethod
    def _decode_image(value: str) -> bytes:
        encoded = value.split(",", 1)[1] if value.startswith("data:image") else value
        return base64.b64decode(encoded, validate=True)

    @staticmethod
    def _verify_png(image_bytes: bytes) -> None:
        with Image.open(io.BytesIO(image_bytes)) as image:
            image.verify()

    async def render_scene(
        self,
        prompt: str,
        out_file: Path,
        *,
        width: int,
        height: int,
        seed: int | None,
    ) -> None:
        out_file.parent.mkdir(parents=True, exist_ok=True)
        if self.demo_mode:
            print("[demo] writing diagnostic still frame; real image backends are skipped.")
            self._render_fallback_image(prompt, out_file, width, height)
            return
        if self.backend == "local_diffusers":
            await to_thread(
                self._render_local_diffusers,
                prompt,
                out_file,
                width,
                height,
                seed,
            )
            return
        if self.backend != "a1111":
            raise RuntimeError(f"Unsupported image.backend: {self.backend}")
        if not self.base_url or not self.path:
            raise RuntimeError("image.base_url and image.txt2img_path are required when demo_mode is false")
        payload: dict[str, Any] = {
            "prompt": prompt,
            "negative_prompt": self.negative_prompt,
            "steps": self.steps,
            "cfg_scale": self.cfg_scale,
            "sampler_name": self.sampler_name,
            "width": width,
            "height": height,
        }
        if seed is not None:
            payload["seed"] = seed
        payload.update(self.extra_payload)
        url = f"{self.base_url}{self.path}"

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
            data = response.json()
            images = data.get("images", []) if isinstance(data, dict) else []
            if not images or not isinstance(images[0], str):
                raise ValueError("image response has no base64 image in images[0]")
            image_bytes = self._decode_image(images[0])
            self._verify_png(image_bytes)
            out_file.write_bytes(image_bytes)
        except (httpx.HTTPError, ValueError, OSError) as exc:
            raise RuntimeError(
                f"Image generation failed at {url}: {exc}. Fix the local image service; no fallback is used "
                "outside demo_mode."
            ) from exc

    def _render_local_diffusers(
        self,
        prompt: str,
        out_file: Path,
        width: int,
        height: int,
        seed: int | None,
    ) -> None:
        if not self.local_python or not self.local_model_path:
            raise RuntimeError(
                "image.local_diffusers.python_bin and image.local_diffusers.model_path are required"
            )
        if not Path(self.local_python).is_file():
            raise RuntimeError(f"Local Diffusers Python not found: {self.local_python}")
        if not Path(self.local_model_path).is_dir():
            raise RuntimeError(f"Local Diffusers model not found: {self.local_model_path}")
        if not self.local_worker_path.is_file():
            raise RuntimeError(f"Local Diffusers worker not found: {self.local_worker_path}")

        out_file.parent.mkdir(parents=True, exist_ok=True)
        request_file = out_file.with_suffix(".diffusers_request.json")
        result_file = out_file.with_suffix(".diffusers_result.json")
        request = {
            "model_path": self.local_model_path,
            "output_path": str(out_file.resolve()),
            "prompt": prompt,
            "negative_prompt": self.negative_prompt,
            "width": width,
            "height": height,
            "steps": self.steps,
            "cfg_scale": self.cfg_scale,
            "seed": seed,
            "device": self.local_device,
            "dtype": self.local_dtype,
            "attention_slicing": self.local_attention_slicing,
            "vae_slicing": self.local_vae_slicing,
        }
        request_file.write_text(json.dumps(request, ensure_ascii=False), encoding="utf-8")
        command = [
            self.local_python,
            str(self.local_worker_path),
            "--request",
            str(request_file),
            "--result",
            str(result_file),
        ]
        try:
            completed = subprocess.run(command, capture_output=True, check=False)
            result = json.loads(result_file.read_text(encoding="utf-8")) if result_file.exists() else {}
            if completed.returncode != 0 or not result.get("ok"):
                detail = result.get("error") or completed.stderr.decode("utf-8", errors="replace")[-2000:]
                raise RuntimeError(f"Local Diffusers render failed: {detail}")
            if not self._valid_output_file(out_file):
                raise RuntimeError(f"Local Diffusers wrote an invalid image: {out_file}")
        finally:
            request_file.unlink(missing_ok=True)
            result_file.unlink(missing_ok=True)

    @staticmethod
    def _valid_output_file(path: Path) -> bool:
        try:
            with Image.open(path) as image:
                image.verify()
            return True
        except (OSError, ValueError):
            return False

    @staticmethod
    def _render_fallback_image(prompt: str, out_file: Path, width: int, height: int) -> None:
        image = Image.new("RGB", (width, height), color=(21, 24, 37))
        draw = ImageDraw.Draw(image)
        draw.rectangle((28, 28, width - 28, height - 28), outline=(121, 192, 255), width=3)
        draw.text((56, 58), "DEMO FRAME — LOCAL IMAGE SERVICE NOT CONNECTED", fill=(210, 230, 255))
        body = "\n".join(textwrap.wrap(prompt[:900], width=76))
        draw.multiline_text((56, 118), body, fill=(238, 238, 238), spacing=10)
        image.save(out_file, format="PNG")

from __future__ import annotations

import base64
import io
import json
import subprocess
import wave
from asyncio import to_thread
from pathlib import Path
from typing import Any

import httpx

from app.core.config import AppConfig


class TTSService:
    def __init__(self, config: AppConfig):
        self.backend = str(config.get("tts", "backend", default="http"))
        self.base_url = str(config.get("tts", "base_url", default="")).rstrip("/")
        self.path = str(config.get("tts", "synthesize_path", default=""))
        self.speaker = str(config.get("tts", "speaker", default="narrator"))
        self.speed = float(config.get("tts", "speed", default=1.0))
        self.timeout = float(config.get("tts", "timeout_seconds", default=180))
        self.sapi_script = config.resolve_path(
            config.get("tts", "sapi_script", default="scripts/sapi_tts.ps1")
        )
        self.kokoro_python = config.resolve_path(
            config.get("tts", "kokoro", "python_bin", default=".venv-kokoro/Scripts/python.exe")
        )
        self.kokoro_worker = config.resolve_path(
            config.get("tts", "kokoro", "worker_path", default="app/workers/kokoro_worker.py")
        )
        self.kokoro_repo_id = str(
            config.get("tts", "kokoro", "repo_id", default="hexgrad/Kokoro-82M-v1.1-zh")
        )
        model_dir_raw = config.get("tts", "kokoro", "model_dir", default="")
        self.kokoro_model_dir = (
            config.resolve_path(model_dir_raw) if model_dir_raw else None
        )
        self.kokoro_voice = str(config.get("tts", "kokoro", "voice", default="zf_001"))
        self.kokoro_device = str(config.get("tts", "kokoro", "device", default="cpu"))
        self.kokoro_timeout = float(config.get("tts", "kokoro", "timeout_seconds", default=300))
        self.demo_mode = bool(config.get("project", "demo_mode", default=False))

    @staticmethod
    def _extract_audio(response: httpx.Response) -> bytes:
        content_type = response.headers.get("content-type", "").lower()
        if "application/json" not in content_type:
            return response.content
        body: Any = response.json()
        if isinstance(body, dict):
            encoded = body.get("audio") or body.get("audio_base64")
            if not encoded and isinstance(body.get("data"), dict):
                encoded = body["data"].get("audio") or body["data"].get("audio_base64")
            if isinstance(encoded, str):
                return base64.b64decode(encoded, validate=True)
        raise ValueError("JSON TTS response has no audio or audio_base64 field")

    @staticmethod
    def _verify_wav(audio_bytes: bytes) -> None:
        with wave.open(io.BytesIO(audio_bytes), "rb") as wav_file:
            if wav_file.getnchannels() < 1 or wav_file.getframerate() < 8_000 or wav_file.getnframes() < 1:
                raise ValueError("WAV has no usable audio frames")

    async def synthesize(self, text: str, out_file: Path, *, speaker: str | None = None) -> None:
        out_file.parent.mkdir(parents=True, exist_ok=True)
        if self.demo_mode:
            print("[demo] writing silence WAV; real TTS backends are skipped.")
            self._write_silence_wav(out_file, seconds=3)
            return
        if self.backend == "powershell_sapi":
            await to_thread(self._synthesize_sapi, text, out_file, speaker or self.speaker)
            return
        if self.backend == "kokoro":
            await to_thread(self._synthesize_kokoro, text, out_file, speaker or self.kokoro_voice)
            return
        if self.backend != "http":
            raise RuntimeError(f"Unsupported tts.backend: {self.backend}")
        if not self.base_url or not self.path:
            raise RuntimeError("tts.base_url and tts.synthesize_path are required when demo_mode is false")
        payload = {
            "text": text,
            "speaker": speaker or self.speaker,
            "speed": self.speed,
            "format": "wav",
        }
        url = f"{self.base_url}{self.path}"
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
            audio_bytes = self._extract_audio(response)
            if not audio_bytes:
                raise ValueError("TTS response body is empty")
            self._verify_wav(audio_bytes)
            out_file.write_bytes(audio_bytes)
        except (httpx.HTTPError, ValueError, OSError, wave.Error) as exc:
            raise RuntimeError(
                f"TTS synthesis failed at {url}: {exc}. Fix the local TTS service; no fallback is used "
                "outside demo_mode."
            ) from exc

    def _synthesize_sapi(self, text: str, out_file: Path, speaker: str) -> None:
        if not self.sapi_script.is_file():
            raise RuntimeError(f"SAPI worker script not found: {self.sapi_script}")
        out_file.parent.mkdir(parents=True, exist_ok=True)
        text_file = out_file.with_suffix(".sapi_input.txt")
        text_file.write_text(text, encoding="utf-8")
        rate = max(-10, min(10, round((self.speed - 1.0) * 10)))
        command = [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(self.sapi_script),
            "-TextPath",
            str(text_file),
            "-OutputPath",
            str(out_file),
            "-VoiceName",
            speaker,
            "-Rate",
            str(rate),
        ]
        try:
            completed = subprocess.run(command, capture_output=True, check=False)
            if completed.returncode != 0:
                detail = completed.stderr.decode("utf-8", errors="replace")[-2000:]
                raise RuntimeError(f"Windows SAPI synthesis failed: {detail}")
            audio_bytes = out_file.read_bytes()
            self._verify_wav(audio_bytes)
        finally:
            text_file.unlink(missing_ok=True)

    def _synthesize_kokoro(self, text: str, out_file: Path, voice: str) -> None:
        if not self.kokoro_python.is_file():
            raise RuntimeError(
                f"Kokoro Python not found: {self.kokoro_python}. Run scripts/setup_kokoro.ps1 first."
            )
        if not self.kokoro_worker.is_file():
            raise RuntimeError(f"Kokoro worker not found: {self.kokoro_worker}")
        mapped = voice
        if voice in {"Microsoft Huihui Desktop", "narrator", "su_lan", "lin_yao"}:
            mapped = self.kokoro_voice
        if not mapped.startswith(("zf_", "zm_")):
            raise RuntimeError(
                f"Kokoro voice must be a built-in ID like zf_001/zm_010, got: {voice}"
            )

        out_file.parent.mkdir(parents=True, exist_ok=True)
        request_file = out_file.with_suffix(".kokoro_request.json")
        result_file = out_file.with_suffix(".kokoro_result.json")
        ledger_file = out_file.with_suffix(".kokoro_ledger.json")
        request = {
            "text": text,
            "voice": mapped,
            "speed": self.speed,
            "repo_id": self.kokoro_repo_id,
            "device": self.kokoro_device,
            "output_path": str(out_file.resolve()),
            "sample_rate": 24000,
        }
        if self.kokoro_model_dir is not None:
            request["model_dir"] = str(self.kokoro_model_dir)
        request_file.write_text(json.dumps(request, ensure_ascii=False, indent=2), encoding="utf-8")
        try:
            completed = subprocess.run(
                [
                    str(self.kokoro_python),
                    str(self.kokoro_worker),
                    "--request",
                    str(request_file),
                    "--result",
                    str(result_file),
                ],
                capture_output=True,
                check=False,
                timeout=self.kokoro_timeout,
            )
            result = json.loads(result_file.read_text(encoding="utf-8")) if result_file.exists() else {}
            if completed.returncode != 0 or not result.get("ok"):
                detail = result.get("error") or completed.stderr.decode("utf-8", errors="replace")[-2000:]
                raise RuntimeError(f"Kokoro synthesis failed: {detail}")
            self._verify_wav(out_file.read_bytes())
            ledger_file.write_text(
                json.dumps(
                    {
                        "commercial_status": "BLOCKED",
                        "purpose": "local_prototype_listening_only",
                        "text": text,
                        "requested_voice": voice,
                        "resolved_voice": mapped,
                        "repo_id": self.kokoro_repo_id,
                        "device": self.kokoro_device,
                        "speed": self.speed,
                        "output": str(out_file),
                        "worker_result": result,
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
        finally:
            request_file.unlink(missing_ok=True)
            result_file.unlink(missing_ok=True)

    @staticmethod
    def _write_silence_wav(out_file: Path, seconds: int = 3, sample_rate: int = 22050) -> None:
        frames = b"\x00\x00" * sample_rate * seconds
        with wave.open(str(out_file), "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(frames)

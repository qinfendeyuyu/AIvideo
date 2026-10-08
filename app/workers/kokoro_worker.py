"""Kokoro TTS worker: offline Mandarin synthesis for local prototypes.

Commercial status remains BLOCKED until rights evidence in
docs/COMMERCIAL_LOCAL_TTS_OPTION.md is closed. Use only built-in voice IDs.
"""

from __future__ import annotations

import argparse
import json
import traceback
from pathlib import Path


def synthesize(request: dict) -> dict:
    import numpy as np
    import soundfile as sf
    import torch
    from kokoro import KModel, KPipeline

    text = str(request["text"]).strip()
    if not text:
        raise ValueError("text must not be empty")

    voice = str(request.get("voice") or "zf_001")
    if not voice.startswith(("zf_", "zm_")):
        raise ValueError(f"Only built-in Mandarin voice IDs are allowed, got: {voice}")

    speed = float(request.get("speed") or 1.0)
    repo_id = str(request.get("repo_id") or "hexgrad/Kokoro-82M-v1.1-zh")
    model_dir = request.get("model_dir")
    sample_rate = int(request.get("sample_rate") or 24000)
    device = str(request.get("device") or ("cuda" if torch.cuda.is_available() else "cpu"))
    output_path = Path(str(request["output_path"]))
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if model_dir:
        root = Path(str(model_dir))
        config_path = root / "config.json"
        weight_path = root / "kokoro-v1_1-zh.pth"
        if not config_path.is_file() or not weight_path.is_file():
            raise FileNotFoundError(f"Kokoro local model incomplete under {root}")
        model = KModel(config=str(config_path), model=str(weight_path)).to(device).eval()
        # Voices still resolve from the Hub repo id / local HF cache.
        pipeline = KPipeline(lang_code="z", repo_id=repo_id, model=model)
    else:
        model = KModel(repo_id=repo_id).to(device).eval()
        pipeline = KPipeline(lang_code="z", repo_id=repo_id, model=model)

    chunks: list[np.ndarray] = []
    for result in pipeline(text, voice=voice, speed=speed):
        audio = getattr(result, "audio", None)
        if audio is None and isinstance(result, (tuple, list)) and len(result) >= 3:
            audio = result[2]
        if audio is None:
            continue
        if hasattr(audio, "detach"):
            audio = audio.detach().cpu().numpy()
        chunks.append(np.asarray(audio, dtype=np.float32))

    if not chunks:
        raise RuntimeError("Kokoro produced no audio chunks")

    waveform = np.concatenate(chunks) if len(chunks) > 1 else chunks[0]
    sf.write(str(output_path), waveform, sample_rate)

    return {
        "ok": True,
        "output_path": str(output_path.resolve()),
        "voice": voice,
        "repo_id": repo_id,
        "sample_rate": sample_rate,
        "device": device,
        "samples": int(waveform.shape[0]),
        "duration_seconds": round(float(waveform.shape[0]) / sample_rate, 3),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Kokoro local TTS worker")
    parser.add_argument("--request", required=True, help="JSON request path")
    parser.add_argument("--result", required=True, help="JSON result path")
    args = parser.parse_args()

    request_path = Path(args.request)
    result_path = Path(args.result)
    try:
        request = json.loads(request_path.read_text(encoding="utf-8"))
        payload = synthesize(request)
    except Exception as exc:  # noqa: BLE001 - worker boundary
        payload = {"ok": False, "error": f"{type(exc).__name__}: {exc}", "trace": traceback.format_exc()[-4000:]}
    result_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0 if payload.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())

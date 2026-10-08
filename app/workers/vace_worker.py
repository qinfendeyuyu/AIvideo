"""Isolated official Wan VACE renderer for reference-locked action shots.

This worker intentionally delegates sampling to the checked-in Wan source
tree.  It never falls back to a still image or a talking-head clip: a missing
weight, invalid reference, subprocess failure, or absent MP4 makes the job
fail with a machine-readable result.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path


SUPPORTED_SIZES = {(480, 832), (832, 480)}
REQUIRED_MODEL_FILES = (
    "config.json",
    "diffusion_pytorch_model.safetensors",
    "models_t5_umt5-xxl-enc-bf16.pth",
    "Wan2.1_VAE.pth",
    "google/umt5-xxl/special_tokens_map.json",
    "google/umt5-xxl/spiece.model",
    "google/umt5-xxl/tokenizer.json",
    "google/umt5-xxl/tokenizer_config.json",
)


def _write_result(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _validate(payload: dict[str, object]) -> tuple[Path, Path, Path, Path, int, int, int]:
    source_root = Path(str(payload["source_root"])).resolve()
    model_path = Path(str(payload["model_path"])).resolve()
    reference_image = Path(str(payload["reference_image"])).resolve()
    output_path = Path(str(payload["output_path"])).resolve()
    width = int(payload["width"])
    height = int(payload["height"])
    num_frames = int(payload["num_frames"])

    if not (source_root / "generate.py").is_file():
        raise FileNotFoundError(f"Wan VACE source entrypoint not found: {source_root / 'generate.py'}")
    if not reference_image.is_file():
        raise FileNotFoundError(f"VACE reference image not found: {reference_image}")
    missing = [item for item in REQUIRED_MODEL_FILES if not (model_path / item).is_file()]
    if missing:
        raise FileNotFoundError("VACE checkpoint is incomplete: " + ", ".join(missing))
    if (width, height) not in SUPPORTED_SIZES:
        raise ValueError("VACE 1.3B only supports 480x832 or 832x480 in the official source")
    if num_frames < 5 or (num_frames - 1) % 4:
        raise ValueError("VACE num_frames must be at least 5 and use the form 4*k+1")
    if not str(payload.get("prompt") or "").strip():
        raise ValueError("VACE action prompt is empty")
    return source_root, model_path, reference_image, output_path, width, height, num_frames


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--request", required=True)
    parser.add_argument("--result", required=True)
    args = parser.parse_args()
    result_path = Path(args.result)
    try:
        payload = json.loads(Path(args.request).read_text(encoding="utf-8"))
        source_root, model_path, reference_image, output_path, width, height, num_frames = _validate(payload)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        environment = os.environ.copy()
        environment["PYTHONPATH"] = str(source_root) + os.pathsep + environment.get("PYTHONPATH", "")
        command = [
            sys.executable,
            str(source_root / "generate.py"),
            "--task",
            "vace-1.3B",
            "--size",
            f"{width}*{height}",
            "--frame_num",
            str(num_frames),
            "--ckpt_dir",
            str(model_path),
            "--offload_model",
            "True",
            "--t5_cpu",
            "--src_ref_images",
            str(reference_image),
            "--prompt",
            str(payload["prompt"]),
            "--base_seed",
            str(int(payload.get("seed") if payload.get("seed") is not None else 20260806)),
            "--sample_solver",
            "unipc",
            "--sample_steps",
            str(int(payload.get("steps", 50))),
            "--sample_shift",
            str(float(payload.get("flow_shift", 16.0))),
            "--sample_guide_scale",
            str(float(payload.get("guidance_scale", 5.0))),
            "--save_file",
            str(output_path),
        ]
        started = time.perf_counter()
        completed = subprocess.run(
            command,
            cwd=str(source_root),
            env=environment,
            capture_output=True,
            check=False,
        )
        elapsed = round(time.perf_counter() - started, 3)
        stdout = completed.stdout.decode("utf-8", errors="replace")[-3000:]
        stderr = completed.stderr.decode("utf-8", errors="replace")[-3000:]
        if completed.returncode != 0:
            raise RuntimeError(f"official VACE process exited {completed.returncode}: {stderr or stdout}")
        if not output_path.is_file() or output_path.stat().st_size == 0:
            raise RuntimeError(f"official VACE process produced no MP4: {output_path}")
        _write_result(
            result_path,
            {
                "ok": True,
                "output_path": str(output_path),
                "fps": 16,
                "num_frames": num_frames,
                "elapsed_seconds": elapsed,
                "stdout_tail": stdout,
            },
        )
        return 0
    except Exception as exc:
        _write_result(result_path, {"ok": False, "error": str(exc)})
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

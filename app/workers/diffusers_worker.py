"""Isolated Diffusers renderer for local GPU inference."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--request", required=True)
    parser.add_argument("--result", required=True)
    args = parser.parse_args()
    result_path = Path(args.result)
    try:
        payload = json.loads(Path(args.request).read_text(encoding="utf-8"))
        import torch
        from diffusers import StableDiffusionPipeline

        if not torch.cuda.is_available():
            raise RuntimeError("CUDA is unavailable to this Diffusers runtime")
        model_path = Path(payload["model_path"])
        if not model_path.is_dir():
            raise FileNotFoundError(f"Diffusers model directory not found: {model_path}")
        output_path = Path(payload["output_path"])
        output_path.parent.mkdir(parents=True, exist_ok=True)
        dtype = torch.float16 if payload.get("dtype", "float16") == "float16" else torch.float32
        started = time.perf_counter()
        torch.cuda.reset_peak_memory_stats()
        pipeline = StableDiffusionPipeline.from_pretrained(
            model_path,
            torch_dtype=dtype,
            safety_checker=None,
            local_files_only=True,
        )
        pipeline.set_progress_bar_config(disable=True)
        if payload.get("attention_slicing", True):
            pipeline.enable_attention_slicing()
        if payload.get("vae_slicing", True):
            pipeline.enable_vae_slicing()
        pipeline.to(payload.get("device", "cuda"))
        seed = payload.get("seed")
        generator = None
        if seed is not None:
            generator = torch.Generator(device=payload.get("device", "cuda")).manual_seed(int(seed))
        image = pipeline(
            prompt=payload["prompt"],
            negative_prompt=payload.get("negative_prompt") or None,
            width=int(payload["width"]),
            height=int(payload["height"]),
            num_inference_steps=int(payload["steps"]),
            guidance_scale=float(payload["cfg_scale"]),
            generator=generator,
        ).images[0]
        image.save(output_path)
        result = {
            "ok": True,
            "seconds": round(time.perf_counter() - started, 2),
            "peak_gpu_mb": round(torch.cuda.max_memory_allocated() / 1024 / 1024),
            "output_path": str(output_path),
        }
    except Exception as exc:
        result = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
    result_path.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

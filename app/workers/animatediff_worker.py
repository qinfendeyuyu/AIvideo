"""Isolated AnimateDiff + IP-Adapter image-to-video renderer for local GPU inference."""

from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
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
        from diffusers import AnimateDiffPipeline, DDIMScheduler, MotionAdapter
        from PIL import Image

        if not torch.cuda.is_available():
            raise RuntimeError("CUDA is unavailable to this AnimateDiff runtime")

        reference_mode = bool(payload.get("reference_mode", False))
        source_image = Path(payload["source_image"]) if reference_mode else None
        base_model = Path(payload["base_model_path"])
        motion_adapter = Path(payload["motion_adapter_path"])
        ip_adapter = Path(payload["ip_adapter_path"])
        output_path = Path(payload["output_path"])
        for label, path in {
            "base model": base_model,
            "motion adapter": motion_adapter,
        }.items():
            if not path.exists():
                raise FileNotFoundError(f"{label} not found: {path}")
        if reference_mode and source_image is not None and not source_image.is_file():
            raise FileNotFoundError(f"source image not found: {source_image}")
        if reference_mode and not ip_adapter.is_dir():
            raise FileNotFoundError(f"IP-Adapter not found: {ip_adapter}")

        output_path.parent.mkdir(parents=True, exist_ok=True)
        started = time.perf_counter()
        torch.cuda.empty_cache()
        torch.cuda.reset_peak_memory_stats()
        dtype = torch.float16 if payload.get("dtype", "float16") == "float16" else torch.float32
        adapter = MotionAdapter.from_pretrained(
            motion_adapter, torch_dtype=dtype, variant="fp16", local_files_only=True
        )
        pipeline = AnimateDiffPipeline.from_pretrained(
            base_model,
            motion_adapter=adapter,
            torch_dtype=dtype,
            safety_checker=None,
            local_files_only=True,
        )
        pipeline.scheduler = DDIMScheduler.from_pretrained(
            base_model,
            subfolder="scheduler",
            clip_sample=False,
            timestep_spacing="linspace",
            beta_schedule="linear",
            steps_offset=1,
            local_files_only=True,
        )
        # Keep the non-offloaded 8 GB compatibility probe below the VRAM
        # limit.  The attention path is exact, only its execution is sliced.
        pipeline.enable_attention_slicing()
        pipeline.enable_vae_slicing()
        if reference_mode:
            pipeline.load_ip_adapter(
                ip_adapter,
                subfolder="models",
                weight_name="ip-adapter_sd15.bin",
                local_files_only=True,
            )
            pipeline.set_ip_adapter_scale(float(payload.get("ip_adapter_scale", 0.65)))
        # Offload after loading the IP-Adapter; this is normally required on an
        # 8 GB GPU, but can be disabled for a compatibility probe.
        if bool(payload.get("cpu_offload", True)):
            pipeline.enable_model_cpu_offload()
        else:
            pipeline.to("cuda")
        pipeline.set_progress_bar_config(disable=True)
        width = int(payload["width"])
        height = int(payload["height"])
        reference = (
            Image.open(source_image).convert("RGB").resize((width, height))
            if reference_mode and source_image is not None
            else None
        )
        seed = payload.get("seed")
        generator = torch.Generator(device="cpu")
        if seed is not None:
            generator.manual_seed(int(seed))
        call_args = {
            "prompt": payload["prompt"],
            "negative_prompt": payload.get("negative_prompt") or None,
            "num_frames": int(payload.get("num_frames", 16)),
            "num_inference_steps": int(payload.get("steps", 20)),
            "guidance_scale": float(payload.get("guidance_scale", 7.0)),
            "width": width,
            "height": height,
            "generator": generator,
        }
        if reference is not None:
            call_args["ip_adapter_image"] = reference
        frames = pipeline(**call_args).frames[0]
        with tempfile.TemporaryDirectory(prefix="animatediff_frames_") as frames_dir:
            frame_pattern = Path(frames_dir) / "frame_%04d.png"
            for index, frame in enumerate(frames):
                frame.save(Path(frames_dir) / f"frame_{index:04d}.png")
            encoded = subprocess.run(
                [
                    "ffmpeg", "-y", "-framerate", str(int(payload.get("fps", 8))),
                    "-i", str(frame_pattern), "-c:v", "libx264", "-pix_fmt", "yuv420p",
                    "-movflags", "+faststart", str(output_path),
                ],
                capture_output=True,
                check=False,
            )
            if encoded.returncode != 0:
                detail = encoded.stderr.decode("utf-8", errors="replace")[-2000:]
                raise RuntimeError(f"ffmpeg frame encoding failed: {detail}")
        result = {
            "ok": True,
            "seconds": round(time.perf_counter() - started, 2),
            "peak_gpu_mb": round(torch.cuda.max_memory_allocated() / 1024 / 1024),
            "frames": len(frames),
            "output_path": str(output_path),
        }
    except Exception as exc:
        result = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
    finally:
        try:
            del pipeline, adapter
        except NameError:
            pass
        try:
            torch.cuda.empty_cache()
        except (NameError, AttributeError):
            pass
    result_path.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

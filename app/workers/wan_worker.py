"""Isolated low-VRAM Wan 2.1 text-to-video renderer for action shots.

The worker deliberately has no dependency on the main FastAPI process.  Wan
uses substantially more RAM/VRAM than the image and talking-head renderers,
so loading it in a fresh subprocess makes failures recoverable and releases
CUDA memory between individual action shots.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
import time
from pathlib import Path


def _install_torch_rmsnorm_compat(torch: object) -> None:
    """Backport torch.nn.RMSNorm for the pinned CUDA 12.1 / Torch 2.3 runtime.

    Diffusers 0.35 fixed Wan's temporal VAE decode but uses the RMSNorm class
    added to PyTorch 2.4.  Keeping the mature CUDA 12.1 Torch installation is
    safer than replacing the complete GPU stack, so provide the equivalent
    layer only when the class is absent.
    """
    if hasattr(torch.nn, "RMSNorm"):
        return

    class RMSNorm(torch.nn.Module):
        def __init__(
            self,
            normalized_shape: int | tuple[int, ...] | list[int],
            eps: float | None = None,
            elementwise_affine: bool = True,
            device: object | None = None,
            dtype: object | None = None,
        ) -> None:
            super().__init__()
            if isinstance(normalized_shape, int):
                normalized_shape = (normalized_shape,)
            else:
                normalized_shape = tuple(normalized_shape)
            self.normalized_shape = normalized_shape
            self.eps = eps
            if elementwise_affine:
                self.weight = torch.nn.Parameter(
                    torch.ones(normalized_shape, device=device, dtype=dtype)
                )
            else:
                self.register_parameter("weight", None)

        def forward(self, hidden_states: object) -> object:
            epsilon = self.eps
            if epsilon is None:
                epsilon = torch.finfo(hidden_states.dtype).eps
            variance = hidden_states.float().pow(2).mean(dim=-1, keepdim=True)
            result = hidden_states.float() * torch.rsqrt(variance + epsilon)
            if self.weight is not None:
                result = result * self.weight.float()
            return result.to(hidden_states.dtype)

    torch.nn.RMSNorm = RMSNorm


def _install_torch_sdpa_compat(torch: object) -> None:
    """Accept the PyTorch 2.5 ``enable_gqa`` attention argument on Torch 2.3."""
    attention = torch.nn.functional.scaled_dot_product_attention
    if getattr(attention, "_wan_enable_gqa_compat", False):
        return

    def scaled_dot_product_attention(query: object, key: object, value: object, *args: object, **kwargs: object) -> object:
        enable_gqa = bool(kwargs.pop("enable_gqa", False))
        if enable_gqa and query.shape[-3] != key.shape[-3]:
            if query.shape[-3] % key.shape[-3]:
                raise ValueError("Wan attention query heads must be divisible by key/value heads")
            repeats = query.shape[-3] // key.shape[-3]
            key = key.repeat_interleave(repeats, dim=-3)
            value = value.repeat_interleave(repeats, dim=-3)
        # Torch 2.3's fused kernel does not perform the mixed-precision
        # promotion accepted by newer Torch releases.  Wan may provide BF16
        # values alongside FP32 queries/keys, so align the operands locally.
        if key.dtype != query.dtype:
            key = key.to(query.dtype)
        if value.dtype != query.dtype:
            value = value.to(query.dtype)
        return attention(query, key, value, *args, **kwargs)

    scaled_dot_product_attention._wan_enable_gqa_compat = True
    torch.nn.functional.scaled_dot_product_attention = scaled_dot_product_attention


def _encode_frames(frames: list[object], output_path: Path, fps: int) -> None:
    """Encode PIL frames with the project ffmpeg, avoiding plugin-specific codecs."""
    import numpy as np
    from PIL import Image

    with tempfile.TemporaryDirectory(prefix="wan_frames_") as frame_root:
        root = Path(frame_root)
        for index, frame in enumerate(frames):
            # WanPipeline in the pinned Diffusers version returns NumPy RGB
            # arrays, while some later versions return PIL images.  Normalize
            # both forms here so the render contract is version-stable.
            if not hasattr(frame, "save"):
                array = np.asarray(frame)
                if np.issubdtype(array.dtype, np.floating):
                    # Diffusers decodes video frames as normalized [0, 1]
                    # float RGB arrays.  Pillow cannot encode float RGB PNGs.
                    scale = 255.0 if array.size and float(array.max()) <= 1.0 else 1.0
                    array = np.clip(array * scale, 0, 255).astype(np.uint8)
                frame = Image.fromarray(array)
            frame.save(root / f"frame_{index:04d}.png")
        encoded = subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-framerate",
                str(fps),
                "-i",
                str(root / "frame_%04d.png"),
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                "-movflags",
                "+faststart",
                str(output_path),
            ],
            capture_output=True,
            check=False,
        )
        if encoded.returncode != 0:
            detail = encoded.stderr.decode("utf-8", errors="replace")[-2000:]
            raise RuntimeError(f"ffmpeg frame encoding failed: {detail}")


def _enable_offload(pipeline: object, mode: str) -> None:
    if mode == "sequential":
        pipeline.enable_sequential_cpu_offload()
    elif mode == "model":
        pipeline.enable_model_cpu_offload()
    elif mode == "balanced":
        # The pipeline was dispatched while loading.  Calling either of the
        # generic CPU offload helpers afterwards would discard that mapping.
        return
    elif mode == "none":
        pipeline.to("cuda")
    else:
        raise ValueError("offload_mode must be one of: sequential, model, none")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--request", required=True)
    parser.add_argument("--result", required=True)
    args = parser.parse_args()
    result_path = Path(args.result)
    pipeline = None
    vae = None
    try:
        payload = json.loads(Path(args.request).read_text(encoding="utf-8"))
        import torch

        _install_torch_rmsnorm_compat(torch)
        _install_torch_sdpa_compat(torch)
        from diffusers import AutoencoderKLWan, WanPipeline
        from diffusers.schedulers.scheduling_unipc_multistep import UniPCMultistepScheduler

        if not torch.cuda.is_available():
            raise RuntimeError("CUDA is unavailable to this Wan runtime")
        if not torch.cuda.is_bf16_supported():
            raise RuntimeError("This GPU/runtime does not support bfloat16 required by Wan 2.1")

        model_path = Path(payload["model_path"])
        output_path = Path(payload["output_path"])
        width = int(payload["width"])
        height = int(payload["height"])
        requested_frame_count = int(payload["num_frames"])
        temporal_output_scale = int(payload.get("temporal_output_scale", 1))
        if temporal_output_scale < 1:
            raise ValueError("temporal_output_scale must be at least 1")
        # Wan-VAE in the compatible 0.35 runtime consumes four internal
        # temporal units for each exported frame after the first.  Keep the
        # public request expressed in delivered frames, not latent units.
        frame_count = 1 + (requested_frame_count - 1) * temporal_output_scale
        if not model_path.is_dir():
            raise FileNotFoundError(f"Wan model directory not found: {model_path}")
        if width % 16 or height % 16:
            raise ValueError("Wan width and height must be multiples of 16")
        if requested_frame_count < 5 or (requested_frame_count - 1) % 4:
            raise ValueError("Wan num_frames must have the form 4*k+1 and be at least 5")

        output_path.parent.mkdir(parents=True, exist_ok=True)
        started = time.perf_counter()
        torch.cuda.empty_cache()
        torch.cuda.reset_peak_memory_stats()
        torch.backends.cuda.matmul.allow_tf32 = True

        # Wan's VAE is intentionally float32: it produces materially cleaner
        # decoding than BF16 while the much larger transformer stays BF16.
        offload_mode = str(payload.get("offload_mode", "sequential"))
        if offload_mode == "balanced":
            # T2V-1.3B includes a much larger UMT5 text encoder than its
            # name suggests.  On a 32GB RAM / 8GB VRAM workstation, loading
            # every component on CPU first can page indefinitely.  Diffusers'
            # component-level balanced mapping keeps the encoder in RAM and
            # the video transformer/VAE on CUDA without changing any weights.
            pipeline = WanPipeline.from_pretrained(
                model_path,
                torch_dtype={
                    "text_encoder": torch.bfloat16,
                    "transformer": torch.bfloat16,
                    "vae": torch.float32,
                },
                device_map="balanced",
                max_memory={0: str(payload.get("gpu_memory_limit", "7GiB")), "cpu": str(payload.get("cpu_memory_limit", "14GiB"))},
                local_files_only=True,
                low_cpu_mem_usage=True,
            )
            vae = pipeline.vae
        else:
            vae = AutoencoderKLWan.from_pretrained(
                model_path,
                subfolder="vae",
                torch_dtype=torch.float32,
                local_files_only=True,
            )
            pipeline = WanPipeline.from_pretrained(
                model_path,
                vae=vae,
                torch_dtype=torch.bfloat16,
                local_files_only=True,
                low_cpu_mem_usage=True,
            )
        for method in ("enable_slicing",):
            callback = getattr(vae, method, None)
            if callback is not None:
                callback()
        # Spatial tiling is useful only when a full VAE decode cannot fit. On
        # the 512/640px acceptance sizes it can introduce visible grid seams,
        # so it is an explicit opt-in rather than an unconditional default.
        if bool(payload.get("vae_tiling", False)):
            callback = getattr(vae, "enable_tiling", None)
            if callback is not None:
                callback()
        pipeline.scheduler = UniPCMultistepScheduler.from_config(
            pipeline.scheduler.config,
            flow_shift=float(payload.get("flow_shift", 3.0)),
        )
        _enable_offload(pipeline, offload_mode)
        pipeline.set_progress_bar_config(disable=True)

        generator = torch.Generator(device="cpu")
        seed = payload.get("seed")
        if seed is not None:
            generator.manual_seed(int(seed))
        frames = pipeline(
            prompt=str(payload["prompt"]),
            negative_prompt=str(payload.get("negative_prompt") or ""),
            height=height,
            width=width,
            num_frames=frame_count,
            num_inference_steps=int(payload.get("steps", 30)),
            guidance_scale=float(payload.get("guidance_scale", 5.0)),
            max_sequence_length=int(payload.get("max_sequence_length", 512)),
            generator=generator,
        ).frames[0]
        if len(frames) != requested_frame_count:
            raise RuntimeError(
                "Wan temporal decode returned "
                f"{len(frames)} frames for requested {requested_frame_count} "
                f"(pipeline requested {frame_count})"
            )
        _encode_frames(frames, output_path, int(payload.get("fps", 15)))
        result = {
            "ok": True,
            "seconds": round(time.perf_counter() - started, 2),
            "peak_gpu_mb": round(torch.cuda.max_memory_allocated() / 1024 / 1024),
            "frames": len(frames),
            "pipeline_frames": frame_count,
            "output_path": str(output_path),
        }
    except Exception as exc:
        result = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
    finally:
        try:
            del pipeline, vae
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

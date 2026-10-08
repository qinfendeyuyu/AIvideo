"""Read-only probe for the local VACE safetensors checkpoint.

The script deliberately keeps only one tensor alive at a time so failures can
be attributed to mapping, dtype conversion, or CUDA transfer without building
the full diffusion model.
"""

from __future__ import annotations

import argparse
import gc
from pathlib import Path

import torch
from safetensors import safe_open


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("checkpoint", type=Path)
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cpu")
    args = parser.parse_args()

    print(f"checkpoint={args.checkpoint}", flush=True)
    print(f"bytes={args.checkpoint.stat().st_size}", flush=True)
    with safe_open(str(args.checkpoint), framework="pt", device="cpu") as handle:
        keys = list(handle.keys())
        print(f"tensor_count={len(keys)}", flush=True)
        for index, key in enumerate(keys, start=1):
            tensor = handle.get_tensor(key)
            converted = tensor.to(dtype=torch.bfloat16, device=args.device)
            # Force the asynchronous CUDA copy to complete while the current
            # key is still visible in the log.
            if args.device == "cuda":
                torch.cuda.synchronize()
            if index == 1 or index % 25 == 0 or index == len(keys):
                print(
                    f"ok={index}/{len(keys)} key={key} "
                    f"shape={tuple(tensor.shape)} dtype={tensor.dtype}",
                    flush=True,
                )
            del converted, tensor
            if args.device == "cuda":
                torch.cuda.empty_cache()

    gc.collect()
    print("probe=passed", flush=True)


if __name__ == "__main__":
    main()

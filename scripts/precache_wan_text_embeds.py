"""
Pre-cache Wan T5 text embeds.
Streams safetensors into the model (no full state_dict resident) to fit 8GB VRAM / tight commit.
"""
from __future__ import annotations

import gc
import hashlib
import json
import logging
import struct
import sys
import types
from pathlib import Path

import numpy as np

COMFY = Path(r"D:\ComfyUI")
WRAPPER = COMFY / "custom_nodes" / "ComfyUI-WanVideoWrapper"
CACHE = WRAPPER / "text_embed_cache"
MODEL = COMFY / "models" / "text_encoders" / "umt5-xxl-enc-fp8_e4m3fn.safetensors"
TOKENIZER = WRAPPER / "configs" / "T5_tokenizer"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
log = logging.getLogger("precache")


def cache_file(prompt: str) -> Path:
    h = hashlib.sha256(prompt.strip().encode("utf-8")).hexdigest()
    return CACHE / f"{h}.pt"


def register_packages() -> None:
    sys.path.insert(0, str(COMFY))

    def ensure(name: str, path: Path) -> None:
        if name in sys.modules:
            return
        mod = types.ModuleType(name)
        mod.__path__ = [str(path)]  # type: ignore[attr-defined]
        sys.modules[name] = mod

    ensure("ww", WRAPPER)
    ensure("ww.wanvideo", WRAPPER / "wanvideo")
    ensure("ww.wanvideo.modules", WRAPPER / "wanvideo" / "modules")
    sys.modules["wanvideo"] = sys.modules["ww.wanvideo"]
    sys.modules["wanvideo.modules"] = sys.modules["ww.wanvideo.modules"]


def convert_key(key: str, has_shared: bool) -> str:
    if not has_shared:
        return key
    if key.startswith("encoder.block."):
        parts = key.split(".")
        block_num = parts[2]
        rest = ".".join(parts[3:])
        mapping = {
            "layer.0.SelfAttention.q.weight": f"blocks.{block_num}.attn.q.weight",
            "layer.0.SelfAttention.k.weight": f"blocks.{block_num}.attn.k.weight",
            "layer.0.SelfAttention.v.weight": f"blocks.{block_num}.attn.v.weight",
            "layer.0.SelfAttention.o.weight": f"blocks.{block_num}.attn.o.weight",
            "layer.0.SelfAttention.relative_attention_bias.weight": f"blocks.{block_num}.pos_embedding.embedding.weight",
            "layer.0.layer_norm.weight": f"blocks.{block_num}.norm1.weight",
            "layer.1.layer_norm.weight": f"blocks.{block_num}.norm2.weight",
            "layer.1.DenseReluDense.wi_0.weight": f"blocks.{block_num}.ffn.gate.0.weight",
            "layer.1.DenseReluDense.wi_1.weight": f"blocks.{block_num}.ffn.fc1.weight",
            "layer.1.DenseReluDense.wo.weight": f"blocks.{block_num}.ffn.fc2.weight",
        }
        return mapping.get(rest, key)
    if key == "shared.weight":
        return "token_embedding.weight"
    if key == "encoder.final_layer_norm.weight":
        return "norm.weight"
    return key


def iter_safetensors(path: Path):
    import torch

    dtype_map = {
        "F64": torch.float64,
        "F32": torch.float32,
        "F16": torch.float16,
        "BF16": torch.bfloat16,
        "I64": torch.int64,
        "I32": torch.int32,
        "I16": torch.int16,
        "I8": torch.int8,
        "U8": torch.uint8,
        "BOOL": torch.bool,
    }
    for attr, key in [("float8_e4m3fn", "F8_E4M3"), ("float8_e5m2", "F8_E5M2")]:
        dt = getattr(torch, attr, None)
        if dt is not None:
            dtype_map[key] = dt

    with open(path, "rb") as f:
        hlen = struct.unpack("<Q", f.read(8))[0]
        header = json.loads(f.read(hlen))
        data_base = 8 + hlen
        has_shared = "shared.weight" in header
        keys = [k for k in header if k != "__metadata__"]
        log.info("Streaming %d tensors from %s (shared=%s)", len(keys), path.name, has_shared)
        for i, k in enumerate(keys, 1):
            meta = header[k]
            start, end = meta["data_offsets"]
            n_bytes = end - start
            f.seek(data_base + start)
            buf = np.empty(n_bytes, dtype=np.uint8)
            f.readinto(memoryview(buf))
            tdtype = dtype_map.get(meta["dtype"], torch.float32)
            tensor = torch.from_numpy(buf).view(tdtype).reshape(meta["shape"]).clone()
            del buf
            yield i, len(keys), convert_key(k, has_shared), tensor


def main() -> int:
    workflows_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(r"E:\AI漫剧\ai-comic-drama\workflows")
    CACHE.mkdir(parents=True, exist_ok=True)

    register_packages()
    import importlib
    import torch
    from accelerate.utils import set_module_tensor_to_device

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    use_gpu = device.type == "cuda"
    if use_gpu:
        torch.cuda.empty_cache()
        free, total = torch.cuda.mem_get_info()
        log.info("GPU=%s free=%.2f/%.2f GB", torch.cuda.get_device_name(0), free / 1024**3, total / 1024**3)

    T5EncoderModel = importlib.import_module("wanvideo.modules.t5").T5EncoderModel

    needed: list[str] = []
    seen = set()
    for wf in sorted(workflows_dir.glob("wan14b_photoreal_*_api.json")):
        node = json.loads(wf.read_text(encoding="utf-8"))["1"]["inputs"]
        for kind in ("positive_prompt", "negative_prompt"):
            p = node[kind]
            hit = cache_file(p).exists()
            log.info("%s %s: %s", wf.name, kind, "HIT" if hit else "MISS")
            if not hit and p not in seen:
                seen.add(p)
                needed.append(p)
    if not needed:
        log.info("All caches present")
        return 0

    # Build empty model; stream weights in one-by-one.
    # GPU: keep fp8. CPU: cast to bf16 (fp8 Linear unsupported on CPU).
    encoder = T5EncoderModel(
        text_len=512,
        dtype=torch.bfloat16,
        device=device,
        state_dict={},  # unused; we materialize manually
        tokenizer_path=str(TOKENIZER),
        quantization="fp8_e4m3fn" if use_gpu else "disabled",
    )
    keep = {"norm", "pos_embedding", "token_embedding"}
    param_names = {n for n, _ in encoder.model.named_parameters()}

    for i, n, name, tensor in iter_safetensors(MODEL):
        if name not in param_names:
            del tensor
            continue
        if use_gpu:
            dtype_to_use = torch.bfloat16 if any(k in name for k in keep) else torch.float8_e4m3fn
            if tensor.dtype != dtype_to_use and dtype_to_use != torch.float8_e4m3fn:
                tensor = tensor.to(dtype_to_use)
            set_module_tensor_to_device(encoder.model, name, device=device, dtype=dtype_to_use, value=tensor)
        else:
            tensor = tensor.to(torch.bfloat16)
            set_module_tensor_to_device(encoder.model, name, device=device, dtype=torch.bfloat16, value=tensor)
        del tensor
        if i % 40 == 0:
            log.info("  materialized %d/%d", i, n)
            gc.collect()
            if use_gpu:
                torch.cuda.empty_cache()
                log.info("  VRAM alloc=%.2fGB", torch.cuda.memory_allocated() / 1024**3)

    encoder.state_dict = None
    gc.collect()
    if use_gpu:
        torch.cuda.empty_cache()
        log.info("Ready. VRAM alloc=%.2fGB; encoding %d prompts", torch.cuda.memory_allocated() / 1024**3, len(needed))
    else:
        log.info("Ready on CPU bf16; encoding %d prompts", len(needed))

    for i, prompt in enumerate(needed, 1):
        out = cache_file(prompt)
        log.info("[%d/%d] -> %s", i, len(needed), out.name)
        with torch.inference_mode():
            if use_gpu:
                with torch.autocast(device_type="cuda", dtype=torch.bfloat16, enabled=True):
                    emb = encoder([prompt], device)
            else:
                emb = encoder([prompt], device)
        if isinstance(emb, list):
            emb = [e.detach().to("cpu") for e in emb]
        else:
            emb = emb.detach().to("cpu")
        torch.save(emb, out)
        del emb
        gc.collect()
        if use_gpu:
            torch.cuda.empty_cache()

    log.info("DONE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

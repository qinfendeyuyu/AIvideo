"""Validate the official Wan VAE without the project's low-VRAM tile shim.

This produces only a local round-trip frame from a project-owned image.  It
lets the action pipeline distinguish a model/weight problem from a custom
tiling problem before a long commercial test render is started.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", required=True)
    parser.add_argument("--vae", required=True)
    parser.add_argument("--image", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--frames", type=int, default=5)
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cuda")
    args = parser.parse_args()

    import torch
    import torch.nn.functional as functional
    from PIL import Image
    from torchvision.transforms.functional import to_tensor

    sys.path.insert(0, args.source_root)
    from wan.modules.vae import WanVAE

    image = Image.open(args.image).convert("RGB")
    pixels = to_tensor(image).sub(0.5).div(0.5)
    pixels = functional.interpolate(
        pixels.unsqueeze(0), size=(832, 480), mode="bilinear", align_corners=False
    ).squeeze(0)
    video = pixels.unsqueeze(1).repeat(1, args.frames, 1, 1).to(args.device)

    vae = WanVAE(vae_pth=args.vae, device=args.device)
    with torch.inference_mode():
        latent = vae.encode([video])[0]
        decoded = vae.decode([latent])[0][:, 0]
    output = ((decoded.clamp(-1, 1) + 1) * 127.5).to(torch.uint8)
    result = Image.fromarray(output.permute(1, 2, 0).cpu().numpy())
    destination = Path(args.output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    result.save(destination)
    print(f"ROUNDTRIP_OK={destination}")
    print(f"LATENT_SHAPE={tuple(latent.shape)}")


if __name__ == "__main__":
    main()

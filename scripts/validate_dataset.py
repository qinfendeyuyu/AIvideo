"""Validate LoRA training data before any GPU time is spent."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image


IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(1_048_576), b""):
            digest.update(block)
    return digest.hexdigest()


def validate_dataset(dataset_dir: Path, *, min_images: int, min_side: int) -> dict[str, object]:
    if not dataset_dir.exists():
        raise FileNotFoundError(f"Dataset dir not found: {dataset_dir}")
    images = sorted(path for path in dataset_dir.rglob("*") if path.suffix.lower() in IMAGE_EXTENSIONS)
    captions = sorted(dataset_dir.rglob("*.txt"))
    caption_names = {path.with_suffix("").relative_to(dataset_dir).as_posix() for path in captions}
    image_names = {path.with_suffix("").relative_to(dataset_dir).as_posix() for path in images}
    missing_captions = [path for path in images if path.with_suffix("").relative_to(dataset_dir).as_posix() not in caption_names]
    orphan_captions = [path for path in captions if path.with_suffix("").relative_to(dataset_dir).as_posix() not in image_names]
    invalid_images: list[str] = []
    small_images: list[str] = []
    blank_captions: list[str] = []
    duplicates: list[list[str]] = []
    hashes: dict[str, list[str]] = {}

    for image_path in images:
        relative = image_path.relative_to(dataset_dir).as_posix()
        try:
            with Image.open(image_path) as image:
                image.verify()
            with Image.open(image_path) as image:
                if min(image.size) < min_side:
                    small_images.append(relative)
        except OSError:
            invalid_images.append(relative)
        hashes.setdefault(file_hash(image_path), []).append(relative)
    duplicates = [paths for paths in hashes.values() if len(paths) > 1]
    for caption in captions:
        if not caption.read_text(encoding="utf-8").strip():
            blank_captions.append(caption.relative_to(dataset_dir).as_posix())

    report: dict[str, object] = {
        "dataset": str(dataset_dir.resolve()),
        "image_count": len(images),
        "caption_count": len(captions),
        "minimum_required_images": min_images,
        "missing_captions": [path.relative_to(dataset_dir).as_posix() for path in missing_captions],
        "orphan_captions": [path.relative_to(dataset_dir).as_posix() for path in orphan_captions],
        "invalid_images": invalid_images,
        "small_images": small_images,
        "blank_captions": blank_captions,
        "exact_duplicate_groups": duplicates,
    }
    failures = (
        len(images) < min_images
        or missing_captions
        or invalid_images
        or small_images
        or blank_captions
        or duplicates
    )
    report["ok"] = not bool(failures)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate character/style LoRA image-caption pairs")
    parser.add_argument("dataset", nargs="?", default="data/inputs/training")
    parser.add_argument("--min-images", type=int, default=80)
    parser.add_argument("--min-side", type=int, default=768)
    parser.add_argument("--report", help="Optional JSON report path")
    args = parser.parse_args()
    report = validate_dataset(Path(args.dataset), min_images=args.min_images, min_side=args.min_side)
    text = json.dumps(report, ensure_ascii=False, indent=2)
    print(text)
    if args.report:
        Path(args.report).write_text(text, encoding="utf-8")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
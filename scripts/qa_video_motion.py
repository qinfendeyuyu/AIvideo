"""Decode videos and report reproducible motion/sharpness diagnostics."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import cv2
import numpy as np


def inspect_video(path: Path) -> dict[str, object]:
    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        raise RuntimeError(f"Cannot open video: {path}")

    frames: list[np.ndarray] = []
    while True:
        ok, frame = capture.read()
        if not ok:
            break
        frames.append(frame)
    fps = float(capture.get(cv2.CAP_PROP_FPS))
    capture.release()

    if not frames:
        raise RuntimeError(f"No decoded frames: {path}")

    frame_hashes = [hashlib.sha256(frame.tobytes()).hexdigest() for frame in frames]
    adjacent = [
        float(cv2.absdiff(previous, current).mean())
        for previous, current in zip(frames, frames[1:])
    ]
    laplacian = [
        float(cv2.Laplacian(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY), cv2.CV_64F).var())
        for frame in frames
    ]
    # These VACE probes use a centered full-body composition.  Track a fixed
    # upper-center region that contains the face in every frame; naming it a
    # region (rather than a detected face) keeps the diagnostic honest and
    # reproducible without external detector weights.
    upper_center_laplacian: list[float] = []
    for frame in frames:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        height, width = gray.shape
        region = gray[
            int(height * 0.08) : int(height * 0.32),
            int(width * 0.35) : int(width * 0.65),
        ]
        upper_center_laplacian.append(
            float(cv2.Laplacian(region, cv2.CV_64F).var())
        )

    return {
        "path": str(path.resolve()),
        "bytes": path.stat().st_size,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "width": int(frames[0].shape[1]),
        "height": int(frames[0].shape[0]),
        "fps": fps,
        "decoded_frames": len(frames),
        "unique_decoded_frames": len(set(frame_hashes)),
        "adjacent_frame_mean_absolute_difference": {
            "mean": float(np.mean(adjacent)) if adjacent else 0.0,
            "min": float(np.min(adjacent)) if adjacent else 0.0,
            "max": float(np.max(adjacent)) if adjacent else 0.0,
        },
        "grayscale_laplacian_variance": {
            "mean": float(np.mean(laplacian)),
            "min": float(np.min(laplacian)),
            "max": float(np.max(laplacian)),
        },
        "upper_center_region_laplacian_variance": {
            "normalized_roi_xyxy": [0.35, 0.08, 0.65, 0.32],
            "mean": float(np.mean(upper_center_laplacian)),
            "min": float(np.min(upper_center_laplacian)),
            "max": float(np.max(upper_center_laplacian)),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("videos", nargs="+", type=Path)
    args = parser.parse_args()
    print(json.dumps([inspect_video(path) for path in args.videos], indent=2))


if __name__ == "__main__":
    main()

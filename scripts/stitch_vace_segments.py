"""Blend retained VACE overlap frames and encode a continuous MP4."""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

import cv2
import numpy as np


def decode(path: Path) -> list[np.ndarray]:
    capture = cv2.VideoCapture(str(path))
    frames: list[np.ndarray] = []
    while True:
        ok, frame = capture.read()
        if not ok:
            break
        frames.append(frame)
    capture.release()
    if not frames:
        raise RuntimeError(f"No decoded frames: {path}")
    return frames


def encode(frames: list[np.ndarray], output: Path, fps: int, crf: int) -> None:
    height, width = frames[0].shape[:2]
    output.parent.mkdir(parents=True, exist_ok=True)
    command = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-f",
        "rawvideo",
        "-pix_fmt",
        "bgr24",
        "-s",
        f"{width}x{height}",
        "-r",
        str(fps),
        "-i",
        "-",
        "-an",
        "-c:v",
        "libx264",
        "-preset",
        "slow",
        "-crf",
        str(crf),
        "-pix_fmt",
        "yuv420p",
        "-color_primaries",
        "bt709",
        "-color_trc",
        "bt709",
        "-colorspace",
        "bt709",
        "-movflags",
        "+faststart",
        str(output),
    ]
    process = subprocess.Popen(command, stdin=subprocess.PIPE)
    assert process.stdin is not None
    try:
        for frame in frames:
            process.stdin.write(np.ascontiguousarray(frame).tobytes())
    finally:
        process.stdin.close()
    return_code = process.wait()
    if return_code:
        raise RuntimeError(f"ffmpeg failed with exit code {return_code}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("previous", type=Path)
    parser.add_argument("continuation", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--overlap", type=int, default=6)
    parser.add_argument("--fps", type=int, default=16)
    parser.add_argument("--crf", type=int, default=14)
    args = parser.parse_args()

    previous = decode(args.previous)
    continuation = decode(args.continuation)
    if len(previous) < args.overlap or len(continuation) <= args.overlap:
        raise RuntimeError("Videos are shorter than the requested overlap")
    if previous[0].shape != continuation[0].shape:
        raise RuntimeError("Segment dimensions do not match")

    blended_overlap: list[np.ndarray] = []
    denominator = max(args.overlap - 1, 1)
    for index, (old_frame, new_frame) in enumerate(
        zip(previous[-args.overlap :], continuation[: args.overlap])
    ):
        alpha = index / denominator
        blended_overlap.append(
            cv2.addWeighted(old_frame, 1.0 - alpha, new_frame, alpha, 0.0)
        )

    stitched = (
        previous[: -args.overlap]
        + blended_overlap
        + continuation[args.overlap :]
    )
    encode(stitched, args.output, args.fps, args.crf)
    print(f"STITCHED_OUTPUT={args.output.resolve()}")
    print(f"STITCHED_FRAMES={len(stitched)}")


if __name__ == "__main__":
    main()

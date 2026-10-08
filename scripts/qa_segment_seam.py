"""Measure retained overlap fidelity and the visible append seam."""

from __future__ import annotations

import argparse
import json
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


def difference(first: np.ndarray, second: np.ndarray) -> float:
    return float(cv2.absdiff(first, second).mean())


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("previous", type=Path)
    parser.add_argument("continuation", type=Path)
    parser.add_argument("--overlap", type=int, default=6)
    args = parser.parse_args()

    previous = decode(args.previous)
    continuation = decode(args.continuation)
    if len(previous) < args.overlap or len(continuation) <= args.overlap:
        raise RuntimeError("Videos are shorter than the requested overlap")

    retained_differences = [
        difference(source, retained)
        for source, retained in zip(previous[-args.overlap :], continuation[: args.overlap])
    ]
    previous_adjacent = [
        difference(a, b) for a, b in zip(previous, previous[1:])
    ]
    continuation_adjacent = [
        difference(a, b) for a, b in zip(continuation, continuation[1:])
    ]
    append_seam = difference(previous[-1], continuation[args.overlap])

    print(
        json.dumps(
            {
                "overlap_frames": args.overlap,
                "retained_overlap_mae": {
                    "per_frame": retained_differences,
                    "mean": float(np.mean(retained_differences)),
                    "max": float(np.max(retained_differences)),
                },
                "previous_adjacent_mae": {
                    "mean": float(np.mean(previous_adjacent)),
                    "last_pair": previous_adjacent[-1],
                },
                "continuation_adjacent_mae": {
                    "mean": float(np.mean(continuation_adjacent)),
                    "transition_from_retained_to_generated": continuation_adjacent[
                        args.overlap - 1
                    ],
                },
                "stitched_append_seam_mae": append_seam,
                "stitched_frame_count": len(previous)
                + len(continuation)
                - args.overlap,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

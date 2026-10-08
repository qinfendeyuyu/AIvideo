"""Build VACE first-clip extension video and mask from a finished segment."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

import cv2
import numpy as np


def encode_video(frames: list[np.ndarray], output: Path, fps: int) -> None:
    height, width = frames[0].shape[:2]
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
        "0",
        "-pix_fmt",
        "yuv420p",
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
        raise RuntimeError(f"ffmpeg failed with exit code {return_code}: {output}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("previous_video", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--total-frames", type=int, default=17)
    parser.add_argument("--keep-frames", type=int, default=6)
    parser.add_argument("--fps", type=int, default=16)
    args = parser.parse_args()

    if not 1 <= args.keep_frames < args.total_frames:
        raise ValueError("keep-frames must be between 1 and total-frames - 1")

    capture = cv2.VideoCapture(str(args.previous_video))
    decoded: list[np.ndarray] = []
    while True:
        ok, frame = capture.read()
        if not ok:
            break
        decoded.append(frame)
    capture.release()
    if len(decoded) < args.keep_frames:
        raise RuntimeError(
            f"Need {args.keep_frames} source frames, decoded only {len(decoded)}"
        )

    retained = decoded[-args.keep_frames :]
    height, width = retained[0].shape[:2]
    missing_count = args.total_frames - args.keep_frames
    source_frames = retained + [
        # RGB 128 maps closest to VACE's normalized zero for unknown pixels.
        np.full((height, width, 3), 128, dtype=np.uint8)
        for _ in range(missing_count)
    ]
    mask_frames = [
        np.zeros((height, width, 3), dtype=np.uint8)
        for _ in range(args.keep_frames)
    ] + [
        np.full((height, width, 3), 255, dtype=np.uint8)
        for _ in range(missing_count)
    ]

    args.output_dir.mkdir(parents=True, exist_ok=True)
    source_path = args.output_dir / "firstclip_source.mp4"
    mask_path = args.output_dir / "firstclip_mask.mp4"
    last_frame_path = args.output_dir / "previous_last_frame.png"
    encode_video(source_frames, source_path, args.fps)
    encode_video(mask_frames, mask_path, args.fps)
    encoded_ok, encoded_png = cv2.imencode(".png", retained[-1])
    if not encoded_ok:
        raise RuntimeError(f"Could not write: {last_frame_path}")
    last_frame_path.write_bytes(encoded_png.tobytes())

    print(
        json.dumps(
            {
                "source_video": str(source_path.resolve()),
                "source_mask": str(mask_path.resolve()),
                "previous_last_frame": str(last_frame_path.resolve()),
                "total_frames": args.total_frames,
                "retained_prefix_frames": args.keep_frames,
                "generated_suffix_frames": missing_count,
                "fps": args.fps,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

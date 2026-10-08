"""Sequential Wan I2V batch for ~3min local episode (resume-safe).

Reads storyboard JSON, submits ComfyUI workflows one-by-one (81f @ 16fps),
chains last-frame starts within scenes, writes progress.json for resume.
"""
from __future__ import annotations

import argparse
import copy
import json
import shutil
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_PATH = ROOT / "workflows" / "toonflow_local_wan_i2v_template.json"
DEFAULT_STORYBOARD = ROOT / "data" / "outputs" / "wan_3min_local_20260927" / "storyboard_3min.json"
DEFAULT_OUT = ROOT / "data" / "outputs" / "wan_3min_local_20260927"
COMFY_INPUT = ROOT / "runtime_cache" / "comfy_input"
COMFY_OUTPUT = ROOT / "runtime_cache" / "comfy_output" / "toonflow_local"


def _http_json(method: str, url: str, payload: dict | None = None, timeout: float = 60.0) -> dict:
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _expand_prompt(shot: dict, character_lock: str) -> str:
    return str(shot["prompt"]).replace("{char}", character_lock)


def _load_progress(path: Path) -> dict:
    if path.is_file():
        return json.loads(path.read_text(encoding="utf-8"))
    return {"completed": {}, "failed": {}, "started_at": time.time()}


def _save_progress(path: Path, progress: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(progress, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def _extract_last_frame(mp4: Path, png: Path, ffmpeg: str) -> None:
    import subprocess

    png.parent.mkdir(parents=True, exist_ok=True)
    attempts = [
        [ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-i", str(mp4), "-vf", "reverse", "-frames:v", "1", str(png)],
        [ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-sseof", "-0.15", "-i", str(mp4), "-frames:v", "1", str(png)],
        [ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-i", str(mp4), "-update", "1", "-q:v", "2", str(png)],
    ]
    last_err: Exception | None = None
    for cmd in attempts:
        try:
            subprocess.run(cmd, check=True)
            if png.is_file() and png.stat().st_size > 0:
                return
        except Exception as exc:  # noqa: BLE001
            last_err = exc
    raise RuntimeError(f"failed to extract last frame from {mp4}: {last_err}")


def _build_workflow(
    *,
    prompt: str,
    negative: str,
    start_rel: str,
    num_frames: int,
    frame_rate: float,
    seed: int,
    filename_prefix: str,
) -> dict:
    wf = copy.deepcopy(json.loads(TEMPLATE_PATH.read_text(encoding="utf-8")))
    wf["1"]["inputs"]["positive_prompt"] = prompt
    wf["1"]["inputs"]["negative_prompt"] = negative
    wf["3"]["inputs"]["image"] = start_rel
    wf["7"]["inputs"]["num_frames"] = int(num_frames)
    wf["7"]["inputs"]["tiled_vae"] = True
    wf["7"]["inputs"]["force_offload"] = True
    wf["9"]["inputs"]["blocks_to_swap"] = 40
    wf["9"]["inputs"]["offload_img_emb"] = True
    wf["9"]["inputs"]["offload_txt_emb"] = True
    wf["11"]["inputs"]["seed"] = int(seed)
    wf["11"]["inputs"]["force_offload"] = True
    wf["12"]["inputs"]["enable_vae_tiling"] = True
    wf["13"]["inputs"]["filename_prefix"] = filename_prefix
    wf["13"]["inputs"]["frame_rate"] = float(frame_rate)
    return wf


def _wait_prompt(comfy: str, prompt_id: str, timeout_min: float) -> dict:
    deadline = time.monotonic() + timeout_min * 60.0
    while time.monotonic() < deadline:
        try:
            hist = _http_json("GET", f"{comfy}/history/{prompt_id}", timeout=30.0)
        except urllib.error.URLError:
            time.sleep(10)
            continue
        rec = hist.get(prompt_id)
        if rec is not None:
            status = rec.get("status") or {}
            if status.get("completed") or status.get("status_str") == "error":
                return rec
        time.sleep(15)
    raise TimeoutError(f"Comfy prompt timed out: {prompt_id}")


def _find_mp4(task_tag: str, history: dict) -> Path | None:
    outputs = history.get("outputs") or {}
    for node_out in outputs.values():
        for key in ("gifs", "videos"):
            for item in node_out.get(key) or []:
                full = item.get("fullpath")
                if full and Path(full).is_file():
                    return Path(full)
                filename = item.get("filename")
                sub = item.get("subfolder") or ""
                if filename:
                    cand = COMFY_OUTPUT.parent / sub / filename if sub else COMFY_OUTPUT / filename
                    # VHS often writes under toonflow_local/
                    for base in (COMFY_OUTPUT, COMFY_OUTPUT.parent / sub if sub else COMFY_OUTPUT):
                        p = Path(base) / filename
                        if p.is_file():
                            return p
    matches = sorted(COMFY_OUTPUT.glob(f"{task_tag}*.mp4"), key=lambda p: p.stat().st_mtime, reverse=True)
    return matches[0] if matches else None


def run_batch(args: argparse.Namespace) -> int:
    storyboard = json.loads(Path(args.storyboard).read_text(encoding="utf-8"))
    out_dir = Path(args.out_dir)
    clips_dir = out_dir / "clips_16fps"
    frames_dir = out_dir / "chain_frames"
    keys_dir = out_dir / "keyframes"
    progress_path = out_dir / "progress.json"
    clips_dir.mkdir(parents=True, exist_ok=True)
    frames_dir.mkdir(parents=True, exist_ok=True)

    progress = _load_progress(progress_path)
    shots: list[dict] = storyboard["shots"]
    char = storyboard["character_lock"]
    negative = storyboard["negative_prompt"]
    num_frames = int(storyboard.get("num_frames") or 81)
    fps = float(storyboard.get("native_fps") or 16)
    comfy = args.comfy.rstrip("/")

    print(
        f"[3min] shots={len(shots)} frames={num_frames} fps={fps} "
        f"~{len(shots) * num_frames / fps:.1f}s native → out={out_dir}"
    )

    prev_last: Path | None = None
    for idx, shot in enumerate(shots):
        sid = shot["id"]
        dst = clips_dir / f"{idx:02d}_{sid}.mp4"
        last_png = frames_dir / f"{idx:02d}_{sid}_last.png"

        if sid in progress.get("completed", {}) and dst.is_file():
            print(f"[skip] {sid} already done", flush=True)
            prev_last = Path(progress["completed"][sid].get("last_frame") or last_png)
            if not prev_last.is_file():
                _extract_last_frame(dst, last_png, args.ffmpeg)
                prev_last = last_png
                progress["completed"][sid]["last_frame"] = str(last_png)
                _save_progress(progress_path, progress)
            continue

        # Resolve start image
        if shot.get("chain"):
            if not (prev_last and prev_last.is_file()):
                # Resume safety: rebuild from previous completed clip if needed.
                if idx > 0:
                    prev = shots[idx - 1]
                    prev_dst = clips_dir / f"{idx - 1:02d}_{prev['id']}.mp4"
                    prev_png = frames_dir / f"{idx - 1:02d}_{prev['id']}_last.png"
                    if prev_dst.is_file() and not prev_png.is_file():
                        _extract_last_frame(prev_dst, prev_png, args.ffmpeg)
                    prev_last = prev_png if prev_png.is_file() else None
            if prev_last and prev_last.is_file():
                start_src = prev_last
            elif shot.get("start_key"):
                start_src = keys_dir / str(shot["start_key"])
            else:
                raise RuntimeError(f"{sid}: chain shot has no previous last-frame or start_key")
        else:
            key = shot.get("start_key")
            if not key:
                raise RuntimeError(f"{sid}: non-chain shot missing start_key")
            start_src = keys_dir / key
        if not start_src.is_file():
            raise RuntimeError(f"{sid}: missing start image {start_src}")

        task_tag = f"ep3m_{sid}_{uuid.uuid4().hex[:8]}"
        rel = Path("toonflow_jobs") / "ep3m" / task_tag / "start.png"
        abs_start = COMFY_INPUT / rel
        abs_start.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(start_src, abs_start)

        prompt = _expand_prompt(shot, char)
        wf = _build_workflow(
            prompt=prompt,
            negative=negative,
            start_rel=rel.as_posix(),
            num_frames=num_frames,
            frame_rate=fps,
            seed=int(shot["seed"]),
            filename_prefix=f"toonflow_local/{task_tag}",
        )

        print(f"[run ] {idx + 1}/{len(shots)} {sid} seed={shot['seed']} start={start_src.name}")
        t0 = time.time()
        try:
            queued = _http_json(
                "POST",
                f"{comfy}/prompt",
                {"prompt": wf, "client_id": str(uuid.uuid4())},
            )
            prompt_id = queued["prompt_id"]
            rec = _wait_prompt(comfy, prompt_id, timeout_min=args.timeout_minutes)
            status = rec.get("status") or {}
            if status.get("status_str") == "error" or not status.get("completed"):
                raise RuntimeError(f"Comfy error: {status}")
            mp4 = _find_mp4(task_tag, rec)
            if not mp4:
                raise RuntimeError("finished but mp4 missing")
            shutil.copy2(mp4, dst)
            _extract_last_frame(dst, last_png, args.ffmpeg)
            elapsed = round(time.time() - t0, 1)
            progress.setdefault("completed", {})[sid] = {
                "index": idx,
                "mp4": str(dst),
                "last_frame": str(last_png),
                "prompt_id": prompt_id,
                "source_mp4": str(mp4),
                "elapsed_sec": elapsed,
                "finished_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            }
            progress.get("failed", {}).pop(sid, None)
            _save_progress(progress_path, progress)
            prev_last = last_png
            print(f"[ok  ] {sid} {elapsed}s → {dst.name}")
        except Exception as exc:  # noqa: BLE001
            progress.setdefault("failed", {})[sid] = {
                "error": str(exc),
                "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            }
            _save_progress(progress_path, progress)
            print(f"[fail] {sid}: {exc}")
            if args.stop_on_fail:
                return 1
            # Do not chain from a failed shot
            prev_last = None
            if not shot.get("chain"):
                # keep going; next non-chain will use its keyframe
                pass

    done = len(progress.get("completed", {}))
    print(f"[3min] completed {done}/{len(shots)} → {progress_path}")
    return 0 if done == len(shots) else 2


def main() -> int:
    p = argparse.ArgumentParser(description="Run ~3min Wan I2V batch (resume-safe)")
    p.add_argument("--storyboard", default=str(DEFAULT_STORYBOARD))
    p.add_argument("--out-dir", default=str(DEFAULT_OUT))
    p.add_argument("--comfy", default="http://127.0.0.1:8188")
    p.add_argument("--ffmpeg", default=r"E:\FFmpeg\bin\ffmpeg.exe")
    p.add_argument("--timeout-minutes", type=float, default=120.0)
    p.add_argument("--stop-on-fail", action="store_true")
    return run_batch(p.parse_args())


if __name__ == "__main__":
    raise SystemExit(main())

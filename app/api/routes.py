from __future__ import annotations

import json
import re
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel, Field

from app.core.config import AppConfig
from app.core.readiness import build_readiness_report
from app.core.run_store import RunStore
from app.pipeline.episode_pipeline import EpisodePipeline
from app.schemas.project import EpisodeRequest, EpisodeResult

router = APIRouter(prefix="/api/v1", tags=["episode"])
config = AppConfig.load()
pipeline = EpisodePipeline(config)

STATIC_DIR = Path(__file__).resolve().parents[1] / "static"
STUDIO_HTML = STATIC_DIR / "studio.html"


class ScenePatch(BaseModel):
    narration: str | None = Field(default=None, min_length=1, max_length=2000)
    invalidate_audio: bool = True
    invalidate_clip: bool = True
    invalidate_image: bool = False


def _output_root() -> Path:
    return config.resolve_path(config.get("project", "output_root", default="data/outputs"))


def _run_dir(run_id: str) -> Path:
    if not re.fullmatch(r"[A-Za-z0-9_-]{3,80}", run_id):
        raise HTTPException(status_code=400, detail="Invalid run id")
    return _output_root() / run_id


def _safe_child(run_dir: Path, relative: str) -> Path:
    cleaned = relative.replace("\\", "/").lstrip("/")
    if not cleaned or ".." in Path(cleaned).parts:
        raise HTTPException(status_code=400, detail="Invalid asset path")
    target = (run_dir / cleaned).resolve()
    run_root = run_dir.resolve()
    if run_root not in target.parents and target != run_root:
        raise HTTPException(status_code=400, detail="Asset path escapes run directory")
    return target


def studio_page() -> HTMLResponse:
    if STUDIO_HTML.is_file():
        return HTMLResponse(STUDIO_HTML.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>studio.html missing</h1>", status_code=500)


@router.get("/health")
async def health() -> dict[str, object]:
    report = build_readiness_report(config, check_services=True)
    return {
        "status": "ok" if report.get("ready") else "degraded",
        "ready": bool(report.get("ready")),
        "demo_mode": bool(report.get("demo_mode")),
        "project_root": str(config.project_root),
        "video_backend": report.get("video_backend"),
        "llm_model": report.get("llm_model"),
        "checks": report.get("checks", {}),
    }


@router.get("/runs")
async def list_runs() -> dict[str, object]:
    root = _output_root()
    if not root.is_dir():
        return {"runs": []}
    runs: list[dict[str, object]] = []
    for path in sorted(root.iterdir(), key=lambda item: item.stat().st_mtime, reverse=True):
        if not path.is_dir():
            continue
        manifest_path = path / "manifest.json"
        if not manifest_path.is_file():
            continue
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        request = manifest.get("request") if isinstance(manifest.get("request"), dict) else {}
        runs.append(
            {
                "run_id": path.name,
                "status": manifest.get("status"),
                "title": request.get("title") or manifest.get("title"),
                "updated_at": manifest.get("updated_at"),
                "created_at": manifest.get("created_at"),
            }
        )
    return {"runs": runs}


@router.post("/episode", response_model=EpisodeResult)
async def generate_episode(payload: EpisodeRequest) -> EpisodeResult:
    try:
        return await pipeline.run(payload)
    except (ValueError, FileExistsError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/runs/{run_id}")
async def get_run(run_id: str) -> dict:
    try:
        store = RunStore.open(_run_dir(run_id))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    payload = dict(store.manifest)
    payload["output_dir"] = str(store.run_dir.resolve())
    return payload


@router.get("/runs/{run_id}/video")
async def get_run_video(run_id: str) -> FileResponse:
    run_dir = _run_dir(run_id)
    try:
        manifest = RunStore.open(run_dir).manifest
        filename = manifest.get("artifacts", {}).get("episode_video", "episode.mp4")
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    video_file = run_dir / str(filename)
    if not video_file.is_file():
        raise HTTPException(status_code=404, detail="Episode video is not available yet")
    return FileResponse(video_file, media_type="video/mp4", filename=f"{run_id}.mp4")


@router.get("/runs/{run_id}/file")
async def get_run_file(run_id: str, path: str) -> FileResponse:
    run_dir = _run_dir(run_id)
    target = _safe_child(run_dir, path)
    if not target.is_file():
        raise HTTPException(status_code=404, detail="Asset not found")
    return FileResponse(target)


@router.patch("/runs/{run_id}/scenes/{index}")
async def patch_scene(run_id: str, index: int, payload: ScenePatch) -> dict:
    if index < 1:
        raise HTTPException(status_code=400, detail="Scene index must be >= 1")
    run_dir = _run_dir(run_id)
    try:
        store = RunStore.open(run_dir)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    scene_key = str(index)
    scenes = store.manifest.setdefault("scenes", {})
    scene = scenes.setdefault(scene_key, {"index": index})
    updates: dict[str, object] = {}
    if payload.narration is not None:
        updates["narration"] = payload.narration

    storyboard_path = run_dir / "storyboard.json"
    if payload.narration is not None and storyboard_path.is_file():
        try:
            board = json.loads(storyboard_path.read_text(encoding="utf-8"))
            for item in board.get("scenes", []):
                if int(item.get("index", -1)) == index:
                    item["narration"] = payload.narration
                    break
            storyboard_path.write_text(json.dumps(board, ensure_ascii=False, indent=2), encoding="utf-8")
        except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
            raise HTTPException(status_code=500, detail=f"Failed to update storyboard: {exc}") from exc

    deleted: list[str] = []
    targets: list[Path] = []
    if payload.invalidate_audio:
        targets.append(run_dir / "audio" / f"scene_{index:02d}.wav")
    if payload.invalidate_clip:
        targets.extend(
            [
                run_dir / "clips" / f"scene_{index:02d}.mp4",
                run_dir / "clips" / f"motion_{index:02d}.mp4",
            ]
        )
    if payload.invalidate_image:
        targets.append(run_dir / "images" / f"scene_{index:02d}.png")
    # Final assemble products must be rebuilt after scene edits.
    targets.extend([run_dir / "episode_master.mp4", run_dir / "episode.mp4", run_dir / "subtitles.srt"])
    for target in targets:
        if target.exists():
            target.unlink()
            deleted.append(str(target.relative_to(run_dir)))

    updates["status"] = "pending_regen"
    store.update_scene(index, **updates)
    store.set_status("interrupted_edit")
    return {"ok": True, "scene": store.manifest["scenes"][scene_key], "deleted": deleted}

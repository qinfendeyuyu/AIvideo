"""Atomic, human-readable production manifest storage."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class RunStore:
    """Keeps every pipeline decision on disk so an interrupted run can resume."""

    filename = "manifest.json"

    def __init__(self, run_dir: Path, manifest: dict[str, Any]):
        self.run_dir = run_dir
        self.path = run_dir / self.filename
        self.manifest = manifest

    @classmethod
    def create(cls, run_dir: Path, initial: dict[str, Any]) -> "RunStore":
        manifest = {**initial, "created_at": utc_now(), "updated_at": utc_now(), "errors": []}
        store = cls(run_dir, manifest)
        store.save()
        return store

    @classmethod
    def open(cls, run_dir: Path) -> "RunStore":
        path = run_dir / cls.filename
        if not path.exists():
            raise FileNotFoundError(f"Cannot resume: manifest does not exist: {path}")
        try:
            manifest = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Cannot resume: manifest is invalid JSON: {path}") from exc
        if not isinstance(manifest, dict):
            raise RuntimeError(f"Cannot resume: manifest root must be an object: {path}")
        return cls(run_dir, manifest)

    def save(self) -> None:
        self.manifest["updated_at"] = utc_now()
        temp_path = self.path.with_suffix(".json.tmp")
        temp_path.write_text(
            json.dumps(self.manifest, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        temp_path.replace(self.path)

    def set_status(self, status: str, *, error: str | None = None) -> None:
        self.manifest["status"] = status
        if error:
            self.manifest.setdefault("errors", []).append({"at": utc_now(), "message": error})
        self.save()

    def update_scene(self, index: int, **values: Any) -> None:
        scenes = self.manifest.setdefault("scenes", {})
        scene = scenes.setdefault(str(index), {"index": index})
        scene.update(values)
        self.save()
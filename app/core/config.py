from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel


class AppConfig(BaseModel):
    """Configuration loaded once and resolved relative to the project root."""

    raw: dict[str, Any]
    source_path: Path

    @classmethod
    def load(cls, path: str = "configs/models.yaml") -> "AppConfig":
        config_path = Path(path)
        if not config_path.exists() and not config_path.is_absolute():
            # Let uvicorn be launched from any directory without breaking paths.
            config_path = Path(__file__).resolve().parents[2] / config_path
        if not config_path.exists() and path == "configs/models.yaml":
            # Public checkouts omit the private machine profile. Loading the
            # example keeps inspection/tests available; it installs no models
            # and never enables demo mode or a cloud fallback implicitly.
            config_path = Path(__file__).resolve().parents[2] / "configs/models.example.yaml"
        if not config_path.exists():
            raise FileNotFoundError(f"Config not found: {config_path}")
        with config_path.open("r", encoding="utf-8") as file:
            data = yaml.safe_load(file) or {}
        if not isinstance(data, dict):
            raise ValueError(f"Config root must be a mapping: {config_path}")
        return cls(raw=data, source_path=config_path.resolve())

    def get(self, *keys: str, default: Any = None) -> Any:
        current: Any = self.raw
        for key in keys:
            if not isinstance(current, dict) or key not in current:
                return default
            current = current[key]
        return current

    @property
    def project_root(self) -> Path:
        """Directory containing app/, configs/ and data/."""
        return self.source_path.parent.parent

    def resolve_path(self, value: str | Path) -> Path:
        path = Path(value)
        return path if path.is_absolute() else self.project_root / path

    def public_snapshot(self) -> dict[str, Any]:
        """A reproducibility snapshot that deliberately removes credentials."""
        snapshot = deepcopy(self.raw)
        for section in snapshot.values():
            if not isinstance(section, dict):
                continue
            for key in tuple(section):
                if any(token in key.lower() for token in ("key", "token", "secret", "password")):
                    section[key] = "***REDACTED***"
        return snapshot

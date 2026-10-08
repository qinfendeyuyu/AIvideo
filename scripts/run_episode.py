"""CLI entry point for a reproducible local episode run."""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.config import AppConfig
from app.pipeline.episode_pipeline import EpisodePipeline
from app.schemas.project import EpisodeRequest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate or resume one local AI comic-drama episode.")
    parser.add_argument("--config", default="configs/models.yaml", help="Model config YAML path")
    parser.add_argument(
        "--input", default="configs/episode.example.yaml", help="Episode brief YAML path"
    )
    parser.add_argument("--run-id", help="New run ID, or the existing ID when --resume is used")
    parser.add_argument("--resume", action="store_true", help="Reuse verified assets from an interrupted run")
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Explicit offline diagnostic mode; does not call real AI models",
    )
    return parser.parse_args()


def load_request(path: Path, args: argparse.Namespace) -> EpisodeRequest:
    if not path.exists():
        raise FileNotFoundError(f"Episode brief not found: {path}")
    with path.open("r", encoding="utf-8") as file:
        payload = yaml.safe_load(file) or {}
    if not isinstance(payload, dict):
        raise ValueError("Episode brief root must be a YAML mapping")
    payload.update({key: value for key, value in {"run_id": args.run_id, "resume": args.resume}.items() if value})
    return EpisodeRequest.model_validate(payload)


async def main() -> None:
    args = parse_args()
    config = AppConfig.load(args.config)
    if args.demo:
        # Force diagnostic mode even when models.yaml keeps demo_mode: false.
        config.raw.setdefault("project", {})
        config.raw["project"]["demo_mode"] = True
    request = load_request(ROOT / args.input if not Path(args.input).is_absolute() else Path(args.input), args)
    result = await EpisodePipeline(config).run(request)
    print(result.model_dump_json(indent=2))


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
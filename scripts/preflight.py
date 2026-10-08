"""Check the local production machine before starting an episode."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.config import AppConfig
from app.core.readiness import build_readiness_report


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Preflight checks for AI Comic Drama Local Studio")
    result.add_argument("--config", default="configs/models.yaml")
    result.add_argument("--check-services", action="store_true", help="Call configured local health endpoints")
    return result


def main() -> int:
    args = parser().parse_args()
    config = AppConfig.load(args.config)
    report = build_readiness_report(config, check_services=args.check_services)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report.get("ready") else 1


if __name__ == "__main__":
    raise SystemExit(main())

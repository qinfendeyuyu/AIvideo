"""Human-readable local studio status for Windows operators."""

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


LABELS = {
    "binary:ffmpeg": "FFmpeg",
    "binary:ffprobe": "FFprobe",
    "configured:video_motion": "动态后端",
    "configured:llm": "剧本 LLM",
    "configured:image": "出图后端",
    "configured:tts": "配音后端",
    "service:llm": "Ollama 服务",
    "demo_mode": "诊断模式",
}


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Print Chinese readiness status for the local studio")
    result.add_argument("--config", default="configs/models.yaml")
    result.add_argument("--json", action="store_true", help="Also print raw JSON report")
    result.add_argument("--check-services", action="store_true", default=True)
    result.add_argument("--skip-services", action="store_true")
    return result


def main() -> int:
    args = parser().parse_args()
    config = AppConfig.load(args.config)
    report = build_readiness_report(config, check_services=(args.check_services and not args.skip_services))
    ready = bool(report.get("ready"))
    print("AI 漫剧本地工作室状态")
    print("=" * 32)
    print(f"总览: {'就绪' if ready else '未就绪'}")
    print(f"配置: {report.get('config')}")
    print(f"视频后端: {report.get('video_backend')}")
    print(f"LLM 模型: {report.get('llm_model')}")
    print(f"demo_mode: {report.get('demo_mode')}")
    print("-" * 32)
    checks = report.get("checks", {})
    if isinstance(checks, dict):
        for key, payload in checks.items():
            if not isinstance(payload, dict):
                continue
            label = LABELS.get(key, key)
            ok = bool(payload.get("ok"))
            mark = "OK" if ok else "FAIL"
            extra = ""
            if "backend" in payload:
                extra = f" [{payload['backend']}]"
            elif "value" in payload:
                extra = f" = {payload['value']}"
            elif "status" in payload:
                extra = f" HTTP {payload['status']}"
            elif "error" in payload:
                extra = f" {payload['error']}"
            print(f"[{mark}] {label}{extra}")
    print("-" * 32)
    if ready:
        print("建议下一步:")
        print("  1) 近景试片:  .\\scripts\\local_studio.ps1 face")
        print("  2) 正式一集:  .\\scripts\\local_studio.ps1 episode -RunId season01_ep01")
        print("  3) 本地 API:  .\\scripts\\local_studio.ps1 api")
        print("注意: Wan14B 写实动态仍需 E: 页面文件生效（当前若 active_target_allocated_mb=0 请先重启）。")
    else:
        print("请先修复 FAIL 项，再启动正式生产。")
        print("Wan14B 写实动态另需 E: 页面文件生效（重启后 validate）。")
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if ready else 1


if __name__ == "__main__":
    raise SystemExit(main())

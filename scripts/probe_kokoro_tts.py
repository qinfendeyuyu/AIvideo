"""Probe Kokoro Mandarin TTS and write a rights ledger stub."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def main() -> int:
    parser = argparse.ArgumentParser(description="Probe local Kokoro Mandarin TTS")
    parser.add_argument("--text", required=True)
    parser.add_argument("--voice", default="zf_001")
    parser.add_argument("--output", default="data/outputs/kokoro_probe/probe.wav")
    parser.add_argument("--ledger", default="data/outputs/kokoro_probe/probe.ledger.json")
    parser.add_argument("--python", default=".venv-kokoro/Scripts/python.exe")
    parser.add_argument("--worker", default="app/workers/kokoro_worker.py")
    parser.add_argument("--repo-id", default="hexgrad/Kokoro-82M-v1.1-zh")
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--speed", type=float, default=1.0)
    args = parser.parse_args()

    import subprocess

    output = (ROOT / args.output).resolve() if not Path(args.output).is_absolute() else Path(args.output)
    ledger = (ROOT / args.ledger).resolve() if not Path(args.ledger).is_absolute() else Path(args.ledger)
    python_bin = (ROOT / args.python).resolve() if not Path(args.python).is_absolute() else Path(args.python)
    worker = (ROOT / args.worker).resolve() if not Path(args.worker).is_absolute() else Path(args.worker)
    request_file = output.with_suffix(".request.json")
    result_file = output.with_suffix(".result.json")
    output.parent.mkdir(parents=True, exist_ok=True)

    request = {
        "text": args.text,
        "voice": args.voice,
        "speed": args.speed,
        "repo_id": args.repo_id,
        "device": args.device,
        "output_path": str(output),
        "sample_rate": 24000,
    }
    request_file.write_text(json.dumps(request, ensure_ascii=False, indent=2), encoding="utf-8")
    completed = subprocess.run(
        [str(python_bin), str(worker), "--request", str(request_file), "--result", str(result_file)],
        capture_output=True,
        check=False,
    )
    result = json.loads(result_file.read_text(encoding="utf-8")) if result_file.exists() else {}
    if completed.returncode != 0 or not result.get("ok"):
        detail = result.get("error") or completed.stderr.decode("utf-8", errors="replace")[-3000:]
        print(f"ERROR: {detail}", file=sys.stderr)
        return 1

    ledger_payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "commercial_status": "BLOCKED",
        "purpose": "local_prototype_listening_only",
        "text": args.text,
        "voice": args.voice,
        "repo_id": args.repo_id,
        "device": args.device,
        "speed": args.speed,
        "output_wav": str(output),
        "output_sha256": sha256_file(output),
        "worker_result": result,
        "note": "Do not ship as commercial master until docs/COMMERCIAL_LOCAL_TTS_OPTION.md is CLEARED.",
    }
    ledger.write_text(json.dumps(ledger_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(ledger_payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Submit a ComfyUI API workflow and wait for a terminal result.

This helper intentionally uses only the Python standard library so it can run
from any of the project's virtual environments.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path


def request_json(url: str, *, payload: dict | None = None, timeout: float = 30.0) -> dict:
    data = None
    headers: dict[str, str] = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("workflow", type=Path)
    parser.add_argument("--server", default="http://127.0.0.1:8188")
    parser.add_argument("--timeout-minutes", type=float, default=90.0)
    parser.add_argument("--poll-seconds", type=float, default=5.0)
    parser.add_argument("--result", type=Path)
    args = parser.parse_args()

    workflow = json.loads(args.workflow.read_text(encoding="utf-8"))
    client_id = str(uuid.uuid4())
    try:
        queued = request_json(
            f"{args.server.rstrip('/')}/prompt",
            payload={"prompt": workflow, "client_id": client_id},
        )
    except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
        print(f"ComfyUI submission failed: {exc}", file=sys.stderr)
        return 2

    prompt_id = queued.get("prompt_id")
    if not prompt_id:
        print(json.dumps(queued, ensure_ascii=False, indent=2), file=sys.stderr)
        return 3

    print(f"queued prompt_id={prompt_id}", flush=True)
    deadline = time.monotonic() + args.timeout_minutes * 60.0
    last_queue = None

    while time.monotonic() < deadline:
        try:
            history = request_json(
                f"{args.server.rstrip('/')}/history/{prompt_id}", timeout=30.0
            )
        except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
            print(f"history poll warning: {exc}", flush=True)
            time.sleep(args.poll_seconds)
            continue

        record = history.get(prompt_id)
        if record is not None:
            status = record.get("status", {})
            completed = bool(status.get("completed"))
            status_text = status.get("status_str", "unknown")
            if completed or status_text == "error":
                rendered = json.dumps(record, ensure_ascii=False, indent=2)
                if args.result:
                    args.result.parent.mkdir(parents=True, exist_ok=True)
                    args.result.write_text(rendered + "\n", encoding="utf-8")
                print(rendered)
                return 0 if completed and status_text != "error" else 4

        try:
            queue = request_json(f"{args.server.rstrip('/')}/queue", timeout=15.0)
            running = len(queue.get("queue_running", []))
            pending = len(queue.get("queue_pending", []))
            snapshot = (running, pending)
            if snapshot != last_queue:
                print(f"queue running={running} pending={pending}", flush=True)
                last_queue = snapshot
        except (OSError, urllib.error.URLError, json.JSONDecodeError):
            pass
        time.sleep(args.poll_seconds)

    print(f"Timed out waiting for {prompt_id}", file=sys.stderr)
    return 5


if __name__ == "__main__":
    raise SystemExit(main())

"""Gateway contract/restart/network-boundary tests; never connect to a model."""
import base64
import io
import json
import threading
import time
import uuid
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from scripts.local_free_gateway import ROOT, create_app, local_url, output_metadata, validate_video_asset


def png_bytes(size=(64, 96)):
    stream = io.BytesIO()
    Image.new("RGB", size, (30, 60, 90)).save(stream, format="PNG")
    return stream.getvalue()


def video_body(**extra):
    return {"prompt": "one slow step", "image": base64.b64encode(png_bytes()).decode(), "seed": 0, **extra}


class ComfyStub:
    def __init__(self):
        self.calls = []
        self.submissions = []
        self.complete = False
        self.in_queue = True
        self.fail_submit = False
        self.submit_400 = False
        self.bad_output = None
        self.redirect_view = False
        self.poll_disconnect = False
        self.last_upload = None

    def __call__(self, request):
        assert request.url.host in {"127.0.0.1", "::1"}
        self.calls.append((request.method, str(request.url)))
        path = request.url.path
        if path == "/prompt":
            self.submissions.append(json.loads(request.content))
            if self.fail_submit:
                raise httpx.ReadTimeout("response lost after acceptance", request=request)
            if self.submit_400:
                return httpx.Response(400, json={"error": "missing model"})
            return httpx.Response(200, json={"prompt_id": f"prompt-{len(self.submissions)}"})
        if path == "/upload/image":
            self.last_upload = request.content
            return httpx.Response(200, json={"name": "uploaded.png", "subfolder": "local_free", "type": "input"})
        if path.startswith("/history/"):
            if self.poll_disconnect:
                raise httpx.ConnectError("restarting", request=request)
            if not self.complete:
                return httpx.Response(200, json={})
            image = "CheckpointLoaderSimple" == self.submissions[-1]["prompt"]["1"]["class_type"]
            item = self.bad_output or {"filename": "image.png" if image else "video.mp4", "subfolder": "local_free", "type": "output", "fullpath": "C:/DO_NOT_READ/secret"}
            node = {"images": [item]} if image else {"gifs": [item]}
            return httpx.Response(200, json={path.rsplit("/", 1)[-1]: {"status": {"completed": True, "status_str": "success"}, "outputs": {"12" if image else "13": node}}})
        if path == "/queue":
            return httpx.Response(200, json={"queue_running": [[0, f"prompt-{len(self.submissions)}"]] if self.in_queue else [], "queue_pending": []})
        if path == "/view":
            if self.redirect_view:
                return httpx.Response(302, headers={"location": "https://paid.example/model"})
            if request.url.params["filename"].endswith(".png"):
                inputs = self.submissions[-1]["prompt"]["2"]["inputs"]
                return httpx.Response(200, content=png_bytes((inputs["width"], inputs["height"])))
            return httpx.Response(200, content=b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 64)
        if path == "/api/chat":
            self.text_payload = json.loads(request.content)
            return httpx.Response(200, json={"message": {"content": "本地剧本"}})
        raise AssertionError(f"Unexpected network request: {request.method} {request.url}")


def setup_gateway(tmp_path, stub=None):
    stub = stub or ComfyStub()
    app = create_app(work_dir=tmp_path, transport=httpx.MockTransport(stub), start_worker=False,
                     memory_probe=lambda: {"supported": True, "available_commit_gib": 32})
    return TestClient(app), app.state.gateway, stub


@pytest.mark.parametrize("url", [
    "https://127.0.0.1:8488", "http://localhost:8488", "http://paid.example:8488",
    "http://127.0.0.1.evil.test:8488", "http://192.168.1.2:8488", "http://0.0.0.0:8488",
    "http://user:pass@127.0.0.1:8488", "http://127.0.0.1:8488/path", "http://127.0.0.1:8488?x=1",
    "http://127.0.0.1:8488#x", "file:///tmp/comfy", "http://127.0.0.1",
])
def test_external_and_ambiguous_urls_rejected(url):
    with pytest.raises(ValueError):
        local_url(url)


def test_explicit_ipv4_ipv6_loopback_allowed():
    assert local_url("http://127.0.0.1:8488/") == "http://127.0.0.1:8488"
    assert local_url("http://[::1]:8488") == "http://[::1]:8488"


@pytest.mark.parametrize("value", ["https://paid.example/image.png", "http://127.0.0.1:8488/view", "file:///C:/secret", "C:/secret", "not base64", "data:text/plain;base64,AAAA"])
def test_video_input_rejects_urls_and_bad_base64_before_network(tmp_path, value):
    client, gateway, stub = setup_gateway(tmp_path)
    response = client.post("/jobs/video", json=video_body(image=value))
    assert response.status_code == 400
    assert gateway.jobs == {}
    assert not stub.calls


@pytest.mark.parametrize("extra", [{"duration": 5}, {"aspect_ratio": "16:9"}, {"seed": -1}, {"seed": True}, {"paid_provider": "x"}])
def test_request_limits(tmp_path, extra):
    client, _, stub = setup_gateway(tmp_path)
    assert client.post("/jobs/video", json=video_body(**extra)).status_code == 422
    assert not stub.calls


def test_blank_prompt_small_and_nonimage_inputs_rejected(tmp_path):
    client, _, stub = setup_gateway(tmp_path)
    assert client.post("/jobs/image", json={"prompt": "   "}).status_code == 400
    assert client.post("/jobs/video", json=video_body(image=base64.b64encode(b"hello").decode())).status_code == 400
    assert client.post("/jobs/video", json=video_body(image=base64.b64encode(png_bytes((1, 1))).decode())).status_code == 400
    assert not stub.calls


@pytest.mark.parametrize("ratio,size", [("9:16", (720, 1280)), ("16:9", (1280, 720)), ("1:1", (1024, 1024))])
def test_image_contract_seed_zero_dimensions_and_asset(tmp_path, ratio, size):
    client, gateway, stub = setup_gateway(tmp_path)
    response = client.post("/jobs/image", json={"prompt": "portrait", "seed": 0, "aspect_ratio": ratio, "negative_prompt": ""})
    assert response.status_code == 202
    job = response.json()
    assert job["seed"] == 0 and job["status"] == "queued"
    assert (job["native_width"], job["native_height"]) == size
    gateway.process_once()
    workflow = stub.submissions[0]["prompt"]
    assert workflow["10"]["inputs"]["seed"] == 0
    assert workflow["10"]["inputs"]["steps"] == 40
    assert workflow["4"]["inputs"]["text"] == ""
    stub.complete = True
    gateway.process_once()
    done = client.get(f"/jobs/{job['id']}").json()
    assert done["status"] == "succeeded"
    asset = client.get(done["asset_url"])
    assert asset.status_code == 200 and asset.headers["content-type"] == "image/png"
    assert Image.open(io.BytesIO(asset.content)).size == size
    stored = (tmp_path / f"{job['id']}.json").read_text()
    assert "base64" not in stored and "C:/DO_NOT_READ" not in stored
    assert not list(tmp_path.glob("*.tmp"))


@pytest.mark.parametrize("duration,frames", [(2, 17), (3, 25), (4, 33)])
def test_video_upload_workflow_and_native_output(tmp_path, duration, frames):
    client, gateway, stub = setup_gateway(tmp_path)
    # This test isolates the HTTP protocol; actual media validation is tested below.
    gateway.video_validator = lambda path, job: None
    response = client.post("/jobs/video", json=video_body(duration=duration))
    job = response.json()
    assert (job["native_width"], job["native_height"], job["fps"], job["frames"]) == (480, 832, 8, frames)
    gateway.process_once()
    workflow = stub.submissions[0]["prompt"]
    assert stub.last_upload and b"image/png" in stub.last_upload
    assert workflow["3"]["inputs"]["image"] == "local_free/uploaded.png"
    assert workflow["11"]["inputs"]["seed"] == 0
    assert workflow["7"]["inputs"]["num_frames"] == frames
    assert workflow["11"]["inputs"]["steps"] == 20
    stub.complete = True
    gateway.process_once()
    done = client.get(f"/jobs/{job['id']}").json()
    assert done["status"] == "succeeded"
    assert client.get(done["asset_url"]).headers["content-type"] == "video/mp4"


def test_queue_serial_across_multiple_requests(tmp_path):
    client, gateway, stub = setup_gateway(tmp_path)
    first = client.post("/jobs/image", json={"prompt": "one"}).json()
    second = client.post("/jobs/image", json={"prompt": "two"}).json()
    gateway.process_once()
    gateway.process_once()
    assert len(stub.submissions) == 1
    assert client.get(f"/jobs/{second['id']}").json()["status"] == "queued"
    stub.complete = True
    gateway.process_once()
    assert client.get(f"/jobs/{first['id']}").json()["status"] == "succeeded"
    gateway.process_once()
    assert len(stub.submissions) == 2


def test_restart_recovers_acknowledged_prompt_without_resubmit(tmp_path):
    client, gateway, stub = setup_gateway(tmp_path)
    job = client.post("/jobs/image", json={"prompt": "one"}).json()
    gateway.process_once()
    client2, resumed, _ = setup_gateway(tmp_path, stub)
    stub.complete = True
    resumed.process_once()
    assert len(stub.submissions) == 1
    assert client2.get(f"/jobs/{job['id']}").json()["status"] == "succeeded"


def test_unknown_submission_pauses_queue_and_survives_restart(tmp_path):
    client, gateway, stub = setup_gateway(tmp_path)
    first = client.post("/jobs/image", json={"prompt": "one"}).json()
    second = client.post("/jobs/image", json={"prompt": "two"}).json()
    stub.fail_submit = True
    gateway.process_once()
    assert client.get(f"/jobs/{first['id']}").json()["status"] == "needs_attention"
    _, resumed, _ = setup_gateway(tmp_path, stub)
    resumed.process_once()
    assert len(stub.submissions) == 1
    assert resumed.jobs[second["id"]]["status"] == "queued"


def test_crash_between_submit_and_ack_never_resubmits(tmp_path):
    client, gateway, stub = setup_gateway(tmp_path)
    job = client.post("/jobs/image", json={"prompt": "one"}).json()
    gateway.update(job["id"], status="submitting")
    _, resumed, _ = setup_gateway(tmp_path, stub)
    resumed.process_once()
    assert resumed.jobs[job["id"]]["status"] == "needs_attention"
    assert not stub.calls


def test_transient_poll_failure_keeps_prompt_and_never_resubmits(tmp_path):
    client, gateway, stub = setup_gateway(tmp_path)
    job = client.post("/jobs/image", json={"prompt": "one"}).json()
    gateway.process_once()
    stub.poll_disconnect = True
    gateway.process_once()
    assert gateway.jobs[job["id"]]["status"] == "running"
    stub.poll_disconnect, stub.complete = False, True
    gateway.process_once()
    assert gateway.jobs[job["id"]]["status"] == "succeeded"
    assert len(stub.submissions) == 1


def test_missing_prompt_requires_attention(tmp_path):
    client, gateway, stub = setup_gateway(tmp_path)
    job = client.post("/jobs/image", json={"prompt": "one"}).json()
    gateway.process_once()
    stub.in_queue = False
    gateway.process_once()
    assert gateway.jobs[job["id"]]["status"] == "needs_attention"
    assert len(stub.submissions) == 1


def test_explicit_rejection_is_failed_not_unknown(tmp_path):
    client, gateway, stub = setup_gateway(tmp_path)
    job = client.post("/jobs/image", json={"prompt": "one"}).json()
    stub.submit_400 = True
    gateway.process_once()
    assert gateway.jobs[job["id"]]["status"] == "failed"


@pytest.mark.parametrize("item", [
    {"filename": "../secret.png", "subfolder": "", "type": "output"},
    {"filename": "secret.png", "subfolder": "../secret", "type": "output"},
    {"filename": "secret.png", "subfolder": "C:/secret", "type": "output"},
    {"filename": "secret.png", "subfolder": "a\\b", "type": "output"},
    {"filename": "secret.png", "subfolder": "/secret", "type": "output"},
    {"filename": "secret.png", "subfolder": "", "type": "input"},
])
def test_metadata_traversal_blocked_before_view(tmp_path, item):
    client, gateway, stub = setup_gateway(tmp_path)
    job = client.post("/jobs/image", json={"prompt": "one"}).json()
    gateway.process_once()
    stub.complete, stub.bad_output = True, item
    gateway.process_once()
    assert gateway.jobs[job["id"]]["status"] == "failed"
    assert not any("/view" in url for _, url in stub.calls)


def test_redirect_not_followed(tmp_path):
    client, gateway, stub = setup_gateway(tmp_path)
    job = client.post("/jobs/image", json={"prompt": "one"}).json()
    gateway.process_once()
    stub.complete, stub.redirect_view = True, True
    gateway.process_once()
    assert len(stub.submissions) == 1
    assert gateway.jobs[job["id"]]["status"] != "succeeded"
    assert all("paid.example" not in url for _, url in stub.calls)


def test_uuid_and_asset_path_safety(tmp_path):
    client, gateway, _ = setup_gateway(tmp_path)
    assert client.get("/jobs/not-a-uuid").status_code == 400
    assert client.get(f"/jobs/{uuid.uuid4()}").status_code == 404
    job = client.post("/jobs/image", json={"prompt": "one"}).json()
    assert client.get(f"/jobs/{job['id']}/asset").status_code == 409
    gateway.update(job["id"], status="succeeded", asset_name="../private.png")
    assert client.get(f"/jobs/{job['id']}/asset").status_code == 404


def test_text_is_cpu_ollama_no_stream_no_fallback(tmp_path):
    client, _, stub = setup_gateway(tmp_path)
    response = client.post("/text", json={"prompt": "写剧本", "system": "严谨"})
    assert response.status_code == 200 and response.json()["text"] == "本地剧本"
    payload = stub.text_payload
    assert payload["model"] == "qwen2.5:7b"
    assert payload["stream"] is False and payload["keep_alive"] == 0
    assert payload["options"]["num_gpu"] == 0
    assert payload["options"]["num_ctx"] == 4096
    assert payload["options"]["num_predict"] == 2048
    assert len(stub.calls) == 1


def object_info():
    nodes = {}
    for path in ("realvisxl_v5_vertical_hero_portrait_single_api.json", "toonflow_local_wan_i2v_template.json"):
        workflow = json.loads((ROOT / "workflows" / path).read_text())
        for value in workflow.values():
            fields = {}
            for key in ("ckpt_name", "model", "model_name"):
                configured = value["inputs"].get(key)
                if isinstance(configured, str):
                    fields[key] = [[configured]]
            nodes[value["class_type"]] = {"input": {"required": fields}}
    return nodes


def test_health_checks_real_services_nodes_and_models(tmp_path):
    nodes = object_info()
    def handler(request):
        if request.url.path == "/system_stats":
            return httpx.Response(200, json={"system": {}})
        if request.url.path == "/object_info":
            return httpx.Response(200, json=nodes)
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={"models": [{"name": "qwen2.5:7b"}]})
        raise AssertionError(request.url)
    client, _, _ = setup_gateway(tmp_path, handler)
    assert client.get("/health").json()["ready"] is True
    nodes["CheckpointLoaderSimple"]["input"]["required"]["ckpt_name"] = [["other.safetensors"]]
    health = client.get("/health").json()
    assert health["ready"] is False and health["comfy"]["image_ready"] is False
    assert health["comfy"]["video_ready"] is True


def test_unreachable_health_does_not_claim_ready(tmp_path):
    def handler(request):
        raise httpx.ConnectError("offline", request=request)
    client, _, _ = setup_gateway(tmp_path, handler)
    health = client.get("/health").json()
    assert health["ready"] is False
    assert health["comfy"]["reachable"] is False and health["ollama"]["reachable"] is False


def test_clients_disable_environment_proxies_and_redirects(tmp_path, monkeypatch):
    monkeypatch.setenv("HTTP_PROXY", "http://paid.example:8080")
    _, gateway, _ = setup_gateway(tmp_path)
    with gateway.client() as client:
        assert client._trust_env is False
        assert client.follow_redirects is False


def test_duplicate_start_has_only_one_worker(tmp_path):
    _, gateway, _ = setup_gateway(tmp_path)
    gateway.start()
    first = gateway.thread
    gateway.start()
    assert gateway.thread is first and first.is_alive()
    gateway.close()
    assert not first.is_alive()


def test_corrupt_persisted_state_is_visible_and_blocks_retries(tmp_path):
    job_id = str(uuid.uuid4())
    (tmp_path / f"{job_id}.json").write_text("{broken")
    client, gateway, stub = setup_gateway(tmp_path)
    assert client.get(f"/jobs/{job_id}").json()["status"] == "needs_attention"
    client.post("/jobs/image", json={"prompt": "one"})
    gateway.process_once()
    assert not stub.calls


def test_low_memory_rejects_without_job_or_gpu_submission(tmp_path):
    client, gateway, stub = setup_gateway(tmp_path)
    gateway.memory_probe = lambda: {"supported": True, "available_commit_gib": 6.71}
    assert client.post("/jobs/image", json={"prompt": "one"}).status_code == 503
    response = client.post("/jobs/video", json=video_body())
    assert response.status_code == 503 and "16 GiB" in response.json()["detail"]
    assert not gateway.jobs and not stub.calls


def test_text_memory_gate_prevents_model_load_and_releases_lock(tmp_path):
    client, gateway, stub = setup_gateway(tmp_path)
    gateway.memory_probe = lambda: {"supported": True, "available_commit_gib": 4.01}
    response = client.post("/text", json={"prompt": "写剧本"})
    assert response.status_code == 503 and "6 GiB" in response.json()["detail"]
    assert not stub.calls and not gateway.text_lock.locked()
    assert gateway.memory()["text_ready"] is False


def test_concurrent_text_request_is_rejected_without_parallel_load(tmp_path):
    client, gateway, stub = setup_gateway(tmp_path)
    gateway.text_lock.acquire()
    try:
        response = client.post("/text", json={"prompt": "写剧本"})
        assert response.status_code == 409 and not stub.calls
    finally:
        gateway.text_lock.release()
    assert client.post("/text", json={"prompt": "写剧本"}).status_code == 200


def test_failed_text_request_releases_cpu_lock(tmp_path):
    def handler(request):
        raise httpx.ConnectError("offline", request=request)
    client, gateway, _ = setup_gateway(tmp_path, handler)
    assert client.post("/text", json={"prompt": "写剧本"}).status_code == 503
    assert not gateway.text_lock.locked()


def test_worker_rechecks_memory_before_gpu_submission(tmp_path):
    client, gateway, stub = setup_gateway(tmp_path)
    job = client.post("/jobs/image", json={"prompt": "one"}).json()
    gateway.memory_probe = lambda: {"supported": True, "available_commit_gib": 2}
    gateway.process_once()
    assert gateway.jobs[job["id"]]["status"] == "queued"
    assert not stub.calls
    gateway.memory_probe = lambda: {"supported": True, "available_commit_gib": 20}
    gateway.process_once()
    assert len(stub.submissions) == 1


@pytest.mark.parametrize("content", ["[]", '"text"', '{"id":"wrong","kind":"image"}', '{"kind":"unsupported"}'])
def test_invalid_json_schema_blocks_without_crashing(tmp_path, content):
    job_id = str(uuid.uuid4())
    (tmp_path / f"{job_id}.json").write_text(content)
    client, gateway, stub = setup_gateway(tmp_path)
    assert client.get(f"/jobs/{job_id}").json()["status"] == "needs_attention"
    gateway.process_once()
    assert not stub.calls


def test_cross_instance_worker_lock(tmp_path):
    _, first, _ = setup_gateway(tmp_path)
    _, second, _ = setup_gateway(tmp_path)
    try:
        first.start()
        with pytest.raises(RuntimeError, match="already owns"):
            second.start()
    finally:
        first.close()
        second.close()


def test_second_factory_does_not_rewrite_active_submission(tmp_path):
    client, gateway, _ = setup_gateway(tmp_path)
    job = client.post("/jobs/image", json={"prompt": "one"}).json()
    gateway.update(job["id"], status="submitting")
    before = (tmp_path / f"{job['id']}.json").read_bytes()
    _, second, _ = setup_gateway(tmp_path)
    assert second.jobs[job["id"]]["status"] == "needs_attention"
    assert (tmp_path / f"{job['id']}.json").read_bytes() == before


def test_failed_create_persistence_does_not_queue_gpu_work(tmp_path, monkeypatch):
    client, gateway, stub = setup_gateway(tmp_path)
    def fail(_):
        raise OSError("disk full")
    monkeypatch.setattr(gateway, "_save", fail)
    with pytest.raises(OSError):
        client.post("/jobs/image", json={"prompt": "one"})
    assert not gateway.jobs
    gateway.process_once()
    assert not stub.calls


def test_video_validation_checks_frames_and_full_decode(tmp_path, monkeypatch):
    import scripts.local_free_gateway as module
    calls = []
    monkeypatch.setattr(module.shutil, "which", lambda name: name)
    def run(command, **kwargs):
        assert kwargs["check"] and kwargs["timeout"] == 60
        calls.append(command)
        class Result:
            stdout = json.dumps({"streams": [{"width": 480, "height": 832, "avg_frame_rate": "8/1", "nb_read_frames": "17"}]})
        return Result()
    monkeypatch.setattr(module.subprocess, "run", run)
    validate_video_asset(tmp_path / "video.mp4", {"native_width": 480, "native_height": 832, "fps": 8, "frames": 17})
    assert len(calls) == 2 and "-count_frames" in calls[0] and "-xerror" in calls[1]
    with pytest.raises(ValueError, match="frame rate/count"):
        validate_video_asset(tmp_path / "video.mp4", {"native_width": 480, "native_height": 832, "fps": 8, "frames": 33})


def test_video_validation_requires_tools(tmp_path, monkeypatch):
    import scripts.local_free_gateway as module
    monkeypatch.setattr(module.shutil, "which", lambda name: None)
    monkeypatch.setattr(module.Path, "is_file", lambda path: False)
    with pytest.raises(ValueError, match="required to validate"):
        validate_video_asset(tmp_path / "video.mp4", {"native_width": 480, "native_height": 832, "fps": 8, "frames": 17})


def test_truncated_mp4_cannot_become_success(tmp_path):
    client, gateway, stub = setup_gateway(tmp_path)
    job = client.post("/jobs/video", json=video_body()).json()
    gateway.process_once()
    stub.complete = True
    gateway.process_once()
    assert gateway.jobs[job["id"]]["status"] == "failed"
    assert "validation" in gateway.jobs[job["id"]]["error"] or "required" in gateway.jobs[job["id"]]["error"]
    assert client.get(f"/jobs/{job['id']}/asset").status_code == 409

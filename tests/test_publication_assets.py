"""Small, offline checks for the public documentation assets."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]


def test_real_screenshot_manifest_matches_files_and_page():
    folder = ROOT / "docs" / "screenshots"
    manifest = json.loads((folder / "capture-manifest.json").read_text(encoding="utf-8"))
    assert manifest["jobs"] == 0
    assert manifest["cloud_fallback"] is False
    # Git may normalize source newlines; compare the captured LF representation.
    html = (ROOT / "app" / "static" / "local_free.html").read_bytes().replace(b"\r\n", b"\n")
    assert hashlib.sha256(html).hexdigest() == manifest["html_sha256"]
    assert {item["file"] for item in manifest["files"]} == {
        "workbench-overview.png", "generation-panels.png", "service-status.png"
    }
    for item in manifest["files"]:
        image_path = folder / item["file"]
        assert hashlib.sha256(image_path.read_bytes()).hexdigest() == item["sha256"]
        with Image.open(image_path) as image:
            assert image.format == "PNG"
            assert image.width >= 600 and image.height >= 400
            assert image.size == (item["width"], item["height"])
            if item["file"] == "generation-panels.png":
                expected = manifest["generation_panels_expected_size"]
                assert abs(image.width - expected["width"]) <= 1
                assert abs(image.height - expected["height"]) <= 1
            image.verify()


def test_project_and_third_party_license_texts_are_separate():
    license_text = (ROOT / "LICENSE").read_text(encoding="utf-8")
    assert "Version 2.0, January 2004" in license_text
    assert "3. Grant of Patent License." in license_text
    assert "END OF TERMS AND CONDITIONS" in license_text
    assert "Supplementary Agreement" not in license_text
    legacy = (ROOT / "docs" / "licenses" / "Toonflow-legacy-e03cf590-LICENSE.txt").read_text(encoding="utf-8")
    assert "Supplementary Agreement" in legacy
    current = (ROOT / "docs" / "licenses" / "Toonflow-72a895c2-MIT.txt").read_text(encoding="utf-8")
    assert "MIT License" in current and "HBAI-Ltd" in current


def test_readme_includes_public_documentation_entrypoints():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    for target in (
        "docs/SCREENSHOTS.md", "docs/ALGORITHMS_AND_MODELS.md",
        "docs/THIRD_PARTY_NOTICES.md", "docs/LEGACY_TOONFLOW.md", "LICENSE", "NOTICE",
    ):
        assert f"]({target})" in readme
        assert (ROOT / target).is_file()


def test_walkthrough_gif_is_complete_and_animated():
    folder = ROOT / "docs" / "screenshots"
    manifest = json.loads((folder / "walkthrough-manifest.json").read_text(encoding="utf-8"))
    asset = manifest["asset"]
    gif_path = folder / "generation-walkthrough.gif"
    raw = gif_path.read_bytes()
    assert asset["file"] == gif_path.name
    assert len(raw) == asset["bytes"] < 8 * 1024**2
    assert hashlib.sha256(raw).hexdigest() == asset["sha256"]
    with Image.open(gif_path) as gif:
        assert gif.format == "GIF" and gif.is_animated
        assert gif.info["loop"] == 0
        assert gif.size == (asset["width"], asset["height"]) == (1280, 900)
        assert gif.n_frames == asset["frames"] >= 20
        duration_ms = 0
        for index in range(gif.n_frames):
            gif.seek(index)
            gif.load()
            assert gif.info["duration"] > 0
            duration_ms += gif.info["duration"]
        assert abs(duration_ms / 1000 - asset["duration_seconds"]) < 0.1


def test_walkthrough_provenance_and_readme_embed():
    manifest = json.loads((ROOT / "docs" / "screenshots" / "walkthrough-manifest.json").read_text(encoding="utf-8"))
    assert manifest["mocked_api_responses"] is False
    assert manifest["edited_timing"] is True
    assert manifest["image_requests"] == 1 and manifest["image_response_status"] == 503
    assert "可用提交内存不足" in manifest["image_response_detail"]
    assert manifest["video_requests"] == manifest["text_requests"] == manifest["final_jobs"] == 0
    assert len(manifest["steps"]) == 10
    html = (ROOT / "app" / "static" / "local_free.html").read_bytes().replace(b"\r\n", b"\n")
    assert hashlib.sha256(html).hexdigest() == manifest["html_sha256"]
    assert manifest["upload_demo_source"] == "docs/screenshots/workbench-overview.png"
    assert hashlib.sha256((ROOT / manifest["upload_demo_source"]).read_bytes()).hexdigest() == manifest["upload_demo_sha256"]
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "](docs/screenshots/generation-walkthrough.gif)" in readme
    assert "](docs/GENERATION_WALKTHROUGH.md)" in readme

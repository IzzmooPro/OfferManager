"""Aşama 5: güvenli PNG capture ve before/after/diff raporu."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]


def _run(*args: str):
    env = dict(os.environ)
    env["QT_QPA_PLATFORM"] = "offscreen"
    return subprocess.run(
        [sys.executable, "-m", "ui_preview", *args],
        cwd=ROOT, env=env, text=True, capture_output=True, timeout=90,
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def test_single_scenario_capture_writes_png_manifest_and_contact_sheet(tmp_path):
    output = tmp_path / "capture"
    proc = _run(
        "--capture", "component.plus_button.normal",
        "--output", str(output), "--label", "before", "--json",
    )
    assert proc.returncode == 0, proc.stderr
    result = json.loads(proc.stdout)
    assert result["ok"] is True
    assert result["captured"] == 1
    assert result["external_effects"] == []
    assert result["real_credential_accesses"] == 0

    manifest_path = output / "capture_manifest.json"
    index_path = output / "index.html"
    assert manifest_path.is_file()
    assert index_path.is_file()
    manifest = json.loads(manifest_path.read_text("utf-8"))
    assert manifest["schema_version"] == 1
    assert manifest["kind"] == "ui_preview_capture"
    assert manifest["synthetic_only"] is True
    assert manifest["label"] == "before"
    assert len(manifest["source_fingerprint"]) == 64
    assert manifest["qt_version"]
    assert manifest["pyside_version"]
    assert manifest["capture_count"] == 1
    item = manifest["captures"][0]
    assert item["scenario_id"] == "component.plus_button.normal"
    assert item["widget_class"] == "ui.widgets._plus_button.PlusButton"
    assert item["theme"] == "light"
    assert item["viewport"] == "1300x800"
    assert item["dpi"] == 100
    assert item["width"] > 0 and item["height"] > 0
    png = output / item["file"]
    assert png.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
    assert item["sha256"] == _sha256(png)
    with Image.open(png) as image:
        assert image.size == (item["width"], item["height"])

    serialized = manifest_path.read_text("utf-8")
    assert str(tmp_path) not in serialized
    assert "Universe" not in serialized
    assert "credential" not in serialized.lower()
    html = index_path.read_text("utf-8")
    assert item["file"] in html
    assert "component.plus_button.normal" in html


def test_capture_refuses_nonempty_output_to_prevent_silent_overwrite(tmp_path):
    output = tmp_path / "capture"
    output.mkdir()
    (output / "keep.txt").write_text("user-owned", encoding="utf-8")
    proc = _run(
        "--capture", "component.plus_button.normal",
        "--output", str(output), "--json",
    )
    assert proc.returncode != 0
    assert (output / "keep.txt").read_text("utf-8") == "user-owned"
    assert not (output / "capture_manifest.json").exists()


def test_capture_failure_publishes_no_partial_output(tmp_path):
    output = tmp_path / "capture"
    proc = _run(
        "--capture", "component.unknown.missing",
        "--output", str(output), "--json",
    )
    assert proc.returncode != 0
    assert not output.exists()


def test_capture_rejects_path_or_html_in_manifest_label(tmp_path):
    for index, label in enumerate((r"C:\Users\Example", "<script>")):
        output = tmp_path / f"capture-{index}"
        proc = _run(
            "--capture", "component.plus_button.normal",
            "--output", str(output), "--label", label, "--json",
        )
        assert proc.returncode != 0
        assert not output.exists()


def test_identical_inputs_produce_identical_png_bytes(tmp_path):
    hashes = []
    for index in range(2):
        output = tmp_path / f"capture-{index}"
        proc = _run(
            "--capture", "component.plus_button.normal",
            "--output", str(output), "--json",
        )
        assert proc.returncode == 0, proc.stderr
        manifest = json.loads((output / "capture_manifest.json").read_text("utf-8"))
        hashes.append(manifest["captures"][0]["sha256"])
    assert hashes[0] == hashes[1]


def test_surface_capture_set_creates_43_item_theme_contact_sheet(tmp_path):
    output = tmp_path / "surface-capture"
    proc = _run(
        "--capture-surfaces", "--output", str(output),
        "--theme", "dark", "--viewport", "1100x700",
        "--label", "dark surfaces", "--json",
    )
    assert proc.returncode == 0, proc.stderr
    result = json.loads(proc.stdout)
    assert result["captured"] == 43
    manifest = json.loads((output / "capture_manifest.json").read_text("utf-8"))
    assert manifest["capture_count"] == 43
    assert len({item["surface_id"] for item in manifest["captures"]}) == 43
    assert {item["theme"] for item in manifest["captures"]} == {"dark"}
    assert {item["viewport"] for item in manifest["captures"]} == {"1100x700"}
    html = (output / "index.html").read_text("utf-8")
    assert html.count('<article class="card">') == 43


def test_compare_generates_before_after_diff_and_html_without_baseline_update(tmp_path):
    before_dir = tmp_path / "before"
    after_dir = tmp_path / "after"
    for label, output in (("before", before_dir), ("after", after_dir)):
        proc = _run(
            "--capture", "component.plus_button.normal",
            "--output", str(output), "--label", label, "--json",
        )
        assert proc.returncode == 0, proc.stderr

    after_manifest_path = after_dir / "capture_manifest.json"
    after_manifest = json.loads(after_manifest_path.read_text("utf-8"))
    item = after_manifest["captures"][0]
    after_png = after_dir / item["file"]
    with Image.open(after_png).convert("RGBA") as image:
        image.putpixel((0, 0), (255, 0, 255, 255))
        image.save(after_png)
    item["sha256"] = _sha256(after_png)
    after_manifest_path.write_text(
        json.dumps(after_manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    report_dir = tmp_path / "report"
    proc = _run(
        "--compare", str(before_dir / "capture_manifest.json"),
        str(after_manifest_path), "--output", str(report_dir), "--json",
    )
    assert proc.returncode == 0, proc.stderr
    result = json.loads(proc.stdout)
    assert result["ok"] is True
    assert result["compared"] == 1
    assert result["changed"] == 1

    report_manifest = json.loads(
        (report_dir / "comparison_manifest.json").read_text("utf-8")
    )
    assert report_manifest["synthetic_only"] is True
    comparison = report_manifest["comparisons"][0]
    assert comparison["changed_pixels"] >= 1
    for key in ("before_file", "after_file", "diff_file", "side_by_side_file"):
        assert (report_dir / comparison[key]).is_file()
    assert (report_dir / "index.html").is_file()
    assert not any("baseline" in path.name.lower() for path in report_dir.rglob("*"))


def test_compare_rejects_incompatible_capture_metadata(tmp_path):
    before_dir = tmp_path / "before"
    after_dir = tmp_path / "after"
    first = _run(
        "--capture", "component.plus_button.normal", "--theme", "light",
        "--output", str(before_dir), "--json",
    )
    second = _run(
        "--capture", "component.plus_button.normal", "--theme", "dark",
        "--output", str(after_dir), "--json",
    )
    assert first.returncode == second.returncode == 0
    report_dir = tmp_path / "report"
    proc = _run(
        "--compare", str(before_dir / "capture_manifest.json"),
        str(after_dir / "capture_manifest.json"),
        "--output", str(report_dir), "--json",
    )
    assert proc.returncode != 0
    assert not (report_dir / "comparison_manifest.json").exists()


def test_capture_cli_exposes_explicit_acceptance_but_no_update_switch():
    proc = _run("--help")
    assert proc.returncode == 0
    help_text = proc.stdout.lower()
    assert "baseline-plan" in help_text
    assert "baseline-accept" in help_text
    assert "baseline-update" not in help_text

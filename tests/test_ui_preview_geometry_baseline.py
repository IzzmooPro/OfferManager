"""Aşama 6: geometri denetimi ve açık onaylı değiştirilemez baseline."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _run(*args: str):
    env = dict(os.environ)
    env["QT_QPA_PLATFORM"] = "offscreen"
    return subprocess.run(
        [sys.executable, "-m", "ui_preview", *args],
        cwd=ROOT, env=env, text=True, capture_output=True, timeout=120,
    )


def _capture(tmp_path: Path) -> Path:
    output = tmp_path / "capture"
    proc = _run(
        "--capture", "component.plus_button.normal",
        "--output", str(output), "--label", "candidate", "--json",
    )
    assert proc.returncode == 0, proc.stderr
    return output / "capture_manifest.json"


def test_geometry_analyzer_detects_zero_size():
    from PySide6.QtWidgets import QApplication, QLabel, QWidget
    from ui_preview.geometry import analyze_geometry

    qapp = QApplication.instance() or QApplication([])
    window = QWidget()
    window.resize(220, 100)
    zero = QWidget(window)
    zero.setObjectName("zero_child")
    zero.setGeometry(10, 10, 0, 0)
    window.show()
    zero.show()
    qapp.processEvents()
    findings = analyze_geometry(window, window, "test.geometry")
    window.close()

    assert any(
        item["code"] == "zero_size" and item["object_name"] == "zero_child"
        for item in findings
    )


def test_text_overflow_requires_reliable_proportional_font_metrics():
    from ui_preview.geometry import _text_overflows

    class ReliableMetrics:
        def horizontalAdvance(self, text):
            return {"iiiiiiii": 24, "WWWWWWWW": 88}.get(text, len(text) * 8)

    class UnreliableMetrics:
        def horizontalAdvance(self, text):
            return len(text) * 12

    assert _text_overflows(ReliableMetrics(), "uzun metin", 40) is True
    assert _text_overflows(ReliableMetrics(), "kısa", 80) is False
    assert _text_overflows(UnreliableMetrics(), "uzun metin", 40) is None


def test_step_indicator_long_titles_keep_connectors_visible():
    from PySide6.QtWidgets import QApplication
    from ui.create_offer_page import StepIndicator
    from ui_preview.geometry import analyze_geometry

    qapp = QApplication.instance() or QApplication([])
    indicator = StepIndicator([
        "Müşteri ve İletişim Bilgileri",
        "Ürün, Miktar ve Fiyatlandırma",
        "Teklif Koşulları ve Son Kontrol",
    ])
    indicator.resize(1266, 36)
    indicator.set_step(1)
    indicator.show()
    qapp.processEvents()
    findings = analyze_geometry(indicator, indicator, "component.step_indicator.long_titles")
    connector_widths = [line.width() for line in indicator._lines]
    indicator.close()

    assert connector_widths == [12, 12]
    assert not [item for item in findings if item["severity"] == "critical"]


def test_geometry_surface_cli_checks_every_catalog_surface_without_critical_error():
    proc = _run("--geometry-surfaces", "--json")
    assert proc.returncode == 0, proc.stderr
    result = json.loads(proc.stdout)
    assert result["ok"] is True
    assert result["checked"] == 44
    assert result["critical_count"] == 0
    assert result["text_metrics_reliable"] is False
    assert result["warning_count"] == 0
    assert result["external_effects"] == []
    assert result["real_credential_accesses"] == 0


def test_baseline_plan_is_read_only_and_returns_content_bound_token(tmp_path):
    manifest = _capture(tmp_path)
    baseline_root = tmp_path / "baselines"
    proc = _run("--baseline-plan", str(manifest), "--json")
    assert proc.returncode == 0, proc.stderr
    result = json.loads(proc.stdout)
    assert result["ok"] is True
    assert result["capture_count"] == 1
    assert result["approval_token"].startswith("ACCEPT-")
    assert len(result["manifest_sha256"]) == 64
    assert not baseline_root.exists()


def test_baseline_accept_requires_exact_token_and_never_overwrites(tmp_path):
    manifest = _capture(tmp_path)
    plan = _run("--baseline-plan", str(manifest), "--json")
    token = json.loads(plan.stdout)["approval_token"]
    baseline_root = tmp_path / "baselines"

    denied = _run(
        "--baseline-accept", str(manifest), "--baseline-root", str(baseline_root),
        "--approval-token", "ACCEPT-WRONG", "--json",
    )
    assert denied.returncode != 0
    assert not baseline_root.exists()

    accepted = _run(
        "--baseline-accept", str(manifest), "--baseline-root", str(baseline_root),
        "--approval-token", token, "--json",
    )
    assert accepted.returncode == 0, accepted.stderr
    result = json.loads(accepted.stdout)
    version = baseline_root / result["version"]
    assert (version / "capture_manifest.json").is_file()
    assert (version / "baseline_record.json").is_file()
    record = json.loads((version / "baseline_record.json").read_text("utf-8"))
    assert record["synthetic_only"] is True
    assert record["approval_token"] == token
    assert len(list((version / "images").glob("*.png"))) == 1

    again = _run(
        "--baseline-accept", str(manifest), "--baseline-root", str(baseline_root),
        "--approval-token", token, "--json",
    )
    assert again.returncode != 0
    assert json.loads((version / "baseline_record.json").read_text("utf-8")) == record


def test_baseline_rejects_tampered_capture_before_plan_or_write(tmp_path):
    manifest = _capture(tmp_path)
    data = json.loads(manifest.read_text("utf-8"))
    png = manifest.parent / data["captures"][0]["file"]
    png.write_bytes(png.read_bytes() + b"tamper")
    baseline_root = tmp_path / "baselines"
    plan = _run("--baseline-plan", str(manifest), "--json")
    assert plan.returncode != 0
    assert not baseline_root.exists()

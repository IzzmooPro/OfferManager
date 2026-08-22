"""Açık token onaylı ve üzerine yazılamayan sentetik görsel baseline akışı."""

from __future__ import annotations

import hashlib
import json
import secrets
import shutil
from pathlib import Path
from typing import Any

from ui_preview.capture import CaptureError, load_verified_capture_manifest


def _manifest_sha(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest().upper()


def plan_baseline(manifest_path: Path) -> dict[str, Any]:
    """Yazma yapmadan adayı doğrula ve içeriğe bağlı onay token'ı üret."""
    manifest_path = Path(manifest_path).resolve()
    data, _ = load_verified_capture_manifest(manifest_path)
    digest = _manifest_sha(manifest_path)
    return {
        "capture_count": data["capture_count"],
        "label": data["label"],
        "source_fingerprint": data.get("source_fingerprint", ""),
        "manifest_sha256": digest,
        "approval_token": f"ACCEPT-{digest[:16]}",
        "version": f"baseline-{digest[:16].lower()}",
        "synthetic_only": True,
    }


def accept_baseline(
    manifest_path: Path,
    baseline_root: Path,
    approval_token: str,
) -> dict[str, Any]:
    """Tam doğrulanmış capture'ı yeni, değiştirilemez bir sürüme kopyala."""
    manifest_path = Path(manifest_path).resolve()
    plan = plan_baseline(manifest_path)
    if approval_token != plan["approval_token"]:
        raise CaptureError("Baseline onay token'ı bu capture içeriğiyle uyuşmuyor")

    data, capture_root = load_verified_capture_manifest(manifest_path)
    baseline_root = Path(baseline_root).resolve()
    if baseline_root.exists() and not baseline_root.is_dir():
        raise CaptureError("Baseline kökü klasör olmalı")
    version = baseline_root / plan["version"]
    if version.exists():
        raise CaptureError("Baseline sürümü zaten var; üzerine yazma yasaktır")

    baseline_root.mkdir(parents=True, exist_ok=True)
    stage = baseline_root / f".{plan['version']}.stage-{secrets.token_hex(8)}"
    stage.mkdir()
    try:
        images = stage / "images"
        images.mkdir()
        for item in data["captures"]:
            source = (capture_root / item["file"]).resolve()
            target = stage / item["file"]
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
        shutil.copy2(manifest_path, stage / "capture_manifest.json")
        record = {
            "schema_version": 1,
            "kind": "ui_preview_baseline",
            "synthetic_only": True,
            "immutable": True,
            "approval_token": approval_token,
            "manifest_sha256": plan["manifest_sha256"],
            "source_fingerprint": plan["source_fingerprint"],
            "capture_count": plan["capture_count"],
            "version": plan["version"],
        }
        (stage / "baseline_record.json").write_text(
            json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        stage.replace(version)
    except Exception:
        if stage.exists():
            shutil.rmtree(stage)
        raise
    return {
        "accepted": plan["capture_count"],
        "version": plan["version"],
        "manifest_sha256": plan["manifest_sha256"],
        "synthetic_only": True,
    }

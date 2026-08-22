"""UI Preview Lab sandbox ve deterministik fixture sözleşmesi."""

from __future__ import annotations

import json
import gc
import os
import socket
import smtplib
import sqlite3
import subprocess
import sys
import types
import urllib.request
import webbrowser
from contextlib import closing
from pathlib import Path

import pytest

from ui_preview.fixtures import build_fixture_profile
from ui_preview.sandbox import (
    ExternalEffectBlocked,
    PreviewSandbox,
    SandboxViolation,
)


ROOT = Path(__file__).resolve().parents[1]
_SENSITIVE_MODULES = {"core.app_paths", "core.config", "database.db_manager"}
_ISOLATED_CHILD = "OMS_UI_PREVIEW_TEST_CHILD"


def _delegate_if_production_modules_are_loaded(request) -> bool:
    """Tam suite sırasında bu fail-closed testini temiz alt süreçte yürüt."""
    if os.environ.get(_ISOLATED_CHILD) == "1":
        return False
    if not (_SENSITIVE_MODULES & set(sys.modules)):
        return False
    env = dict(os.environ)
    env[_ISOLATED_CHILD] = "1"
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", request.node.nodeid, "-q"],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        timeout=90,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    return True


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def test_app_paths_resolve_only_inside_preview_root_in_fresh_process():
    code = r"""
import json
from ui_preview.sandbox import PreviewSandbox
with PreviewSandbox() as sandbox:
    from core import app_paths
    print(json.dumps({
        "root": str(sandbox.paths.root),
        "data": str(app_paths.DATA_DIR),
        "db": str(app_paths.DB_PATH),
        "backup": str(app_paths.BACKUP_DIR),
        "log": str(app_paths.LOG_DIR),
        "preview": __import__("os").environ.get("OMS_UI_PREVIEW"),
    }))
"""
    proc = subprocess.run(
        [sys.executable, "-c", code], cwd=ROOT, text=True,
        capture_output=True, check=True,
    )
    data = json.loads(proc.stdout.strip().splitlines()[-1])
    root = Path(data["root"])
    for key in ("data", "db", "backup", "log"):
        assert _is_within(Path(data[key]), root), f"{key} sandbox dışına çıktı"
    assert data["preview"] == "1"


def test_sensitive_production_import_before_activation_fails_closed():
    key = "core.app_paths"
    previous = sys.modules.get(key)
    sys.modules[key] = types.ModuleType(key)
    try:
        with pytest.raises(SandboxViolation, match="erken import"):
            with PreviewSandbox():
                pass
    finally:
        if previous is None:
            sys.modules.pop(key, None)
        else:
            sys.modules[key] = previous


def test_external_effects_are_blocked_and_audited(request):
    if _delegate_if_production_modules_are_loaded(request):
        return
    from PySide6.QtCore import QProcess, QUrl
    from PySide6.QtGui import QDesktopServices

    with PreviewSandbox() as sandbox:
        blocked = [
            lambda: socket.create_connection(("example.com", 443)),
            lambda: urllib.request.urlopen("https://example.com"),
            lambda: smtplib.SMTP("smtp.example.invalid", 25),
            lambda: webbrowser.open("https://example.com"),
            lambda: subprocess.run([sys.executable, "--version"]),
            lambda: os.system("echo preview-should-not-run"),
            lambda: QDesktopServices.openUrl(QUrl("https://example.com")),
            lambda: QProcess.startDetached(sys.executable, ["--version"]),
        ]
        if hasattr(os, "startfile"):
            blocked.append(lambda: os.startfile(str(sandbox.paths.root)))

        for operation in blocked:
            with pytest.raises(ExternalEffectBlocked):
                operation()

        effects = {event["effect"] for event in sandbox.audit.events}
        assert {
            "network", "browser", "subprocess", "os_system",
            "qt_open_url", "qt_process",
        } <= effects
        if hasattr(os, "startfile"):
            assert "os_startfile" in effects


def test_keyring_is_memory_only_and_records_no_real_access(request):
    if _delegate_if_production_modules_are_loaded(request):
        return
    import keyring

    with PreviewSandbox() as sandbox:
        assert keyring.get_password("preview", "user") is None
        keyring.set_password("preview", "user", "synthetic-secret")
        assert keyring.get_password("preview", "user") == "synthetic-secret"
        keyring.delete_password("preview", "user")
        assert keyring.get_password("preview", "user") is None

        assert sandbox.audit.real_credential_accesses == 0
        assert [item["operation"] for item in sandbox.audit.credential_events] == [
            "get", "set", "get", "delete", "get",
        ]


def test_environment_and_temporary_root_are_restored_after_exit(request):
    if _delegate_if_production_modules_are_loaded(request):
        return
    keys = ("USERPROFILE", "LOCALAPPDATA", "APPDATA", "TEMP", "OMS_UI_PREVIEW")
    before = {key: os.environ.get(key) for key in keys}
    with PreviewSandbox() as sandbox:
        root = sandbox.paths.root
        assert root.is_dir()
        assert os.environ["OMS_UI_PREVIEW"] == "1"

    assert not root.exists(), "Preview geçici kökü kapanıştan sonra kaldı"
    assert {key: os.environ.get(key) for key in keys} == before


@pytest.mark.parametrize(
    ("profile", "expected"),
    [
        ("empty", {"customers": 0, "products": 0, "offers": 0}),
        ("populated", {"customers": 4, "products": 8, "offers": 5}),
        ("dense", {"customers": 40, "products": 80, "offers": 60}),
    ],
)
def test_fixture_profiles_are_isolated_valid_and_deterministic(profile, expected, request):
    if _delegate_if_production_modules_are_loaded(request):
        return
    manifests = []
    for _ in range(2):
        with PreviewSandbox() as sandbox:
            manifest = build_fixture_profile(sandbox, profile)
            manifests.append(manifest)

            assert manifest["profile"] == profile
            assert manifest["counts"] | expected == manifest["counts"]
            assert manifest["counts"]["customers"] == expected["customers"]
            assert manifest["counts"]["products"] == expected["products"]
            assert manifest["counts"]["offers"] == expected["offers"]
            assert not any(Path(value).is_absolute()
                           for value in manifest["relative_paths"].values())

            db_path = sandbox.paths.data / manifest["relative_paths"]["database"]
            with closing(sqlite3.connect(db_path)) as conn:
                conn.execute("PRAGMA foreign_keys = ON")
                assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
                assert conn.execute("PRAGMA foreign_key_check").fetchall() == []

            for relative in manifest["relative_paths"].values():
                assert (sandbox.paths.data / relative).is_file()

            config = (sandbox.paths.data / manifest["relative_paths"]["config"])
            config_text = config.read_text(encoding="utf-8")
            assert "SENSORYUM" not in config_text
            assert "PREVIEW TEKNOLOJİ" in config_text
            assert "example.invalid" in config_text

    assert manifests[0] == manifests[1]


def test_unknown_fixture_profile_is_rejected_without_fallback(request):
    if _delegate_if_production_modules_are_loaded(request):
        return
    with PreviewSandbox() as sandbox:
        with pytest.raises(ValueError, match="Bilinmeyen preview fixture profili"):
            build_fixture_profile(sandbox, "production")


def test_fixture_images_and_pdf_are_readable_by_real_rendering_libraries(request):
    if _delegate_if_production_modules_are_loaded(request):
        return
    from PIL import Image
    from PySide6.QtPdf import QPdfDocument

    with PreviewSandbox() as sandbox:
        manifest = build_fixture_profile(sandbox, "populated")
        for key in ("logo", "signature1", "signature2", "signature3", "signature4"):
            path = sandbox.paths.data / manifest["relative_paths"][key]
            with Image.open(path) as image:
                image.verify()

        pdf_path = sandbox.paths.data / manifest["relative_paths"]["sample_pdf"]
        document = QPdfDocument()
        error = document.load(str(pdf_path))
        assert error == QPdfDocument.Error.None_
        assert document.pageCount() == 1
        document.close()
        del document
        gc.collect()  # Windows dosya tanıtıcısı sandbox cleanup'tan önce kapanmalı.

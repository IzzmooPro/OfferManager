"""UI Preview Lab için fail-closed süreç sandbox'ı.

Bu modül üretim modüllerini import etmez. Ortam ve dış-etki blokları, path
sabitlerini import anında hesaplayan ``core.app_paths`` yüklenmeden önce
kurulmalıdır.
"""

from __future__ import annotations

import os
import smtplib
import socket
import subprocess
import sys
import tempfile
import urllib.request
import webbrowser
from contextlib import ExitStack
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable
from unittest import mock


class SandboxViolation(RuntimeError):
    """Preview güvenlik önkoşulu sağlanmadığında yükseltilir."""


class ExternalEffectBlocked(SandboxViolation):
    """Preview sırasında ağ veya dış süreç girişimi engellendiğinde yükselir."""


@dataclass(frozen=True)
class SandboxPaths:
    root: Path
    profile: Path
    local_app_data: Path
    roaming_app_data: Path
    documents: Path
    temp: Path
    data: Path
    backups: Path
    output: Path


@dataclass
class SandboxAudit:
    events: list[dict[str, str]] = field(default_factory=list)
    credential_events: list[dict[str, str]] = field(default_factory=list)
    real_credential_accesses: int = 0


_EARLY_IMPORTS = (
    "core.app_paths",
    "core.config",
    "database.db_manager",
)


class PreviewSandbox:
    """Geçici profil, bellek içi credential ve dış-etki blokları.

    Nesne bir süreçte yalnız bir kez kullanılmalıdır. Üretim UI importları
    sandbox aktifken yapılır ve süreç preview tamamlandıktan sonra sonlanır.
    """

    def __init__(self, *, parent: Path | None = None):
        self._parent = Path(parent).resolve() if parent is not None else None
        self._temporary: tempfile.TemporaryDirectory[str] | None = None
        self._stack: ExitStack | None = None
        self._old_tempdir: str | None = None
        self._credential_store: dict[tuple[str, str], str] = {}
        self.audit = SandboxAudit()
        self.paths: SandboxPaths

    def _check_early_imports(self) -> None:
        imported = [name for name in _EARLY_IMPORTS if name in sys.modules]
        if imported:
            raise SandboxViolation(
                "Preview sandbox kurulmadan erken import edilen hassas modül: "
                + ", ".join(imported)
            )

    def _make_paths(self) -> SandboxPaths:
        if self._parent is not None:
            if not self._parent.is_dir():
                raise SandboxViolation("Preview geçici üst klasörü mevcut değil")
            self._temporary = tempfile.TemporaryDirectory(
                prefix="oms_ui_preview_", dir=str(self._parent)
            )
        else:
            self._temporary = tempfile.TemporaryDirectory(prefix="oms_ui_preview_")

        root = Path(self._temporary.name).resolve()
        profile = root / "profile"
        local = profile / "AppData" / "Local"
        roaming = profile / "AppData" / "Roaming"
        documents = profile / "Documents"
        temp = root / "temp"
        data = local / "OfferManagementSystem" / "data"
        backups = documents / "OfferManagementSystem" / "backups"
        output = root / "output"
        for path in (local, roaming, documents, temp, data, backups, output):
            path.mkdir(parents=True, exist_ok=True)
        return SandboxPaths(
            root=root,
            profile=profile,
            local_app_data=local,
            roaming_app_data=roaming,
            documents=documents,
            temp=temp,
            data=data,
            backups=backups,
            output=output,
        )

    def _environment(self) -> dict[str, str]:
        drive, tail = os.path.splitdrive(str(self.paths.profile))
        return {
            "USERPROFILE": str(self.paths.profile),
            "HOME": str(self.paths.profile),
            "LOCALAPPDATA": str(self.paths.local_app_data),
            "APPDATA": str(self.paths.roaming_app_data),
            "TMP": str(self.paths.temp),
            "TEMP": str(self.paths.temp),
            "HOMEDRIVE": drive,
            "HOMEPATH": tail or os.sep,
            "OMS_UI_PREVIEW": "1",
            "PYTHONHASHSEED": "0",
        }

    def _blocked(self, effect: str) -> Callable:
        def blocker(*_args, **_kwargs):
            self.audit.events.append({"effect": effect, "result": "blocked"})
            raise ExternalEffectBlocked(f"Preview dış etkisi engellendi: {effect}")

        return blocker

    def _install_keyring(self, stack: ExitStack) -> None:
        try:
            import keyring
            from keyring.errors import PasswordDeleteError
        except ImportError as exc:  # pragma: no cover - zorunlu bağımlılık
            raise SandboxViolation("keyring güvenlik sarmalayıcısı kurulamadı") from exc

        def get_password(service: str, username: str):
            self.audit.credential_events.append(
                {"operation": "get", "service": service, "username": username}
            )
            return self._credential_store.get((service, username))

        def set_password(service: str, username: str, password: str):
            self.audit.credential_events.append(
                {"operation": "set", "service": service, "username": username}
            )
            self._credential_store[(service, username)] = password

        def delete_password(service: str, username: str):
            self.audit.credential_events.append(
                {"operation": "delete", "service": service, "username": username}
            )
            try:
                del self._credential_store[(service, username)]
            except KeyError as exc:
                raise PasswordDeleteError("preview kaydı yok") from exc

        stack.enter_context(mock.patch.object(keyring, "get_password", get_password))
        stack.enter_context(mock.patch.object(keyring, "set_password", set_password))
        stack.enter_context(mock.patch.object(keyring, "delete_password", delete_password))

    def _install_external_guards(self, stack: ExitStack) -> None:
        network = self._blocked("network")
        stack.enter_context(mock.patch.object(socket, "create_connection", network))
        stack.enter_context(mock.patch.object(socket.socket, "connect", network))
        stack.enter_context(mock.patch.object(socket.socket, "connect_ex", network))
        stack.enter_context(mock.patch.object(urllib.request, "urlopen", network))
        stack.enter_context(mock.patch.object(smtplib, "SMTP", network))
        stack.enter_context(mock.patch.object(smtplib, "SMTP_SSL", network))

        browser = self._blocked("browser")
        for name in ("open", "open_new", "open_new_tab"):
            stack.enter_context(mock.patch.object(webbrowser, name, browser))

        process = self._blocked("subprocess")
        for name in ("Popen", "run", "call", "check_call", "check_output"):
            stack.enter_context(mock.patch.object(subprocess, name, process))
        stack.enter_context(mock.patch.object(os, "system", self._blocked("os_system")))
        if hasattr(os, "startfile"):
            stack.enter_context(
                mock.patch.object(os, "startfile", self._blocked("os_startfile"))
            )

        # Uygulama QDesktopServices ve QProcess yollarını da kullanabilir.
        try:
            from PySide6.QtCore import QProcess
            from PySide6.QtGui import QDesktopServices
        except ImportError as exc:  # pragma: no cover - zorunlu bağımlılık
            raise SandboxViolation("Qt dış-etki blokları kurulamadı") from exc
        stack.enter_context(
            mock.patch.object(QDesktopServices, "openUrl", self._blocked("qt_open_url"))
        )
        stack.enter_context(
            mock.patch.object(QProcess, "startDetached", self._blocked("qt_process"))
        )

    def __enter__(self) -> "PreviewSandbox":
        self._check_early_imports()
        self.paths = self._make_paths()
        stack = ExitStack()
        self._stack = stack
        try:
            stack.enter_context(mock.patch.dict(os.environ, self._environment()))
            self._old_tempdir = tempfile.tempdir
            tempfile.tempdir = str(self.paths.temp)
            self._install_keyring(stack)
            self._install_external_guards(stack)
        except Exception:
            tempfile.tempdir = self._old_tempdir
            stack.close()
            if self._temporary is not None:
                self._temporary.cleanup()
            raise
        return self

    def __exit__(self, exc_type, exc, traceback) -> bool:
        tempfile.tempdir = self._old_tempdir
        if self._stack is not None:
            self._stack.close()
        if self._temporary is not None:
            self._temporary.cleanup()
        return False

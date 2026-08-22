"""Print a compact, read-only project state for Claude preflight/release checks."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
UNAVAILABLE = "UNAVAILABLE"


def read(path: str) -> str:
    file_path = ROOT / path
    return file_path.read_text(encoding="utf-8") if file_path.exists() else ""


def match(path: str, pattern: str) -> str:
    found = re.search(pattern, read(path), re.MULTILINE)
    return found.group(1).strip() if found else "MISSING"


def git(*args: str) -> str:
    try:
        result = subprocess.run(
            ["git", *args], cwd=ROOT, text=True, encoding="utf-8",
            errors="replace", capture_output=True, check=True,
        )
        return result.stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return UNAVAILABLE


def normalize(value: str) -> str:
    if value in {"MISSING", UNAVAILABLE}:
        return value
    value = value.strip().lower().lstrip("v")
    parts = value.split(".")
    while len(parts) > 2 and parts[-1] == "0":
        parts.pop()
    return "v" + ".".join(parts)


def configure_output() -> None:
    """Claude/PTY yakalayıcıları için Türkçe çıktıyı kararlı tut."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure:
            reconfigure(encoding="utf-8", errors="replace")


def load_manifest() -> dict:
    path = ROOT / "PROJECT_GUIDE" / "project_manifest.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def source_versions() -> dict[str, str]:
    """Manifestteki kaynak sürüm alanlarını tek yerde ölç."""
    return {
        "app": normalize(match(
            "core/constants.py", r'^APP_VERSION\s*=\s*["\']([^"\']+)["\']')),
        "inno": normalize(match(
            "packaging/TeklifYonetim.iss",
            r'^#define\s+MyAppVersion\s+"([^"]+)"')),
        "inno_numeric": normalize(match(
            "packaging/TeklifYonetim.iss",
            r'^VersionInfoVersion\s*=\s*([^\s]+)')),
        "file_product": normalize(match(
            "packaging/version_info.txt",
            r"StringStruct\('ProductVersion',\s*'([^']+)'\)")),
        "file_numeric": normalize(match(
            "packaging/version_info.txt",
            r"StringStruct\('FileVersion',\s*'([^']+)'\)")),
    }


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def artifact_errors(manifest: dict) -> list[str]:
    errors: list[str] = []
    snapshot = manifest.get("snapshot") or {}
    for key in ("dist_exe", "installer"):
        info = snapshot.get(key) or {}
        relative = str(info.get("path", "")).strip()
        path = ROOT / relative
        if not relative or not path.is_file():
            errors.append(f"{key} missing")
            continue
        expected_size = info.get("size")
        if not isinstance(expected_size, int) or path.stat().st_size != expected_size:
            errors.append(f"{key} size mismatch")
        expected_hash = str(info.get("sha256", "")).upper()
        if not expected_hash or sha256(path) != expected_hash:
            errors.append(f"{key} SHA256 mismatch")
    return errors


def canonical_release_gate() -> bool:
    verifier = ROOT / "PROJECT_GUIDE" / "scripts" / "verify_project_guide.py"
    try:
        result = subprocess.run(
            [sys.executable, str(verifier), "--release"], cwd=ROOT,
            text=True, encoding="utf-8", errors="replace",
            capture_output=True, check=False,
        )
    except OSError:
        return False
    return result.returncode == 0


def main() -> int:
    configure_output()
    parser = argparse.ArgumentParser()
    parser.add_argument("--expect", help="Expected version, for example v4.1")
    parser.add_argument("--require-installer", action="store_true")
    args = parser.parse_args()

    versions = source_versions()
    manifest = load_manifest()
    snapshot = manifest.get("snapshot") or {}
    source_match = ("MISSING" not in versions.values()
                    and len(set(versions.values())) == 1)

    installer_version = args.expect or versions["app"]
    installer = ROOT / "installer_output" / f"TeklifYonetim_Setup_{installer_version}.exe"
    exe = ROOT / "dist" / "TeklifYonetim" / "TeklifYonetim.exe"
    status = git("status", "--short")
    branch = git("branch", "--show-current")
    head = git("log", "-1", "--format=%h %cs %s")
    git_available = UNAVAILABLE not in (status, branch, head)
    artifacts = artifact_errors(manifest)
    manifest_ready = snapshot.get("release_candidate_ready") is True
    release_ready = source_match and git_available and not artifacts and manifest_ready

    print(f"ROOT: {ROOT}")
    print(f"GIT: branch={branch} head={head}")
    print(f"DIRTY: {'unknown' if status == UNAVAILABLE else ('clean' if not status else status)}")
    print("VERSIONS: " + " ".join(f"{key}={value}" for key, value in versions.items()))
    print(f"SOURCE_VERSION_MATCH: {'yes' if source_match else 'no'}")
    print(f"BUILD_EXE: {'present' if exe.exists() else 'missing'}" + (f" size={exe.stat().st_size}" if exe.exists() else ""))
    print(f"INSTALLER: {'present' if installer.exists() else 'missing'} path={installer.relative_to(ROOT)}" + (f" size={installer.stat().st_size}" if installer.exists() else ""))
    print(f"MANIFEST_RELEASE_CANDIDATE: {'yes' if manifest_ready else 'no'}")
    print(f"ARTIFACT_CHECK: {'pass' if not artifacts else '; '.join(artifacts)}")
    print(f"RELEASE_READY: {'yes' if release_ready else 'no'}")
    print("LOCAL_ONLY: packaging assets docs/local/SORUN_COZUM_NOTLARI.md .claude")
    print("DATA: %LOCALAPPDATA%\\OfferManagementSystem\\data (do not use for tests)")

    errors: list[str] = []
    if args.expect:
        expected = normalize(args.expect)
        bad = [key for key, value in versions.items() if value != expected]
        if bad:
            errors.append(f"expected {expected}; mismatch: {', '.join(bad)}")
        manifest_target = normalize(str(snapshot.get("version", "MISSING")))
        if manifest_target != expected:
            errors.append(f"expected {expected}; manifest mismatch")
        if not git_available:
            errors.append("git state unavailable")
    if args.require_installer:
        if artifacts:
            errors.extend(artifacts)
        gate_ok = canonical_release_gate()
        print(f"CANONICAL_RELEASE_GATE: {'pass' if gate_ok else 'fail'}")
        if not gate_ok:
            errors.append("canonical release gate failed")
        if not release_ready:
            errors.append("release readiness requirements not met")
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

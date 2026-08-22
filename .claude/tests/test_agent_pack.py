from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def load(name: str, relative: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


validator = load("validate_agent_pack", ".claude/scripts/validate_agent_pack.py")
state = load("offer_state", ".claude/scripts/offer_state.py")


def test_agent_pack_contract_is_clean():
    assert validator.validate(ROOT) == []


def test_shared_pack_and_local_state_git_boundaries_are_explicit():
    lines = {
        line.strip() for line in (ROOT / ".gitignore").read_text(
            encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }
    assert ".claude/" not in lines
    assert set(validator.LOCAL_ONLY_AGENT_PATHS) <= lines


def test_all_skill_names_match_folder_and_have_description():
    for path in (ROOT / ".claude" / "skills").glob("*/SKILL.md"):
        meta = validator.frontmatter(path)
        assert meta["name"] == path.parent.name
        assert meta["description"]


def test_numeric_and_product_versions_normalize_together():
    assert state.normalize("v4.2") == "v4.2"
    assert state.normalize("4.2.0.0") == "v4.2"


def test_current_source_version_fields_match():
    versions = state.source_versions()
    assert "MISSING" not in versions.values()
    assert len(set(versions.values())) == 1


def test_missing_artifacts_fail_closed(tmp_path, monkeypatch):
    monkeypatch.setattr(state, "ROOT", tmp_path)
    manifest = {
        "snapshot": {
            "dist_exe": {"path": "dist/App.exe", "size": 1, "sha256": "00"},
            "installer": {"path": "out/Setup.exe", "size": 1, "sha256": "00"},
        }
    }
    assert state.artifact_errors(manifest) == [
        "dist_exe missing", "installer missing"]


def test_preflight_output_is_utf8_and_separates_release_readiness():
    expected = state.source_versions()["app"]
    result = subprocess.run(
        [sys.executable, str(ROOT / ".claude/scripts/offer_state.py"),
         "--expect", expected],
        cwd=ROOT, capture_output=True, check=False,
    )
    output = result.stdout.decode("utf-8")
    assert result.returncode == 0, result.stderr.decode("utf-8", errors="replace")
    assert f"ROOT: {ROOT}" in output
    assert "SOURCE_VERSION_MATCH: yes" in output
    assert "RELEASE_READY:" in output
    assert not any(line.startswith("VERSION_MATCH:")
                   for line in output.splitlines())

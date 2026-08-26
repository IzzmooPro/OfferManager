"""Aşama 4: bütün katalog yüzey/durumlarının gerçek factory kapsamı."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from collections import Counter
from pathlib import Path

from ui_preview.registry import ScenarioRegistry


ROOT = Path(__file__).resolve().parents[1]


def test_every_catalog_state_has_a_factory_binding():
    registry = ScenarioRegistry.load()
    assert registry.catalog_status == "geometry_baseline_ready"
    assert registry.surface_count == 44
    assert registry.state_count == 188
    assert registry.scenario_count == registry.state_count
    assert registry.missing_state_count == 0

    per_surface = Counter(item.surface_id for item in registry.scenarios)
    assert set(per_surface) == {surface["id"] for surface in registry.surfaces}
    for surface in registry.surfaces:
        assert per_surface[surface["id"]] == len(surface["states"])


def test_surface_bindings_are_unique_and_state_aware():
    data = json.loads((ROOT / "ui_preview" / "scenarios.json").read_text("utf-8"))
    bindings = data["surface_bindings"]
    ids = [binding["surface_id"] for binding in bindings]
    assert len(ids) == len(set(ids)) == 44
    secure = next(
        binding for binding in bindings
        if binding["surface_id"] == "modal.secure_storage_warning"
    )
    assert secure["factory"] == (
        "ui_preview.scenarios.runtime:make_secure_storage_warning"
    )
    assert all(binding["factory"].startswith("ui_preview.scenarios.") for binding in bindings)
    assert all(":" in binding["factory"] for binding in bindings)


def test_representative_scenario_for_every_surface_smokes_in_one_sandbox():
    env = dict(os.environ)
    env["QT_QPA_PLATFORM"] = "offscreen"
    proc = subprocess.run(
        [sys.executable, "-m", "ui_preview", "--smoke-surfaces", "--json"],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        timeout=60,
    )
    assert proc.returncode == 0, proc.stderr
    data = json.loads(proc.stdout)
    assert data["ok"] is True
    assert data["surface_count"] == 44
    assert data["smoked"] == 44
    assert data["failed"] == []
    assert data["external_effects"] == []
    assert data["real_credential_accesses"] == 0


def test_all_catalog_states_smoke_as_real_widgets():
    env = dict(os.environ)
    env["QT_QPA_PLATFORM"] = "offscreen"
    proc = subprocess.run(
        [sys.executable, "-m", "ui_preview", "--smoke-all", "--json"],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        timeout=180,
    )
    assert proc.returncode == 0, proc.stderr
    data = json.loads(proc.stdout)
    assert data["ok"] is True
    assert data["scenario_count"] == 188
    assert data["smoked"] == 188
    assert data["failed"] == []
    assert data["external_effects"] == []
    assert data["real_credential_accesses"] == 0

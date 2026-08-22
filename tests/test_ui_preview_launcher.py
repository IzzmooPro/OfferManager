"""UI Preview registry, CLI ve launcher sözleşmesi."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from ui_preview.registry import RegistryError, ScenarioRegistry


ROOT = Path(__file__).resolve().parents[1]


def _run_preview(*args: str) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env["QT_QPA_PLATFORM"] = "offscreen"
    return subprocess.run(
        [sys.executable, "-m", "ui_preview", *args],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        timeout=30,
    )


def test_registry_references_only_catalogued_surface_states():
    registry = ScenarioRegistry.load()
    assert registry.catalog_status == "geometry_baseline_ready"
    assert registry.surface_count == 43
    assert registry.scenario_count == 186
    assert registry.missing_state_count == 0

    ids = [scenario.id for scenario in registry.scenarios]
    assert ids == sorted(ids)
    assert len(ids) == len(set(ids))
    for scenario in registry.scenarios:
        surface = registry.surface(scenario.surface_id)
        assert scenario.state in surface["states"]
        assert scenario.profile in {"empty", "populated", "dense"}
        assert scenario.theme in {"light", "dark"}
        assert scenario.viewport in registry.viewport_sizes
        assert scenario.id == f"{scenario.surface_id}.{scenario.state}"


def test_factory_resolution_is_forbidden_outside_active_sandbox():
    scenario = ScenarioRegistry.load().scenario("component.plus_button.normal")
    with pytest.raises(RegistryError, match="aktif preview sandbox"):
        scenario.resolve_factory()


def test_registry_rejects_unknown_surface_and_state(tmp_path):
    catalog = json.loads((ROOT / "ui_preview" / "catalog.json").read_text("utf-8"))
    catalog_path = tmp_path / "catalog.json"
    catalog_path.write_text(json.dumps(catalog), encoding="utf-8")

    scenarios_path = tmp_path / "scenarios.json"
    invalid = {
        "schema_version": 1,
        "scenarios": [{
            "id": "page.unknown.empty",
            "surface_id": "page.unknown",
            "state": "empty",
            "profile": "empty",
            "theme": "light",
            "viewport": "1300x800",
            "presentation": "embedded",
            "factory": "ui_preview.scenarios.foundation:make_plus_button",
        }],
    }
    scenarios_path.write_text(json.dumps(invalid), encoding="utf-8")
    with pytest.raises(RegistryError, match="katalog yüzeyi yok"):
        ScenarioRegistry.load(catalog_path=catalog_path, scenarios_path=scenarios_path)

    invalid["scenarios"][0]["surface_id"] = "component.plus_button"
    invalid["scenarios"][0]["id"] = "component.plus_button.unknown"
    invalid["scenarios"][0]["state"] = "unknown"
    scenarios_path.write_text(json.dumps(invalid), encoding="utf-8")
    with pytest.raises(RegistryError, match="katalog durumu yok"):
        ScenarioRegistry.load(catalog_path=catalog_path, scenarios_path=scenarios_path)


def test_cli_list_is_read_only_and_machine_readable():
    proc = _run_preview("--list", "--json")
    assert proc.returncode == 0, proc.stderr
    data = json.loads(proc.stdout)
    assert data["catalog_status"] == "geometry_baseline_ready"
    assert data["surface_count"] == 43
    assert data["scenario_count"] == 186
    assert len(data["scenarios"]) == 186


def test_cli_check_validates_registry_without_starting_qt():
    proc = _run_preview("--check", "--json")
    assert proc.returncode == 0, proc.stderr
    data = json.loads(proc.stdout)
    assert data["ok"] is True
    assert data["production_ui_modified"] is True
    assert data["launcher"] == "implemented"


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_real_factory_smoke_returns_exact_production_widget(theme):
    proc = _run_preview(
        "--scenario", "component.plus_button.normal",
        "--theme", theme,
        "--viewport", "1100x700",
        "--profile", "empty",
        "--dpi", "100",
        "--smoke",
        "--json",
    )
    assert proc.returncode == 0, proc.stderr
    data = json.loads(proc.stdout)
    assert data["ok"] is True
    assert data["widget_class"] == "ui.widgets._plus_button.PlusButton"
    assert data["theme"] == theme
    assert data["resolved_theme"] == theme
    assert data["viewport"] == "1100x700"
    assert data["window_size"] == "1100x700"
    assert data["profile"] == "empty"
    assert data["dpi"] == 100
    assert data["external_effects"] == []
    assert data["real_credential_accesses"] == 0


@pytest.mark.parametrize(
    ("scenario_id", "expected_class", "profile"),
    [
        ("component.nav_card.normal", "ui.main_window.NavCard", "empty"),
        ("component.plus_button.normal", "ui.widgets._plus_button.PlusButton", "empty"),
        ("component.profit_panel.positive", "ui.widgets._profit_panel.ProfitPanel", "populated"),
        ("component.resizable_table.populated", "ui.widgets._resizable_table.ResizableTable", "populated"),
        ("component.step_indicator.first", "ui.create_offer_page.StepIndicator", "empty"),
    ],
)
def test_every_foundation_factory_opens_real_expected_class(
    scenario_id, expected_class, profile
):
    proc = _run_preview(
        "--scenario", scenario_id,
        "--profile", profile,
        "--smoke", "--json",
    )
    assert proc.returncode == 0, proc.stderr
    data = json.loads(proc.stdout)
    assert data["widget_class"] == expected_class
    assert data["external_effects"] == []


def test_launcher_smoke_exposes_catalog_and_controls():
    proc = _run_preview(
        "--launcher", "--profile", "populated", "--dpi", "125",
        "--smoke", "--json",
    )
    assert proc.returncode == 0, proc.stderr
    data = json.loads(proc.stdout)
    assert data["ok"] is True
    assert data["surface_count"] == 43
    assert data["implemented_scenarios"] == 186
    assert data["themes"] == ["light", "dark"]
    assert data["viewports"] == ["1100x700", "1300x800", "1600x900", "1920x1080"]
    assert data["dpi"] == 125
    assert data["planned_states_disabled"] == 0
    assert data["theme_switch_applied"] is True
    assert data["resolved_theme_after_switch"] == "dark"


def test_invalid_dpi_and_viewport_fail_before_launcher():
    bad_dpi = _run_preview("--launcher", "--dpi", "175", "--smoke")
    assert bad_dpi.returncode != 0
    assert "invalid choice" in bad_dpi.stderr.lower()

    bad_viewport = _run_preview(
        "--scenario", "component.plus_button.normal",
        "--viewport", "999x999", "--smoke",
    )
    assert bad_viewport.returncode != 0
    assert "invalid choice" in bad_viewport.stderr.lower()


def test_production_entry_point_has_no_preview_integration():
    main = (ROOT / "main.py").read_text(encoding="utf-8")
    assert "ui_preview" not in main

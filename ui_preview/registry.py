"""UI Preview senaryo kataloğu ve lazy factory çözümü."""

from __future__ import annotations

import importlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


class RegistryError(RuntimeError):
    """Katalog/senaryo sözleşmesi ihlali."""


@dataclass(frozen=True)
class ScenarioContext:
    sandbox: Any
    manifest: dict
    profile: str
    theme: str
    viewport: str
    dpi: int
    scenario_id: str = ""
    surface_id: str = ""
    state: str = ""


@dataclass(frozen=True)
class Scenario:
    id: str
    surface_id: str
    state: str
    profile: str
    theme: str
    viewport: str
    presentation: str
    factory: str
    expected_class: str

    def resolve_factory(self) -> Callable[[ScenarioContext], Any]:
        if os.environ.get("OMS_UI_PREVIEW") != "1":
            raise RegistryError("Factory çözümü için aktif preview sandbox gerekir")
        module_name, separator, function_name = self.factory.partition(":")
        if not separator or not module_name or not function_name:
            raise RegistryError(f"Geçersiz factory başvurusu: {self.factory}")
        module = importlib.import_module(module_name)
        factory = getattr(module, function_name, None)
        if not callable(factory):
            raise RegistryError(f"Factory çağrılabilir değil: {self.factory}")
        return factory


class ScenarioRegistry:
    def __init__(self, catalog: dict, scenario_data: dict):
        self.catalog = catalog
        self.catalog_status = str(catalog.get("status", ""))
        self.production_ui_modified = bool(catalog.get("production_ui_modified"))
        self.surfaces = tuple(sorted(catalog.get("surfaces", []), key=lambda x: x["id"]))
        self._surfaces = {item["id"]: item for item in self.surfaces}
        self.viewport_sizes = tuple(catalog["planned_matrix"]["viewport_sizes"])
        self.themes = tuple(catalog["planned_matrix"]["themes"])
        self.profiles = tuple(catalog["infrastructure"]["fixture_profiles"])
        self.dpi_scales = tuple(catalog["planned_matrix"]["dpi_scales"])
        self._scenarios = self._validate_scenarios(scenario_data)

    @classmethod
    def load(
        cls,
        *,
        catalog_path: Path | None = None,
        scenarios_path: Path | None = None,
    ) -> "ScenarioRegistry":
        root = Path(__file__).resolve().parent
        catalog_path = catalog_path or root / "catalog.json"
        scenarios_path = scenarios_path or root / "scenarios.json"
        catalog = json.loads(Path(catalog_path).read_text(encoding="utf-8"))
        scenario_data = json.loads(Path(scenarios_path).read_text(encoding="utf-8"))
        if catalog.get("schema_version") != 1:
            raise RegistryError("Desteklenmeyen UI preview katalog şeması")
        if scenario_data.get("schema_version") != 1:
            raise RegistryError("Desteklenmeyen UI preview senaryo şeması")
        return cls(catalog, scenario_data)

    def _validate_scenarios(self, data: dict) -> tuple[Scenario, ...]:
        expanded = list(data.get("scenarios", []))
        expanded.extend(self._expand_surface_bindings(data.get("surface_bindings", [])))
        required = {
            "id", "surface_id", "state", "profile", "theme", "viewport",
            "presentation", "factory",
        }
        allowed_presentations = {"embedded", "standalone"}
        scenarios: list[Scenario] = []
        seen: set[str] = set()
        for raw in expanded:
            missing = required - set(raw)
            if missing:
                raise RegistryError(f"Senaryo alanı eksik: {sorted(missing)}")
            surface = self._surfaces.get(raw["surface_id"])
            if surface is None:
                raise RegistryError(f"Senaryo için katalog yüzeyi yok: {raw['surface_id']}")
            if raw["state"] not in surface["states"]:
                raise RegistryError(
                    f"Senaryo için katalog durumu yok: {raw['surface_id']}.{raw['state']}"
                )
            expected_id = f"{raw['surface_id']}.{raw['state']}"
            if raw["id"] != expected_id:
                raise RegistryError(f"Senaryo kimliği sözleşmeye uymuyor: {raw['id']}")
            if raw["id"] in seen:
                raise RegistryError(f"Mükerrer senaryo kimliği: {raw['id']}")
            if raw["profile"] not in self.profiles:
                raise RegistryError(f"Bilinmeyen fixture profili: {raw['profile']}")
            if raw["theme"] not in self.themes:
                raise RegistryError(f"Bilinmeyen tema: {raw['theme']}")
            if raw["viewport"] not in self.viewport_sizes:
                raise RegistryError(f"Bilinmeyen viewport: {raw['viewport']}")
            if raw["presentation"] not in allowed_presentations:
                raise RegistryError(f"Bilinmeyen sunum türü: {raw['presentation']}")
            if raw["factory"].count(":") != 1:
                raise RegistryError(f"Geçersiz factory başvurusu: {raw['factory']}")
            expected_class = raw.get("expected_class") or surface["source"].get(
                "qualified_class"
            )
            if not expected_class:
                raise RegistryError(
                    f"Uygulanan senaryoda qualified_class zorunlu: {raw['surface_id']}"
                )
            seen.add(raw["id"])
            scenarios.append(Scenario(
                id=raw["id"],
                surface_id=raw["surface_id"],
                state=raw["state"],
                profile=raw["profile"],
                theme=raw["theme"],
                viewport=raw["viewport"],
                presentation=raw["presentation"],
                factory=raw["factory"],
                expected_class=expected_class,
            ))
        return tuple(sorted(scenarios, key=lambda item: item.id))

    def _expand_surface_bindings(self, bindings: list[dict]) -> list[dict]:
        expanded: list[dict] = []
        seen_surfaces: set[str] = set()
        required = {"surface_id", "factory", "presentation"}
        for binding in bindings:
            missing = required - set(binding)
            if missing:
                raise RegistryError(f"Yüzey binding alanı eksik: {sorted(missing)}")
            surface_id = binding["surface_id"]
            if surface_id in seen_surfaces:
                raise RegistryError(f"Mükerrer yüzey binding: {surface_id}")
            seen_surfaces.add(surface_id)
            surface = self._surfaces.get(surface_id)
            if surface is None:
                raise RegistryError(f"Binding için katalog yüzeyi yok: {surface_id}")
            expected_class = binding.get("expected_class") or surface["source"].get(
                "qualified_class"
            )
            if not expected_class:
                raise RegistryError(f"Binding expected_class eksik: {surface_id}")
            default_profile = binding.get("profile", "populated")
            default_theme = binding.get("theme", "light")
            default_viewport = binding.get("viewport", "1300x800")
            state_profiles = binding.get("state_profiles", {})
            state_themes = binding.get("state_themes", {})
            state_viewports = binding.get("state_viewports", {})
            for state in surface["states"]:
                expanded.append({
                    "id": f"{surface_id}.{state}",
                    "surface_id": surface_id,
                    "state": state,
                    "profile": state_profiles.get(state, default_profile),
                    "theme": state_themes.get(state, default_theme),
                    "viewport": state_viewports.get(state, default_viewport),
                    "presentation": binding["presentation"],
                    "factory": binding["factory"],
                    "expected_class": expected_class,
                })
        return expanded

    @property
    def scenarios(self) -> tuple[Scenario, ...]:
        return self._scenarios

    @property
    def scenario_count(self) -> int:
        return len(self._scenarios)

    @property
    def surface_count(self) -> int:
        return len(self.surfaces)

    @property
    def state_count(self) -> int:
        return sum(len(surface["states"]) for surface in self.surfaces)

    @property
    def missing_state_count(self) -> int:
        return self.state_count - self.scenario_count

    def surface(self, surface_id: str) -> dict:
        try:
            return self._surfaces[surface_id]
        except KeyError as exc:
            raise RegistryError(f"Katalog yüzeyi yok: {surface_id}") from exc

    def scenario(self, scenario_id: str) -> Scenario:
        for scenario in self._scenarios:
            if scenario.id == scenario_id:
                return scenario
        raise RegistryError(f"Uygulanmış preview senaryosu yok: {scenario_id}")

    def scenario_or_none(self, scenario_id: str) -> Scenario | None:
        try:
            return self.scenario(scenario_id)
        except RegistryError:
            return None

    def summary(self) -> dict:
        return {
            "catalog_status": self.catalog_status,
            "surface_count": self.surface_count,
            "state_count": self.state_count,
            "scenario_count": self.scenario_count,
            "missing_state_count": self.missing_state_count,
            "production_ui_modified": self.production_ui_modified,
            "scenarios": [scenario.id for scenario in self.scenarios],
        }

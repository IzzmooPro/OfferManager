"""UI Preview Lab ekran envanteri sözleşmesi.

Bu testler üretim UI modüllerini import etmez. Kataloğu ve kaynak AST'sini
salt-okunur inceleyerek yeni bir görsel yüzeyin önizleme kapsamı dışında
unutulmasını engeller.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = ROOT / "ui_preview" / "catalog.json"
GUIDE_PATH = ROOT / "PROJECT_GUIDE" / "UI_PREVIEW_GUIDE.md"
INDEX_PATH = ROOT / "PROJECT_GUIDE" / "INDEX.md"

VISUAL_BASES = {
    "QComboBox",
    "QDialog",
    "QDoubleSpinBox",
    "QFrame",
    "QMainWindow",
    "QPushButton",
    "QWidget",
}

# Bunlar ekranda bağımsız bir tasarım yüzeyi değildir.
DISCOVERY_EXCLUSIONS = {
    "ui.create_offer_page._StepItem",
}


def _catalog() -> dict:
    return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))


def _base_name(node: ast.expr) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _visual_classes() -> set[str]:
    """Doğrudan veya yerel kalıtımla Qt widget'ı olan sınıfları bul."""
    classes: dict[str, set[str]] = {}
    for source in (ROOT / "ui").rglob("*.py"):
        if "__pycache__" in source.parts:
            continue
        tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
        module = source.relative_to(ROOT).with_suffix("").as_posix().replace("/", ".")
        for node in tree.body:
            if not isinstance(node, ast.ClassDef):
                continue
            classes[f"{module}.{node.name}"] = {
                name for base in node.bases if (name := _base_name(base))
            }

    found: set[str] = set()
    changed = True
    while changed:
        changed = False
        visual_names = {key.rsplit(".", 1)[-1] for key in found}
        for key, bases in classes.items():
            if key in found or key in DISCOVERY_EXCLUSIONS:
                continue
            if bases & (VISUAL_BASES | visual_names):
                found.add(key)
                changed = True
    return found


def test_catalog_schema_and_unique_ids():
    catalog = _catalog()
    assert catalog["schema_version"] == 1
    assert catalog["status"] == "geometry_baseline_ready"
    assert catalog["production_ui_modified"] is True
    assert catalog["infrastructure"] == {
        "sandbox": "implemented",
        "fixture_profiles": ["empty", "populated", "dense"],
        "launcher": "implemented",
        "capture": "implemented",
        "visual_baseline": "implemented",
        "geometry_checks": "implemented",
    }

    surfaces = catalog["surfaces"]
    assert surfaces, "UI preview kataloğu boş olamaz"
    ids = [item["id"] for item in surfaces]
    assert len(ids) == len(set(ids)), "UI preview kimlikleri benzersiz olmalı"

    allowed_kinds = {"window", "page", "dialog", "component", "runtime_modal"}
    allowed_priorities = {"critical", "standard", "supporting"}
    for item in surfaces:
        assert set(item) >= {
            "id", "kind", "title", "source", "priority", "states",
            "preview_status",
        }
        assert item["kind"] in allowed_kinds
        assert item["priority"] in allowed_priorities
        assert item["preview_status"] == "implemented"
        assert item["states"] and len(item["states"]) == len(set(item["states"]))


def test_every_catalog_source_exists_and_symbol_is_real():
    for item in _catalog()["surfaces"]:
        source = item["source"]
        path = ROOT / source["path"]
        assert path.is_file(), f"Katalog kaynak dosyası yok: {path}"

        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        symbols = {
            node.name
            for node in ast.walk(tree)
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
        }
        assert source["symbol"] in symbols, (
            f"Katalog sembolü kaynakta yok: {source['path']}::{source['symbol']}"
        )


def test_all_production_visual_classes_are_catalogued():
    catalogued = {
        item["source"].get("qualified_class")
        for item in _catalog()["surfaces"]
        if item["source"].get("qualified_class")
    }
    missing = sorted(_visual_classes() - catalogued)
    assert not missing, "Preview kataloğunda unutulan UI sınıfları:\n" + "\n".join(missing)


def test_preview_boundaries_are_fail_closed():
    boundaries = _catalog()["boundaries"]
    assert boundaries["temporary_profile_required"] is True
    assert boundaries["real_user_data_forbidden"] is True
    assert boundaries["credential_manager_forbidden"] is True
    assert boundaries["network_forbidden"] is True
    assert boundaries["external_process_launch_forbidden"] is True
    assert boundaries["automatic_baseline_update_forbidden"] is True
    assert boundaries["production_entry_point_integration_forbidden"] is True


def test_canonical_guide_routes_to_machine_readable_catalog():
    guide = GUIDE_PATH.read_text(encoding="utf-8")
    index = INDEX_PATH.read_text(encoding="utf-8")

    assert "UI_PREVIEW_GUIDE.md" in index
    assert "ui_preview/catalog.json" in guide
    assert "gerçek kullanıcı verisi" in guide.lower()
    assert "otomatik" in guide.lower() and "baseline" in guide.lower()
    assert "preview" in guide.lower() and "frozen" in guide.lower()

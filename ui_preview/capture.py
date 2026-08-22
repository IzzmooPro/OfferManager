"""Sentetik UI capture, temas sayfası ve before/after/diff raporu."""

from __future__ import annotations

import hashlib
import html
import json
import shutil
import tempfile
from pathlib import Path
from typing import Any, Iterable

from PIL import Image, ImageChops

from ui_preview.registry import ScenarioContext, ScenarioRegistry


class CaptureError(ValueError):
    """Capture/rapor sözleşmesi ihlali."""


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def _source_fingerprint(registry: ScenarioRegistry) -> str:
    """Capture'ı etkileyen kaynakların yol+byte parmak izi; mutlak yol yazmaz."""
    root = Path(__file__).resolve().parents[1]
    relative_paths = {
        "ui_preview/catalog.json",
        "ui_preview/scenarios.json",
        "ui_preview/capture.py",
        "ui_preview/launcher.py",
        "ui_preview/registry.py",
        "database/schema.sql",
    }
    relative_paths.update(surface["source"]["path"] for surface in registry.surfaces)
    for folder in ("ui", "ui_preview", "core", "services", "models"):
        relative_paths.update(
            path.relative_to(root).as_posix()
            for path in (root / folder).rglob("*.py")
            if "__pycache__" not in path.parts
        )
    digest = hashlib.sha256()
    for relative in sorted(relative_paths):
        relative_path = Path(relative)
        if relative_path.is_absolute() or ".." in relative_path.parts:
            raise CaptureError("Kaynak parmak izi yolu proje dışına çıkıyor")
        path = (root / relative_path).resolve()
        try:
            path.relative_to(root.resolve())
        except ValueError as exc:
            raise CaptureError("Kaynak parmak izi yolu proje dışına çıkıyor") from exc
        if not path.is_file():
            raise CaptureError(f"Kaynak parmak izi girdisi yok: {relative}")
        digest.update(relative.replace("\\", "/").encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest().upper()


def _safe_name(value: str) -> str:
    name = "".join(ch if ch.isalnum() or ch in "._-" else "-" for ch in value)
    name = name.strip(".-")
    if not name or name in {".", ".."}:
        raise CaptureError("Güvenli capture dosya adı üretilemedi")
    return name


def _validate_label(label: str) -> str:
    value = (label or "capture").strip()
    forbidden = set("/\\:<>&\r\n\t")
    if (not value or len(value) > 80 or any(ord(ch) < 32 for ch in value)
            or any(ch in forbidden for ch in value)):
        raise CaptureError(
            "Capture etiketi 1–80 karakter olmalı; yol/HTML işareti içermemeli")
    return value


def _fresh_stage(output: Path) -> tuple[Path, bool]:
    output = output.resolve()
    existed_empty = output.exists()
    if existed_empty:
        if not output.is_dir():
            raise CaptureError("Çıktı yolu klasör olmalı")
        if any(output.iterdir()):
            raise CaptureError("Sessiz üzerine yazma engellendi: çıktı klasörü boş değil")
    output.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=f".{output.name}.stage-", dir=output.parent))
    return stage, existed_empty


def _publish_stage(stage: Path, output: Path, existed_empty: bool) -> None:
    output = output.resolve()
    if existed_empty:
        output.rmdir()  # yalnız yukarıda doğrulanan boş, açık hedef
    stage.replace(output)


def _discard_stage(stage: Path) -> None:
    if stage.exists():
        shutil.rmtree(stage)


def _dispose(app, widget, window) -> None:
    document = getattr(widget, "_doc", None)
    if document is not None and hasattr(document, "close"):
        view = getattr(widget, "_view", None)
        if view is not None and hasattr(view, "setDocument"):
            view.setDocument(None)
        document.close()
        document.setParent(None)
        document.deleteLater()
        widget._doc = None
    window.close()
    window.deleteLater()
    from PySide6.QtCore import QCoreApplication, QEvent
    app.processEvents()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    app.processEvents()


def _capture_index(manifest: dict) -> str:
    cards = []
    for item in manifest["captures"]:
        cards.append(
            '<article class="card">'
            f'<h2>{html.escape(item["scenario_id"])}</h2>'
            f'<img src="{html.escape(item["file"])}" alt="{html.escape(item["scenario_id"])}">'
            f'<p>{html.escape(item["theme"])} · {html.escape(item["viewport"])} '
            f'· DPI %{item["dpi"]} · {item["width"]}×{item["height"]}</p>'
            "</article>"
        )
    return """<!doctype html><html lang="tr"><meta charset="utf-8">
<title>OMS UI Preview Capture</title><style>
body{font-family:Segoe UI,sans-serif;margin:24px;background:#eef1f6;color:#172033}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(360px,1fr));gap:18px}
.card{background:white;border:1px solid #ccd3df;border-radius:10px;padding:14px;overflow:auto}
img{max-width:100%;height:auto;border:1px solid #d5dae3}h1,h2{margin-top:0}p{color:#596579}
</style><body>""" + f"<h1>{html.escape(manifest['label'])}</h1><div class=\"grid\">" + "".join(cards) + "</div></body></html>"


def capture_scenarios(
    registry: ScenarioRegistry,
    context: ScenarioContext,
    scenario_ids: Iterable[str],
    output: Path,
    *,
    label: str = "capture",
) -> dict[str, Any]:
    """Gerçek widget'ları PNG olarak yakala ve kontrollü klasöre aktar."""
    output = Path(output)
    stage, existed_empty = _fresh_stage(output)
    label = _validate_label(label)
    # DPI ortamı __main__ tarafından ayarlandıktan sonra Qt/launcher import edilir.
    from ui_preview.launcher import apply_theme, create_preview_window, ensure_application
    app = ensure_application()
    apply_theme(app, context.theme)
    captures = []
    try:
        image_dir = stage / "images"
        image_dir.mkdir()
        for scenario_id in scenario_ids:
            scenario = registry.scenario(scenario_id)
            widget, window = create_preview_window(scenario, context)
            try:
                window.show()
                app.processEvents()
                app.processEvents()
                pixmap = window.grab()
                if pixmap.isNull() or pixmap.width() < 1 or pixmap.height() < 1:
                    raise CaptureError(f"PNG capture boş: {scenario.id}")
                filename = f"{_safe_name(scenario.id)}.png"
                relative = Path("images") / filename
                png_path = stage / relative
                if not pixmap.save(str(png_path), "PNG"):
                    raise CaptureError(f"PNG yazılamadı: {scenario.id}")
                actual = f"{type(widget).__module__}.{type(widget).__qualname__}"
                captures.append({
                    "scenario_id": scenario.id,
                    "surface_id": scenario.surface_id,
                    "state": scenario.state,
                    "widget_class": actual,
                    "profile": context.profile,
                    "theme": context.theme,
                    "viewport": context.viewport,
                    "dpi": context.dpi,
                    "width": pixmap.width(),
                    "height": pixmap.height(),
                    "file": relative.as_posix(),
                    "sha256": _sha256(png_path),
                })
            finally:
                _dispose(app, widget, window)
        from PySide6 import __version__ as pyside_version
        from PySide6.QtCore import qVersion
        manifest = {
            "schema_version": 1,
            "kind": "ui_preview_capture",
            "synthetic_only": True,
            "label": label,
            "source_fingerprint": _source_fingerprint(registry),
            "qt_version": qVersion(),
            "pyside_version": pyside_version,
            "capture_count": len(captures),
            "captures": captures,
        }
        (stage / "capture_manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        (stage / "index.html").write_text(_capture_index(manifest), encoding="utf-8")
        _publish_stage(stage, output, existed_empty)
        return {"captured": len(captures), "manifest": "capture_manifest.json"}
    except Exception:
        _discard_stage(stage)
        raise


def load_verified_capture_manifest(path: Path) -> tuple[dict, Path]:
    """Sentetik manifesti ve referans verdiği bütün PNG'leri doğrula."""
    path = Path(path).resolve()
    if not path.is_file():
        raise CaptureError("Capture manifest bulunamadı")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CaptureError("Capture manifest okunamadı") from exc
    if (data.get("schema_version") != 1
            or data.get("kind") != "ui_preview_capture"
            or data.get("synthetic_only") is not True):
        raise CaptureError("Yalnız sentetik UI Preview capture manifesti karşılaştırılabilir")
    _validate_label(str(data.get("label", "")))
    captures = data.get("captures")
    if not isinstance(captures, list) or not captures:
        raise CaptureError("Capture manifest boş")
    if data.get("capture_count") != len(captures):
        raise CaptureError("Capture sayısı manifest ile uyuşmuyor")
    if any(not isinstance(item, dict) for item in captures):
        raise CaptureError("Capture girdisi geçersiz")
    scenario_ids = [item.get("scenario_id") for item in captures]
    if any(not isinstance(value, str) or not value for value in scenario_ids):
        raise CaptureError("Capture senaryo kimliği geçersiz")
    if len(scenario_ids) != len(set(scenario_ids)):
        raise CaptureError("Capture senaryo kimlikleri benzersiz olmalı")
    for item in captures:
        _verified_image(path.parent, item)
    return data, path.parent


def _verified_image(root: Path, item: dict) -> Path:
    relative = Path(str(item.get("file", "")))
    if relative.is_absolute() or ".." in relative.parts:
        raise CaptureError("Capture görsel yolu manifest dışına çıkıyor")
    path = (root / relative).resolve()
    try:
        path.relative_to(root.resolve())
    except ValueError as exc:
        raise CaptureError("Capture görsel yolu manifest dışına çıkıyor") from exc
    if not path.is_file() or _sha256(path) != item.get("sha256"):
        raise CaptureError("Capture PNG bütünlüğü doğrulanamadı")
    try:
        with Image.open(path) as image:
            if image.size != (item.get("width"), item.get("height")):
                raise CaptureError("Capture PNG boyutu manifest ile uyuşmuyor")
    except OSError as exc:
        raise CaptureError("Capture PNG okunamadı") from exc
    return path


def _pad(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    canvas = Image.new("RGBA", size, (255, 255, 255, 0))
    canvas.alpha_composite(image.convert("RGBA"), (0, 0))
    return canvas


def _comparison_index(manifest: dict) -> str:
    rows = []
    for item in manifest["comparisons"]:
        rows.append(
            f'<article><h2>{html.escape(item["scenario_id"])}</h2>'
            f'<p>Değişen piksel: {item["changed_pixels"]}</p>'
            f'<img src="{html.escape(item["side_by_side_file"])}" alt="before after diff"></article>'
        )
    return """<!doctype html><html lang="tr"><meta charset="utf-8">
<title>OMS UI Preview Karşılaştırma</title><style>
body{font-family:Segoe UI,sans-serif;margin:24px;background:#eef1f6;color:#172033}
article{background:white;border:1px solid #ccd3df;border-radius:10px;padding:14px;margin:16px 0;overflow:auto}
img{max-width:100%;height:auto;border:1px solid #d5dae3}h1,h2{margin-top:0}
</style><body><h1>Before / After / Diff</h1>""" + "".join(rows) + "</body></html>"


def compare_captures(before_manifest: Path, after_manifest: Path, output: Path) -> dict[str, Any]:
    """Uyumlu iki sentetik capture setinden görsel fark raporu üret."""
    before, before_root = load_verified_capture_manifest(before_manifest)
    after, after_root = load_verified_capture_manifest(after_manifest)
    before_items = {item["scenario_id"]: item for item in before["captures"]}
    after_items = {item["scenario_id"]: item for item in after["captures"]}
    if set(before_items) != set(after_items):
        raise CaptureError("Karşılaştırma için senaryo kümeleri aynı olmalı")

    compatibility = ("scenario_id", "profile", "theme", "viewport", "dpi", "widget_class")
    for scenario_id in before_items:
        left, right = before_items[scenario_id], after_items[scenario_id]
        if any(left.get(key) != right.get(key) for key in compatibility):
            raise CaptureError(f"Uyumsuz capture metadata: {scenario_id}")

    output = Path(output)
    stage, existed_empty = _fresh_stage(output)
    comparisons = []
    try:
        image_dir = stage / "images"
        image_dir.mkdir()
        for scenario_id in sorted(before_items):
            left_item, right_item = before_items[scenario_id], after_items[scenario_id]
            left_path = _verified_image(before_root, left_item)
            right_path = _verified_image(after_root, right_item)
            with Image.open(left_path).convert("RGBA") as left_raw, Image.open(right_path).convert("RGBA") as right_raw:
                size = (max(left_raw.width, right_raw.width), max(left_raw.height, right_raw.height))
                left = _pad(left_raw, size)
                right = _pad(right_raw, size)
                difference = ImageChops.difference(left, right)
                channels = difference.split()
                mask = ImageChops.lighter(
                    ImageChops.lighter(channels[0], channels[1]),
                    ImageChops.lighter(channels[2], channels[3]),
                )
                changed_pixels = sum(1 for value in mask.getdata() if value)
                diff_visual = Image.new("RGBA", size, (255, 255, 255, 255))
                diff_visual.paste((220, 0, 120, 255), mask=mask)
                safe = _safe_name(scenario_id)
                files = {
                    "before_file": Path("images") / f"{safe}__before.png",
                    "after_file": Path("images") / f"{safe}__after.png",
                    "diff_file": Path("images") / f"{safe}__diff.png",
                    "side_by_side_file": Path("images") / f"{safe}__side-by-side.png",
                }
                left.save(stage / files["before_file"], "PNG")
                right.save(stage / files["after_file"], "PNG")
                diff_visual.save(stage / files["diff_file"], "PNG")
                side = Image.new("RGBA", (size[0] * 3, size[1]), (255, 255, 255, 255))
                side.alpha_composite(left, (0, 0))
                side.alpha_composite(right, (size[0], 0))
                side.alpha_composite(diff_visual, (size[0] * 2, 0))
                side.save(stage / files["side_by_side_file"], "PNG")
            comparisons.append({
                "scenario_id": scenario_id,
                "changed_pixels": changed_pixels,
                "before_sha256": left_item["sha256"],
                "after_sha256": right_item["sha256"],
                **{key: value.as_posix() for key, value in files.items()},
            })
        manifest = {
            "schema_version": 1,
            "kind": "ui_preview_comparison",
            "synthetic_only": True,
            "before_label": before["label"],
            "after_label": after["label"],
            "before_source_fingerprint": before.get("source_fingerprint", ""),
            "after_source_fingerprint": after.get("source_fingerprint", ""),
            "comparison_count": len(comparisons),
            "changed_count": sum(item["changed_pixels"] > 0 for item in comparisons),
            "comparisons": comparisons,
        }
        (stage / "comparison_manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (stage / "index.html").write_text(_comparison_index(manifest), encoding="utf-8")
        _publish_stage(stage, output, existed_empty)
        return {
            "compared": len(comparisons),
            "changed": manifest["changed_count"],
            "manifest": "comparison_manifest.json",
        }
    except Exception:
        _discard_stage(stage)
        raise

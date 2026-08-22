"""Gerçek preview widget ağaçları için muhafazakâr geometri denetimi."""

from __future__ import annotations

from typing import Any, Iterable

from ui_preview.capture import _dispose
from ui_preview.registry import ScenarioContext, ScenarioRegistry


def _identity(widget) -> dict[str, str]:
    return {
        "widget_class": f"{type(widget).__module__}.{type(widget).__qualname__}",
        "object_name": widget.objectName() or "",
    }


def _text_overflows(metrics, text: str, available: int) -> bool | None:
    """Taşmayı döndür; font backend sabit-genişlikli bozuksa ``None``."""
    narrow = metrics.horizontalAdvance("iiiiiiii")
    wide = metrics.horizontalAdvance("WWWWWWWW")
    if abs(wide - narrow) < 4:
        return None
    return metrics.horizontalAdvance(text) > available


def analyze_geometry(widget, window, scenario_id: str) -> list[dict[str, Any]]:
    """Sıfır boyutları ve tek satırlık açık metin taşmalarını bildir."""
    from PySide6.QtWidgets import QAbstractButton, QHeaderView, QLabel, QWidget

    findings: list[dict[str, Any]] = []
    candidates = [window, *window.findChildren(QWidget)]
    seen: set[int] = set()
    for item in candidates:
        marker = id(item)
        if marker in seen:
            continue
        seen.add(marker)
        if item is not window and not item.isVisibleTo(window):
            continue
        width, height = item.width(), item.height()
        if width <= 0 or height <= 0:
            if isinstance(item, QHeaderView) or item.objectName().startswith("qt_"):
                continue
            # max=0, uygulamanın bilinçli kapalı/collapsed durumudur (örn. toast).
            # Kullanılabilir alanı olduğu hâlde sıfır kalan widget hatadır.
            if item.maximumWidth() == 0 or item.maximumHeight() == 0:
                continue
            findings.append({
                "scenario_id": scenario_id,
                "severity": "critical",
                "code": "zero_size",
                "width": width,
                "height": height,
                **_identity(item),
            })
            continue

        text = ""
        available = item.contentsRect().width()
        if isinstance(item, QLabel):
            pixmap = item.pixmap()
            if item.wordWrap() or (pixmap is not None and not pixmap.isNull()):
                continue
            text = item.text()
        elif isinstance(item, QAbstractButton):
            text = item.text()
        if not text or "\n" in text or "<" in text:
            continue
        measured_text = text.replace("&&", "\0").replace("&", "").replace("\0", "&")
        metrics = item.fontMetrics()
        overflow = _text_overflows(metrics, measured_text, available)
        if overflow is not True:
            continue
        findings.append({
            "scenario_id": scenario_id,
            "severity": "warning",
            "code": "text_overflow",
            "text_width": metrics.horizontalAdvance(measured_text),
            "available_width": available,
            **_identity(item),
        })
    return findings


def check_scenarios_geometry(
    registry: ScenarioRegistry,
    context: ScenarioContext,
    scenario_ids: Iterable[str],
) -> dict[str, Any]:
    """Senaryoları gerçek widget olarak aç, geometriyi denetle ve kapat."""
    from ui_preview.launcher import apply_theme, create_preview_window, ensure_application
    from PySide6.QtGui import QFontMetrics

    app = ensure_application()
    apply_theme(app, context.theme)
    text_metrics_reliable = (
        _text_overflows(QFontMetrics(app.font()), "ölçüm metni", 10) is not None
    )
    findings: list[dict[str, Any]] = []
    checked = 0
    for scenario_id in scenario_ids:
        scenario = registry.scenario(scenario_id)
        widget, window = create_preview_window(scenario, context)
        try:
            window.show()
            app.processEvents()
            app.processEvents()
            findings.extend(analyze_geometry(widget, window, scenario.id))
            checked += 1
        finally:
            _dispose(app, widget, window)
    return {
        "checked": checked,
        "critical_count": sum(item["severity"] == "critical" for item in findings),
        "warning_count": sum(item["severity"] == "warning" for item in findings),
        "text_metrics_reliable": text_metrics_reliable,
        "findings": findings,
    }

"""Bağımsız UI Preview Launcher ve gerçek-widget açma akışı."""

from __future__ import annotations

import gc
from dataclasses import replace
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QSplitter,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ui_preview.registry import RegistryError, Scenario, ScenarioContext, ScenarioRegistry


def parse_viewport(value: str) -> tuple[int, int]:
    try:
        width, height = (int(part) for part in value.lower().split("x", 1))
    except (TypeError, ValueError) as exc:
        raise RegistryError(f"Geçersiz viewport: {value}") from exc
    if width <= 0 or height <= 0:
        raise RegistryError(f"Geçersiz viewport: {value}")
    return width, height


def apply_theme(app: QApplication, theme: str) -> None:
    from ui.utils.theme_manager import build_stylesheet, get_theme, set_theme_mode

    set_theme_mode(theme)
    app.setStyleSheet(build_stylesheet(get_theme()))


def create_widget(scenario: Scenario, context: ScenarioContext) -> QWidget:
    factory = scenario.resolve_factory()
    scenario_context = replace(
        context,
        scenario_id=scenario.id,
        surface_id=scenario.surface_id,
        state=scenario.state,
    )
    widget = factory(scenario_context)
    if not isinstance(widget, QWidget):
        raise RegistryError(f"Factory QWidget döndürmedi: {scenario.factory}")
    actual = f"{type(widget).__module__}.{type(widget).__qualname__}"
    if actual != scenario.expected_class:
        raise RegistryError(
            f"Factory yanlış üretim sınıfı döndürdü: beklenen={scenario.expected_class} "
            f"gerçek={actual}"
        )
    widget.setProperty("ui_preview_scenario", scenario.id)
    return widget


def create_preview_window(
    scenario: Scenario,
    context: ScenarioContext,
) -> tuple[QWidget, QWidget]:
    """Gerçek widget ve onu gösterecek üst seviye pencereyi döndür."""
    widget = create_widget(scenario, context)
    if scenario.presentation == "standalone":
        window = widget
    else:
        host = QMainWindow()
        host.setWindowTitle(f"UI Preview — {scenario.id}")
        host.setCentralWidget(widget)
        window = host
    width, height = parse_viewport(context.viewport)
    window.resize(width, height)
    return widget, window


class PreviewLauncher(QMainWindow):
    def __init__(
        self,
        registry: ScenarioRegistry,
        base_context: ScenarioContext,
        *,
        theme: str,
        viewport: str,
    ):
        super().__init__()
        self.registry = registry
        self.base_context = base_context
        self._preview_windows: list[QWidget] = []
        self.planned_states_disabled = 0
        self.setWindowTitle("OMS UI Preview Lab")
        self.setMinimumSize(980, 680)
        self.resize(1180, 760)
        self._build_ui(theme, viewport)
        self._populate_tree()

    def _build_ui(self, theme: str, viewport: str) -> None:
        root = QWidget()
        layout = QVBoxLayout(root)

        title = QLabel("UI Preview Lab — entegrasyon öncesi gerçek widget önizlemesi")
        title.setObjectName("section_title")
        layout.addWidget(title)

        controls = QFrame()
        controls.setObjectName("toolbar")
        controls_layout = QHBoxLayout(controls)
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Ekran veya durum ara…")
        self.search_edit.textChanged.connect(self._filter_tree)
        controls_layout.addWidget(self.search_edit, 1)

        controls_layout.addWidget(QLabel("Tema:"))
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(list(self.registry.themes))
        self.theme_combo.setCurrentText(theme)
        self.theme_combo.currentTextChanged.connect(self._theme_changed)
        controls_layout.addWidget(self.theme_combo)

        controls_layout.addWidget(QLabel("Viewport:"))
        self.viewport_combo = QComboBox()
        self.viewport_combo.addItems(list(self.registry.viewport_sizes))
        self.viewport_combo.setCurrentText(viewport)
        controls_layout.addWidget(self.viewport_combo)

        self.dpi_label = QLabel(f"DPI: %{self.base_context.dpi} (process)")
        self.dpi_label.setToolTip("DPI, Qt başlamadan CLI --dpi ile seçilir.")
        controls_layout.addWidget(self.dpi_label)
        layout.addWidget(controls)

        splitter = QSplitter()
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Yüzey / durum", "Durum"])
        self.tree.setColumnWidth(0, 390)
        self.tree.itemSelectionChanged.connect(self._selection_changed)
        self.tree.itemDoubleClicked.connect(lambda *_: self.open_selected())
        splitter.addWidget(self.tree)

        details = QWidget()
        details_layout = QVBoxLayout(details)
        self.detail_title = QLabel("Bir preview senaryosu seçin")
        self.detail_title.setObjectName("section_title")
        details_layout.addWidget(self.detail_title)
        self.detail_text = QLabel(
            "Aşama 3 yalnız çalışan factory'leri açar. Planlanan durumlar "
            "Aşama 4 tamamlanana kadar devre dışıdır."
        )
        self.detail_text.setWordWrap(True)
        details_layout.addWidget(self.detail_text)
        details_layout.addStretch()
        self.open_button = QPushButton("Gerçek Widget'ı Aç")
        self.open_button.setObjectName("primary")
        self.open_button.setEnabled(False)
        self.open_button.clicked.connect(self.open_selected)
        details_layout.addWidget(self.open_button)
        splitter.addWidget(details)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        layout.addWidget(splitter, 1)

        self.status_label = QLabel(
            f"{self.registry.surface_count} yüzey · "
            f"{self.registry.scenario_count} çalışan senaryo · "
            f"profil={self.base_context.profile}"
        )
        self.status_label.setObjectName("hint_label")
        layout.addWidget(self.status_label)
        self.setCentralWidget(root)

    def _populate_tree(self) -> None:
        for surface in self.registry.surfaces:
            top = QTreeWidgetItem([f"{surface['title']}  [{surface['id']}]", ""])
            top.setData(0, Qt.ItemDataRole.UserRole + 1, surface["id"])
            self.tree.addTopLevelItem(top)
            for state in surface["states"]:
                scenario_id = f"{surface['id']}.{state}"
                scenario = self.registry.scenario_or_none(scenario_id)
                child = QTreeWidgetItem([state, "hazır" if scenario else "planlandı"])
                child.setData(0, Qt.ItemDataRole.UserRole, scenario_id if scenario else None)
                if scenario is None:
                    child.setDisabled(True)
                    self.planned_states_disabled += 1
                top.addChild(child)
            top.setExpanded(surface["id"].startswith("component."))

    def _filter_tree(self, text: str) -> None:
        needle = text.strip().casefold()
        for index in range(self.tree.topLevelItemCount()):
            top = self.tree.topLevelItem(index)
            surface_match = needle in top.text(0).casefold()
            child_match = False
            for child_index in range(top.childCount()):
                child = top.child(child_index)
                matches = not needle or surface_match or needle in child.text(0).casefold()
                child.setHidden(not matches)
                child_match = child_match or matches
            top.setHidden(bool(needle) and not surface_match and not child_match)

    def _selected_scenario(self) -> Scenario | None:
        items = self.tree.selectedItems()
        if not items:
            return None
        scenario_id = items[0].data(0, Qt.ItemDataRole.UserRole)
        return self.registry.scenario_or_none(scenario_id) if scenario_id else None

    def _selection_changed(self) -> None:
        scenario = self._selected_scenario()
        self.open_button.setEnabled(scenario is not None)
        if scenario is None:
            self.detail_title.setText("Planlanan yüzey veya durum")
            self.detail_text.setText("Factory henüz uygulanmadı; Aşama 4 kapsamındadır.")
            return
        self.detail_title.setText(scenario.id)
        self.detail_text.setText(
            f"Gerçek sınıf: {scenario.expected_class}\n"
            f"Fixture: {scenario.profile}\nSunum: {scenario.presentation}"
        )

    def _theme_changed(self, theme: str) -> None:
        apply_theme(QApplication.instance(), theme)

    def open_selected(self) -> None:
        scenario = self._selected_scenario()
        if scenario is None:
            return
        theme = self.theme_combo.currentText()
        viewport = self.viewport_combo.currentText()
        context = ScenarioContext(
            sandbox=self.base_context.sandbox,
            manifest=self.base_context.manifest,
            profile=self.base_context.profile,
            theme=theme,
            viewport=viewport,
            dpi=self.base_context.dpi,
        )
        _widget, window = create_preview_window(scenario, context)
        window.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        window.destroyed.connect(lambda *_: self._discard_window(window))
        self._preview_windows.append(window)
        window.show()
        window.raise_()
        window.activateWindow()

    def _discard_window(self, window: QWidget) -> None:
        if window in self._preview_windows:
            self._preview_windows.remove(window)

    def closeEvent(self, event) -> None:
        for window in list(self._preview_windows):
            window.close()
        super().closeEvent(event)


def ensure_application() -> QApplication:
    return QApplication.instance() or QApplication([])


def run_scenario_smoke(
    registry: ScenarioRegistry,
    context: ScenarioContext,
    scenario_id: str,
) -> dict[str, Any]:
    app = ensure_application()
    apply_theme(app, context.theme)
    scenario = registry.scenario(scenario_id)
    widget, window = create_preview_window(scenario, context)
    window.show()
    app.processEvents()
    from ui.utils.theme_manager import get_theme

    actual = f"{type(widget).__module__}.{type(widget).__qualname__}"
    result = {
        "widget_class": actual,
        "resolved_theme": get_theme()["name"],
        "window_size": f"{window.width()}x{window.height()}",
    }
    # QPdfDocument Windows'ta kaynak PDF'yi açık tutar. Widget'ın
    # deleteLater kuyruğunu beklemek yerine smoke temizliğinde belgeyi açıkça
    # kapat; aksi halde sandbox geçici profilini silemez.
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
    del widget, window
    gc.collect()
    return result


def run_surface_smoke(
    registry: ScenarioRegistry,
    context: ScenarioContext,
) -> dict[str, Any]:
    """Her katalog yüzeyinin bir gerçek temsilci senaryosunu aynı sandbox'ta aç."""
    first_by_surface = {}
    for scenario in registry.scenarios:
        first_by_surface.setdefault(scenario.surface_id, scenario)
    failed = []
    smoked = 0
    for surface in registry.surfaces:
        scenario = first_by_surface[surface["id"]]
        try:
            run_scenario_smoke(registry, context, scenario.id)
            smoked += 1
        except Exception as exc:  # toplu smoke hangi yüzeyin kırıldığını raporlar
            failed.append({"scenario": scenario.id, "error": type(exc).__name__})
    return {
        "surface_count": registry.surface_count,
        "smoked": smoked,
        "failed": failed,
    }


def run_all_scenarios_smoke(
    registry: ScenarioRegistry,
    context: ScenarioContext,
) -> dict[str, Any]:
    """Katalogdaki bütün durumları gerçek widget olarak oluştur/kapat."""
    failed = []
    smoked = 0
    for scenario in registry.scenarios:
        try:
            run_scenario_smoke(registry, context, scenario.id)
            smoked += 1
        except Exception as exc:
            failed.append({"scenario": scenario.id, "error": type(exc).__name__})
    return {
        "scenario_count": registry.scenario_count,
        "smoked": smoked,
        "failed": failed,
    }


def run_interactive_scenario(
    registry: ScenarioRegistry,
    context: ScenarioContext,
    scenario_id: str,
) -> int:
    app = ensure_application()
    apply_theme(app, context.theme)
    scenario = registry.scenario(scenario_id)
    widget, window = create_preview_window(scenario, context)
    window.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
    window.show()
    code = app.exec()
    window.close()
    del widget, window
    gc.collect()
    return code


def run_launcher_smoke(
    registry: ScenarioRegistry,
    context: ScenarioContext,
) -> dict[str, Any]:
    app = ensure_application()
    apply_theme(app, context.theme)
    launcher = PreviewLauncher(
        registry, context, theme=context.theme, viewport=context.viewport
    )
    launcher.show()
    app.processEvents()
    initial_stylesheet = app.styleSheet()
    alternate_theme = "dark" if context.theme == "light" else "light"
    launcher.theme_combo.setCurrentText(alternate_theme)
    app.processEvents()
    from ui.utils.theme_manager import get_theme

    result = {
        "surface_count": launcher.tree.topLevelItemCount(),
        "implemented_scenarios": registry.scenario_count,
        "planned_states_disabled": launcher.planned_states_disabled,
        "themes": [launcher.theme_combo.itemText(i) for i in range(launcher.theme_combo.count())],
        "viewports": [
            launcher.viewport_combo.itemText(i)
            for i in range(launcher.viewport_combo.count())
        ],
        "theme_switch_applied": app.styleSheet() != initial_stylesheet,
        "resolved_theme_after_switch": get_theme()["name"],
    }
    launcher.theme_combo.setCurrentText(context.theme)
    launcher.close()
    launcher.deleteLater()
    app.processEvents()
    del launcher
    gc.collect()
    return result


def run_interactive_launcher(
    registry: ScenarioRegistry,
    context: ScenarioContext,
) -> int:
    app = ensure_application()
    apply_theme(app, context.theme)
    launcher = PreviewLauncher(
        registry, context, theme=context.theme, viewport=context.viewport
    )
    launcher.show()
    code = app.exec()
    launcher.close()
    del launcher
    gc.collect()
    return code

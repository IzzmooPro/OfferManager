"""``python -m ui_preview`` bağımsız CLI başlangıcı."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from ui_preview.capture import CaptureError, capture_scenarios, compare_captures
from ui_preview.baseline import accept_baseline, plan_baseline
from ui_preview.registry import RegistryError, ScenarioContext, ScenarioRegistry
from ui_preview.sandbox import PreviewSandbox, SandboxViolation


THEMES = ("light", "dark")
VIEWPORTS = ("1100x700", "1300x800", "1600x900", "1920x1080")
PROFILES = ("empty", "populated", "dense")
DPIS = (100, 125, 150)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="OMS UI Preview Lab")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--list", action="store_true", help="Senaryoları listele")
    mode.add_argument("--check", action="store_true", help="Registry sözleşmesini doğrula")
    mode.add_argument("--launcher", action="store_true", help="Launcher'ı aç (varsayılan)")
    mode.add_argument("--scenario", help="Tek gerçek-widget senaryosunu aç")
    mode.add_argument(
        "--smoke-surfaces", action="store_true",
        help="Her katalog yüzeyinin bir temsilcisini oluştur/kapat",
    )
    mode.add_argument(
        "--smoke-all", action="store_true",
        help="Katalogdaki bütün durumları oluştur/kapat",
    )
    mode.add_argument("--capture", help="Tek senaryoyu PNG olarak yakala")
    mode.add_argument(
        "--capture-surfaces", action="store_true",
        help="Her katalog yüzeyinin bir temsilcisini PNG olarak yakala",
    )
    mode.add_argument(
        "--compare", nargs=2, metavar=("BEFORE_MANIFEST", "AFTER_MANIFEST"),
        help="İki sentetik capture manifestini karşılaştır",
    )
    mode.add_argument(
        "--geometry-surfaces", action="store_true",
        help="Her katalog yüzeyinin temsilcisinde geometri denetimi yap",
    )
    mode.add_argument(
        "--geometry-all", action="store_true",
        help="Bütün preview durumlarında geometri denetimi yap",
    )
    mode.add_argument(
        "--baseline-plan", metavar="CAPTURE_MANIFEST",
        help="Baseline adayını yazmadan doğrula ve onay token'ı üret",
    )
    mode.add_argument(
        "--baseline-accept", metavar="CAPTURE_MANIFEST",
        help="Açık token ile yeni değiştirilemez baseline sürümü oluştur",
    )
    parser.add_argument("--theme", choices=THEMES, default="light")
    parser.add_argument("--viewport", choices=VIEWPORTS, default="1300x800")
    parser.add_argument("--profile", choices=PROFILES, default="populated")
    parser.add_argument("--dpi", choices=DPIS, default=100, type=int)
    parser.add_argument("--smoke", action="store_true", help="Oluştur/kapat ve çık")
    parser.add_argument("--json", action="store_true", help="Makine-okunur çıktı")
    parser.add_argument("--output", help="Yeni/boş capture veya rapor klasörü")
    parser.add_argument("--label", default="capture", help="Capture seti etiketi")
    parser.add_argument("--baseline-root", help="Baseline sürümlerinin kök klasörü")
    parser.add_argument("--approval-token", help="--baseline-plan çıktısındaki tam token")
    return parser


def _emit(data: dict, as_json: bool) -> None:
    if as_json:
        print(json.dumps(data, ensure_ascii=False, sort_keys=True))
        return
    for key, value in data.items():
        print(f"{key}: {value}")


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        registry = ScenarioRegistry.load()
        if args.baseline_plan:
            result = plan_baseline(Path(args.baseline_plan))
            result["ok"] = True
            _emit(result, args.json)
            return 0
        if args.baseline_accept:
            if not args.baseline_root or not args.approval_token:
                raise CaptureError(
                    "--baseline-accept için --baseline-root ve --approval-token zorunludur")
            result = accept_baseline(
                Path(args.baseline_accept), Path(args.baseline_root), args.approval_token)
            result["ok"] = True
            _emit(result, args.json)
            return 0
        if args.compare:
            if not args.output:
                raise CaptureError("--compare için --output zorunludur")
            result = compare_captures(
                Path(args.compare[0]), Path(args.compare[1]), Path(args.output))
            result["ok"] = True
            _emit(result, args.json)
            return 0
        if args.list:
            _emit(registry.summary(), args.json)
            return 0
        if args.check:
            summary = registry.summary()
            summary.update({
                "ok": True,
                "launcher": registry.catalog["infrastructure"]["launcher"],
            })
            _emit(summary, args.json)
            return 0

        # Qt, sandbox'ın dış-etki bloklarını kurarken import edilir. DPI bundan
        # önce süreç ortamına yazılmalıdır; launcher içinden değiştirilemez.
        os.environ["QT_SCALE_FACTOR"] = str(args.dpi / 100)
        os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "1")

        result: dict = {}
        with PreviewSandbox() as sandbox:
            from ui_preview.fixtures import build_fixture_profile

            manifest = build_fixture_profile(sandbox, args.profile)
            # theme_manager import anında kayıtlı modu okur; gerçek sistem
            # temasına/registry'sine düşmeden sentetik seçim hazır olmalıdır.
            (sandbox.paths.data / "theme.txt").write_text(args.theme, encoding="utf-8")
            from ui_preview.launcher import (
                run_interactive_launcher,
                run_interactive_scenario,
                run_all_scenarios_smoke,
                run_launcher_smoke,
                run_scenario_smoke,
                run_surface_smoke,
            )
            from ui_preview.geometry import check_scenarios_geometry

            context = ScenarioContext(
                sandbox=sandbox,
                manifest=manifest,
                profile=args.profile,
                theme=args.theme,
                viewport=args.viewport,
                dpi=args.dpi,
            )
            if args.geometry_surfaces or args.geometry_all:
                if args.geometry_all:
                    scenario_ids = [scenario.id for scenario in registry.scenarios]
                else:
                    first_by_surface = {}
                    for scenario in registry.scenarios:
                        first_by_surface.setdefault(scenario.surface_id, scenario.id)
                    scenario_ids = [first_by_surface[item["id"]] for item in registry.surfaces]
                result = check_scenarios_geometry(registry, context, scenario_ids)
            elif args.capture or args.capture_surfaces:
                if not args.output:
                    raise CaptureError("Capture için --output zorunludur")
                if args.capture:
                    scenario_ids = [args.capture]
                else:
                    first_by_surface = {}
                    for scenario in registry.scenarios:
                        first_by_surface.setdefault(scenario.surface_id, scenario.id)
                    scenario_ids = [first_by_surface[item["id"]] for item in registry.surfaces]
                result = capture_scenarios(
                    registry, context, scenario_ids, Path(args.output), label=args.label)
            elif args.smoke_all:
                result = run_all_scenarios_smoke(registry, context)
            elif args.smoke_surfaces:
                result = run_surface_smoke(registry, context)
            elif args.scenario:
                if args.smoke:
                    result = run_scenario_smoke(registry, context, args.scenario)
                else:
                    result = {
                        "exit_code": run_interactive_scenario(
                            registry, context, args.scenario
                        )
                    }
            elif args.smoke:
                result = run_launcher_smoke(registry, context)
            else:
                return run_interactive_launcher(registry, context)

            result.update({
                "ok": result.get("critical_count", 0) == 0,
                "theme": args.theme,
                "viewport": args.viewport,
                "profile": args.profile,
                "dpi": args.dpi,
                "external_effects": list(sandbox.audit.events),
                "real_credential_accesses": sandbox.audit.real_credential_accesses,
            })
        _emit(result, args.json)
        return 3 if result.get("critical_count", 0) else 0
    except (CaptureError, RegistryError, SandboxViolation, ValueError) as exc:
        print(f"UI Preview hatası: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

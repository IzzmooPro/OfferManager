"""Validate the local Claude agent pack without changing project state."""
from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CLAUDE_DIR = ROOT / ".claude"
SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
REMOVED_LEGACY = (
    "GITHUB_IS_AKISI_LOCAL.md",
    "docs/README.md",
    "docs/ROADMAP.md",
    "docs/PROJE_GECMISI.md",
    "docs/YOL_HARITASI_KAR_ANALIZI.md",
)
LOCAL_ONLY_AGENT_PATHS = (
    ".claude/settings.local.json",
    ".claude/worktrees/",
)


def frontmatter(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return {}
    try:
        raw = text.split("---", 2)[1]
    except IndexError:
        return {}
    result: dict[str, str] = {}
    for line in raw.splitlines():
        if ":" not in line or line[:1].isspace():
            continue
        key, value = line.split(":", 1)
        result[key.strip()] = value.strip().strip('"\'')
    return result


def validate(root: Path = ROOT) -> list[str]:
    claude_dir = root / ".claude"
    errors: list[str] = []

    required = (
        root / "CLAUDE.md",
        root / "PROJECT_GUIDE" / "INDEX.md",
        claude_dir / "CLAUDE.md",
        claude_dir / "scripts" / "offer_state.py",
        claude_dir / "rules" / "security-privacy.md",
        claude_dir / "skills" / "offer-verify" / "SKILL.md",
    )
    for path in required:
        if not path.is_file():
            errors.append(f"required file missing: {path.relative_to(root)}")

    gitignore = root / ".gitignore"
    if gitignore.is_file():
        ignore_lines = {
            line.strip() for line in gitignore.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        }
        if ".claude/" in ignore_lines:
            errors.append("shared agent pack is still ignored as a whole")
        for relative in LOCAL_ONLY_AGENT_PATHS:
            if relative not in ignore_lines:
                errors.append(f"local agent state is not ignored: {relative}")
    else:
        errors.append(".gitignore missing")

    skill_files = sorted((claude_dir / "skills").glob("*/SKILL.md"))
    if not skill_files:
        errors.append("no skills found")
    for path in skill_files:
        meta = frontmatter(path)
        name = meta.get("name", "")
        description = meta.get("description", "")
        if not SLUG.fullmatch(name):
            errors.append(f"invalid skill name: {path.parent.name}")
        if name != path.parent.name:
            errors.append(f"skill name/folder mismatch: {path.parent.name}")
        if not description:
            errors.append(f"skill description missing: {path.parent.name}")
        body = path.read_text(encoding="utf-8")
        if "PROJECT_GUIDE/INDEX.md" not in body:
            errors.append(f"canonical router missing: {path.parent.name}")

    for path in sorted(claude_dir.rglob("*.md")):
        text = path.read_text(encoding="utf-8")
        for legacy in REMOVED_LEGACY:
            if legacy in text:
                errors.append(
                    f"removed legacy reference: {path.relative_to(root)} -> {legacy}")

    public_text_files = list(claude_dir.rglob("*.md")) + \
        list((claude_dir / "scripts").glob("*.py")) + \
        list((claude_dir / "tests").glob("*.py"))
    absolute_user_path = re.compile(r"(?i)\b[a-z]:[\\/]users[\\/]")
    for path in public_text_files:
        if absolute_user_path.search(path.read_text(encoding="utf-8")):
            errors.append(f"absolute user path in shared file: {path.relative_to(root)}")

    release = claude_dir / "skills" / "offer-release" / "SKILL.md"
    if release.is_file():
        text = release.read_text(encoding="utf-8")
        for required_text in (
                "verify_project_guide.py --release",
                "RELEASE_CHECKLIST.md",
                "VERIFICATION_GUIDE.md",
                "Commit, push, tag, draft",
        ):
            if required_text not in text:
                errors.append(f"release gate missing: {required_text}")

    local_router = claude_dir / "CLAUDE.md"
    if local_router.is_file():
        text = local_router.read_text(encoding="utf-8")
        if "PROJECT_GUIDE/INDEX.md" not in text or "kökteki `CLAUDE.md`" not in text:
            errors.append("local CLAUDE router does not defer to canonical guide")
        if len(text.splitlines()) > 20:
            errors.append("local CLAUDE router repeats too much project policy")

    return errors


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure:
            reconfigure(encoding="utf-8", errors="replace")
    errors = validate()
    if errors:
        print("AGENT_PACK: FAIL")
        for error in errors:
            print(f"  ERROR {error}")
        return 1
    skill_count = len(list((CLAUDE_DIR / "skills").glob("*/SKILL.md")))
    rule_count = len(list((CLAUDE_DIR / "rules").glob("*.md")))
    print(f"AGENT_PACK: PASS skills={skill_count} rules={rule_count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

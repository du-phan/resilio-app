"""Mechanical repository architecture and documentation guardrails."""

from __future__ import annotations

import ast
import filecmp
import re
import warnings
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PACKAGE_ROOT = REPO_ROOT / "resilio"

HARD_LINE_LIMIT = 1_500
WARNING_LINE_LIMIT = 800
OVERSIZED_ALLOWLIST = {
    "resilio/api/plan.py": (
        2_948,
        "docs/issues/split-oversized-plan-modules.md",
    ),
    "resilio/core/plan.py": (
        2_630,
        "docs/issues/split-oversized-plan-modules.md",
    ),
    "resilio/cli/commands/plan.py": (
        2_036,
        "docs/issues/split-oversized-plan-modules.md",
    ),
}

DEPENDENCY_DEBT: dict[tuple[str, str], str] = {}


def _python_modules() -> list[Path]:
    return sorted(PACKAGE_ROOT.rglob("*.py"))


def _module_name(path: Path) -> str:
    relative = path.relative_to(REPO_ROOT).with_suffix("")
    return ".".join(relative.parts)


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(), filename=str(path))
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)
    return imports


def test_module_size_budget_has_shrinking_explicit_allowlist():
    failures: list[str] = []
    warned: list[str] = []

    for path in _python_modules():
        relative = path.relative_to(REPO_ROOT).as_posix()
        line_count = len(path.read_text().splitlines())

        if line_count > HARD_LINE_LIMIT:
            debt = OVERSIZED_ALLOWLIST.get(relative)
            if debt is None:
                failures.append(
                    f"{relative} has {line_count} lines (> {HARD_LINE_LIMIT}); "
                    "split responsibilities or add a reviewed debt issue"
                )
                continue
            baseline, issue = debt
            if not (REPO_ROOT / issue).is_file():
                failures.append(f"{relative}: declared debt issue is missing: {issue}")
            if line_count > baseline:
                failures.append(
                    f"{relative} grew from allowlisted {baseline} to {line_count} lines; "
                    "move new behavior to a focused module"
                )
        elif relative in OVERSIZED_ALLOWLIST:
            failures.append(
                f"{relative} is now {line_count} lines; remove its stale hard-limit allowlist entry"
            )
        elif line_count > WARNING_LINE_LIMIT:
            warned.append(f"{relative} has {line_count} lines")

    if warned:
        warnings.warn(
            "Module-size warning (>800 lines): " + "; ".join(warned),
            stacklevel=1,
        )
    assert not failures, "\n".join(failures)


def test_dependency_direction():
    failures: list[str] = []

    for path in _python_modules():
        source = _module_name(path)
        source_layer = source.split(".")[1] if "." in source else ""
        for imported in _imports(path):
            edge = (source, imported)
            if edge in DEPENDENCY_DEBT:
                assert (REPO_ROOT / DEPENDENCY_DEBT[edge]).is_file()
                continue

            if source_layer == "schemas" and imported.startswith(
                ("resilio.core", "resilio.integrations", "resilio.api", "resilio.cli")
            ):
                failures.append(
                    f"{source} imports {imported}: schemas may import no transport, "
                    "repository, core, API, or CLI layer"
                )
            if source_layer == "integrations" and imported.startswith(
                ("resilio.api", "resilio.cli")
            ):
                failures.append(
                    f"{source} imports {imported}: integrations may not depend on API/CLI"
                )
            if source_layer == "core" and imported.startswith(("resilio.api", "resilio.cli")):
                failures.append(
                    f"{source} imports {imported}: move presentation calls behind a core protocol"
                )
            if source_layer == "api" and imported.startswith("resilio.cli"):
                failures.append(f"{source} imports {imported}: API may not depend on CLI")

    assert not failures, "\n".join(failures)


def test_transport_dtos_do_not_leak_into_domain_consumers():
    consumers = {
        PACKAGE_ROOT / "core" / "load.py",
        PACKAGE_ROOT / "core" / "metrics.py",
        PACKAGE_ROOT / "core" / "profile.py",
        PACKAGE_ROOT / "api" / "profile.py",
        PACKAGE_ROOT / "api" / "coach.py",
        PACKAGE_ROOT / "core" / "plan.py",
        PACKAGE_ROOT / "api" / "plan.py",
    }
    failures = [
        f"{path.relative_to(REPO_ROOT)} imports an external transport DTO"
        for path in consumers
        if path.exists()
        and any(
            imported.startswith("resilio.integrations.intervals_icu.dto")
            for imported in _imports(path)
        )
    ]
    assert not failures, "\n".join(failures)


def test_skill_mirror_matches_authoritative_tree():
    authoritative = REPO_ROOT / ".agents" / "skills"
    mirror = REPO_ROOT / ".claude" / "skills"
    comparison = filecmp.dircmp(authoritative, mirror)

    failures: list[str] = []

    def collect(diff: filecmp.dircmp, prefix: str = "") -> None:
        failures.extend(f"{prefix}{name}: only in .agents" for name in diff.left_only)
        failures.extend(f"{prefix}{name}: only in .claude" for name in diff.right_only)
        failures.extend(f"{prefix}{name}: content differs" for name in diff.diff_files)
        failures.extend(f"{prefix}{name}: unreadable comparison" for name in diff.funny_files)
        for name, child in diff.subdirs.items():
            collect(child, f"{prefix}{name}/")

    collect(comparison)
    assert not failures, (
        ".agents/skills is authoritative; mechanically mirror changed files:\n"
        + "\n".join(failures)
    )


def test_weekly_plan_skill_uses_typed_structured_workouts():
    skill_root = REPO_ROOT / ".agents" / "skills" / "weekly-plan-generate"
    files = [skill_root / "SKILL.md", *sorted((skill_root / "references").glob("*.md"))]
    content = "\n".join(path.read_text() for path in files)

    assert '"structured_workout"' in content, (
        "weekly-plan-generate must teach the typed structured_workout contract"
    )
    assert '"intervals": [' not in content, (
        "weekly-plan-generate still teaches the removed untyped intervals key; "
        "express quality work as recursive structured_workout steps"
    )


def test_documentation_authority_and_current_reference_links_exist():
    index = (REPO_ROOT / "docs/index.md").read_text()
    required = [
        "AGENTS.md",
        "guides/development/agent-workflow.md",
        "reference/architecture-map.md",
        "reference/intervals-icu-integration.md",
    ]
    missing = [value for value in required if value not in index]
    assert not missing, f"docs/index.md is missing authority/navigation links: {missing}"

    for relative in [
        "AGENTS.md",
        "docs/guides/development/agent-workflow.md",
        "docs/reference/architecture-map.md",
        "docs/reference/intervals-icu-integration.md",
    ]:
        assert (REPO_ROOT / relative).is_file(), f"Required documentation missing: {relative}"


def test_activity_mutation_services_remain_focused_and_share_lock_boundary():
    sync_service = PACKAGE_ROOT / "core/activity_sync/service.py"
    backfill_service = (
        PACKAGE_ROOT / "core/historical_activity_backfill/service.py"
    )
    transaction = PACKAGE_ROOT / "core/activity_transaction.py"
    sync_source = sync_service.read_text()
    backfill_source = backfill_service.read_text()

    assert len(sync_source.splitlines()) < WARNING_LINE_LIMIT
    assert len(backfill_source.splitlines()) < WARNING_LINE_LIMIT
    assert "ACTIVITY_MUTATION_LOCK_PATH" in sync_source
    assert "ACTIVITY_MUTATION_LOCK_PATH" in backfill_source
    assert "commit_activity_mutation" in transaction.read_text()


def test_active_markdown_links_resolve():
    """Check every repository-owned Markdown document."""
    documents = [
        *sorted((REPO_ROOT / "docs").rglob("*.md")),
        REPO_ROOT / "README.md",
        REPO_ROOT / "AGENTS.md",
        REPO_ROOT / "CLAUDE.md",
    ]
    link_pattern = re.compile(r"(?<!!)\[[^\]]+\]\(([^)]+)\)")
    failures: list[str] = []
    for document in documents:
        relative = document.relative_to(REPO_ROOT).as_posix()
        for raw_target in link_pattern.findall(document.read_text()):
            target = (
                raw_target.strip()
                .split()[0]
                .strip("<>")
                .split("#", 1)[0]
            )
            if (
                not target
                or "://" in target
                or target.startswith(("mailto:", "/"))
            ):
                continue
            if not (document.parent / target).resolve().exists():
                failures.append(f"{relative}: broken relative link {raw_target!r}")
    assert not failures, "\n".join(failures)


def test_obsolete_provider_term_is_absent_from_active_repository_files():
    forbidden = ("stra" + "va").casefold()
    text_suffixes = {
        "",
        ".csv",
        ".json",
        ".md",
        ".py",
        ".toml",
        ".txt",
        ".yaml",
        ".yml",
    }
    failures: list[str] = []
    for path in sorted(REPO_ROOT.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(REPO_ROOT).as_posix()
        if (
            relative.startswith((".git/", "data/"))
            or "/__pycache__/" in relative
            or relative == ".env.local"
            or path.suffix.casefold() not in text_suffixes
        ):
            continue
        if forbidden in relative.casefold():
            failures.append(f"{relative}: obsolete provider term in path")
            continue
        try:
            content = path.read_text()
        except UnicodeDecodeError:
            continue
        if forbidden in content.casefold():
            failures.append(f"{relative}: obsolete provider term in content")
    assert not failures, (
        "Remove obsolete provider vocabulary or add only an explicitly "
        "classified migration/spec exception:\n" + "\n".join(failures)
    )


def test_obsolete_provider_term_is_absent_from_active_local_state():
    """Audit ignored active state without reading credentials or backups."""
    forbidden = ("stra" + "va").casefold()
    roots = [
        REPO_ROOT / "data/activities",
        REPO_ROOT / "data/athlete",
        REPO_ROOT / "data/state",
        REPO_ROOT / "data/plans",
    ]
    failures: list[str] = []
    for root in roots:
        if not root.exists():
            continue
        for path in sorted(root.rglob("*")):
            if not path.is_file():
                continue
            try:
                content = path.read_text()
            except UnicodeDecodeError:
                continue
            if forbidden in content.casefold():
                failures.append(path.relative_to(REPO_ROOT).as_posix())
    assert not failures, (
        "Remove obsolete provider vocabulary from active ignored state; "
        "recovery copies belong only under data/backups:\n"
        + "\n".join(failures)
    )

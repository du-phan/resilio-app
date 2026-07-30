"""Mechanical repository architecture and documentation guardrails."""

from __future__ import annotations

import ast
import filecmp
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PACKAGE_ROOT = REPO_ROOT / "resilio"

MODULE_LINE_LIMIT = 600
FUNCTION_LINE_LIMIT = 120

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


def test_module_size_budget():
    failures: list[str] = []

    for path in _python_modules():
        relative = path.relative_to(REPO_ROOT).as_posix()
        line_count = len(path.read_text().splitlines())
        if line_count > MODULE_LINE_LIMIT:
            failures.append(
                f"{relative} has {line_count} lines (> {MODULE_LINE_LIMIT}); "
                "split it into responsibility-specific modules"
            )
    assert not failures, "\n".join(failures)


def test_function_size_budget():
    failures: list[str] = []
    for path in _python_modules():
        relative = path.relative_to(REPO_ROOT).as_posix()
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            assert node.end_lineno is not None
            line_count = node.end_lineno - node.lineno + 1
            if line_count > FUNCTION_LINE_LIMIT:
                failures.append(
                    f"{relative}:{node.lineno} {node.name} has {line_count} lines "
                    f"(> {FUNCTION_LINE_LIMIT}); extract cohesive phases"
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
        PACKAGE_ROOT / "core" / "coaching_context" / "service.py",
        PACKAGE_ROOT / "core" / "profile" / "candidates.py",
        PACKAGE_ROOT / "core" / "planning" / "service.py",
        PACKAGE_ROOT / "api" / "profile.py",
        PACKAGE_ROOT / "api" / "coaching_context.py",
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

    assert (
        '"structured_workout"' in content
    ), "weekly-plan-generate must teach the typed structured_workout contract"
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


def test_training_book_records_are_source_only_not_agent_procedures():
    failures: list[str] = []
    forbidden_procedure_markers = (
        "## hard constraints",
        "if/then",
        "data the ai coach",
        "you must collect",
        "workout generation template",
    )
    for path in sorted((REPO_ROOT / "docs/training_books").glob("*.md")):
        content = path.read_text()
        normalized = content.casefold()
        if "operational_authority: false" not in normalized:
            failures.append(f"{path.name}: missing operational_authority: false")
        if "verification_scope: conceptual_summary_only" not in normalized:
            failures.append(f"{path.name}: missing conceptual-only verification scope")
        for marker in forbidden_procedure_markers:
            if marker in normalized:
                failures.append(f"{path.name}: executable procedure marker {marker!r}")
    assert not failures, "\n".join(failures)


def test_activity_mutation_services_remain_focused_and_share_lock_boundary():
    sync_service = PACKAGE_ROOT / "core/activity_sync/service.py"
    transaction = PACKAGE_ROOT / "core/activity_transaction.py"
    sync_source = sync_service.read_text()

    assert len(sync_source.splitlines()) <= MODULE_LINE_LIMIT
    assert "ACTIVITY_MUTATION_LOCK_PATH" in sync_source
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
            target = raw_target.strip().split()[0].strip("<>").split("#", 1)[0]
            if not target or "://" in target or target.startswith(("mailto:", "/")):
                continue
            if not (document.parent / target).resolve().exists():
                failures.append(f"{relative}: broken relative link {raw_target!r}")
    assert not failures, "\n".join(failures)


def test_retired_local_derivation_surfaces_are_absent():
    retired_paths = [
        "resilio/core/load.py",
        "resilio/core/metrics.py",
        "resilio/core/readiness.py",
        "resilio/core/risk.py",
        "resilio/core/adaptation.py",
        "resilio/core/guardrails.py",
        "resilio/core/enrichment.py",
        "resilio/schemas/common.py",
        "resilio/init.py",
    ]
    present = [relative for relative in retired_paths if (REPO_ROOT / relative).exists()]
    assert not present, f"Retired local derivation surfaces remain: {present}"

    settings_text = (REPO_ROOT / "templates/settings.yaml").read_text()
    retired_settings = [
        key
        for key in (
            "metrics_dir",
            "training_defaults",
            "ctl_time_constant",
            "atl_time_constant",
            "acwr_acute_window",
            "metrics_stale_hours",
        )
        if key in settings_text
    ]
    assert not retired_settings, f"Retired local derivation settings remain: {retired_settings}"

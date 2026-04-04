"""Repair Engine -- Detects and fixes common issues in generated projects.

Scans a NexusForge project for structural problems such as missing
``__init__.py`` files, broken imports, unsatisfied module dependencies,
missing env vars, empty files, SQL syntax issues, and missing
``requirements.txt`` entries.  Each problem is represented as a
:class:`RepairIssue` and can optionally be auto-fixed.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Any

import yaml

from core.compatibility import COMPATIBILITY_MATRIX, get_missing_dependencies


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class RepairIssue:
    """A single issue detected in a project.

    Attributes:
        id: Machine-readable identifier (e.g. ``"missing_init_py_1"``).
        severity: One of ``"critical"``, ``"warning"``, ``"info"``.
        category: One of ``"structure"``, ``"imports"``, ``"dependencies"``,
            ``"env"``, ``"migrations"``, ``"tests"``.
        file_path: Relative path of the affected file (or directory).
        description: Human-readable description of the problem.
        fix_description: Human-readable description of the proposed fix.
        auto_fixable: Whether the engine can fix this automatically.
    """

    id: str
    severity: str
    category: str
    file_path: str
    description: str
    fix_description: str
    auto_fixable: bool


@dataclass
class RepairResult:
    """Result of applying a single fix.

    Attributes:
        issue_id: The :attr:`RepairIssue.id` that was addressed.
        applied: Whether the fix was actually applied.
        detail: Human-readable summary of what was done.
    """

    issue_id: str
    applied: bool
    detail: str


@dataclass
class RepairReport:
    """Aggregated report for a full project scan + optional repair.

    Attributes:
        project_path: Absolute path of the scanned project.
        issues: All issues detected.
        fixes: Fixes that were applied (empty for report-only mode).
        summary: Counts by severity level.
    """

    project_path: str
    issues: list[RepairIssue] = field(default_factory=list)
    fixes: list[RepairResult] = field(default_factory=list)
    summary: dict[str, int] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _load_manifest(project_path: str) -> dict[str, Any] | None:
    """Try to load and return the project manifest, or ``None``."""
    manifest_path = os.path.join(project_path, "project_manifest.yaml")
    if not os.path.isfile(manifest_path):
        return None
    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    except Exception:
        return None


def _get_installed_module_ids(manifest: dict[str, Any] | None) -> list[str]:
    """Extract module IDs from a manifest dict."""
    if manifest is None:
        return []
    return [m.get("id", "") for m in manifest.get("modules", []) if m.get("id")]


def _read_file_safe(path: str) -> str | None:
    """Read a file and return its contents, or ``None`` on error."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return None


def _write_file_safe(path: str, content: str) -> bool:
    """Write *content* to *path*, creating parent dirs if needed.

    Returns:
        True on success, False on failure.
    """
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Individual scanners
# ---------------------------------------------------------------------------

_ISSUE_COUNTER = 0


def _next_id(prefix: str) -> str:
    """Return a unique issue ID like ``"missing_init_py_1"``."""
    global _ISSUE_COUNTER
    _ISSUE_COUNTER += 1
    return f"{prefix}_{_ISSUE_COUNTER}"


def _scan_missing_init_py(project_path: str) -> list[RepairIssue]:
    """Detect Python package directories without ``__init__.py``."""
    issues: list[RepairIssue] = []

    for root, dirs, files in os.walk(project_path):
        dirs[:] = [d for d in dirs if not d.startswith(".") and d not in ("node_modules", "__pycache__", ".venv", "venv")]

        # Only flag dirs that contain at least one .py file
        py_files = [f for f in files if f.endswith(".py")]
        if py_files and "__init__.py" not in files:
            rel = os.path.relpath(root, project_path)
            issues.append(RepairIssue(
                id=_next_id("missing_init_py"),
                severity="warning",
                category="structure",
                file_path=rel,
                description=f"Directory '{rel}' contains .py files but no __init__.py",
                fix_description=f"Create empty __init__.py in '{rel}'",
                auto_fixable=True,
            ))

    return issues


def _scan_missing_imports_in_main(
    project_path: str,
    module_ids: list[str],
) -> list[RepairIssue]:
    """Detect installed modules whose routers are not imported in ``main.py``."""
    issues: list[RepairIssue] = []
    main_py = os.path.join(project_path, "main.py")
    content = _read_file_safe(main_py)
    if content is None:
        return issues

    for mod_id in module_ids:
        # Check for either import style
        if f"{mod_id}_router" not in content and f"from src.{mod_id}" not in content:
            # Only flag if the module directory exists
            mod_dir = os.path.join(project_path, "src", mod_id)
            if os.path.isdir(mod_dir):
                issues.append(RepairIssue(
                    id=_next_id("missing_import"),
                    severity="critical",
                    category="imports",
                    file_path="main.py",
                    description=f"Module '{mod_id}' is installed but not imported in main.py",
                    fix_description=f"Add 'from src.{mod_id}.router import router as {mod_id}_router' to main.py",
                    auto_fixable=True,
                ))

    return issues


def _scan_broken_dependencies(module_ids: list[str]) -> list[RepairIssue]:
    """Detect modules whose required dependencies are not installed."""
    issues: list[RepairIssue] = []
    missing = get_missing_dependencies(module_ids)

    for dep in missing:
        # Find which module needs it
        needed_by: list[str] = []
        for mod_id in module_ids:
            entry = COMPATIBILITY_MATRIX.get(mod_id)
            if entry and dep in entry["requires"]:
                needed_by.append(mod_id)

        issues.append(RepairIssue(
            id=_next_id("broken_dep"),
            severity="critical",
            category="dependencies",
            file_path="project_manifest.yaml",
            description=f"Module dependency '{dep}' is required by {needed_by} but not installed",
            fix_description=f"Add module '{dep}' to the project",
            auto_fixable=False,
        ))

    return issues


def _scan_missing_env_vars(
    project_path: str,
    module_ids: list[str],
) -> list[RepairIssue]:
    """Detect env vars required by modules but missing from ``.env.example``."""
    issues: list[RepairIssue] = []
    env_path = os.path.join(project_path, ".env.example")
    content = _read_file_safe(env_path)

    defined_vars: set[str] = set()
    if content:
        for line in content.splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                defined_vars.add(line.split("=", 1)[0].strip())

    for mod_id in module_ids:
        entry = COMPATIBILITY_MATRIX.get(mod_id)
        if entry is None:
            continue
        for var in entry["env_vars"]:
            if var not in defined_vars:
                issues.append(RepairIssue(
                    id=_next_id("missing_env"),
                    severity="warning",
                    category="env",
                    file_path=".env.example",
                    description=f"Env var '{var}' required by module '{mod_id}' is not in .env.example",
                    fix_description=f"Add '{var}=' to .env.example",
                    auto_fixable=True,
                ))

    return issues


def _scan_empty_files(project_path: str) -> list[RepairIssue]:
    """Detect non-trivial files that are 0 bytes (corrupt/empty)."""
    issues: list[RepairIssue] = []
    allowed_empty = {"__init__.py", ".gitkeep", ".keep"}

    for root, dirs, files in os.walk(project_path):
        dirs[:] = [d for d in dirs if not d.startswith(".") and d not in ("node_modules", "__pycache__", ".venv", "venv")]

        for filename in files:
            if filename in allowed_empty:
                continue
            full = os.path.join(root, filename)
            try:
                if os.path.getsize(full) == 0:
                    rel = os.path.relpath(full, project_path)
                    issues.append(RepairIssue(
                        id=_next_id("empty_file"),
                        severity="warning",
                        category="structure",
                        file_path=rel,
                        description=f"File '{rel}' is 0 bytes (empty or corrupt)",
                        fix_description=f"Add placeholder content to '{rel}'",
                        auto_fixable=True,
                    ))
            except OSError:
                pass

    return issues


def _scan_sql_migrations(project_path: str) -> list[RepairIssue]:
    """Basic validation of SQL migration files."""
    issues: list[RepairIssue] = []
    migrations_dir = os.path.join(project_path, "src", "db", "migrations")

    if not os.path.isdir(migrations_dir):
        return issues

    # Simple SQL syntax patterns that indicate problems
    bad_patterns = [
        (r"CREATE\s+TABLE\s+\(", "CREATE TABLE missing table name"),
        (r"ALTER\s+TABLE\s+\(", "ALTER TABLE missing table name"),
        (r"INSERT\s+INTO\s+\(", "INSERT INTO missing table name"),
        (r";;", "Double semicolon (likely typo)"),
    ]

    for filename in os.listdir(migrations_dir):
        if not filename.endswith(".sql"):
            continue
        full = os.path.join(migrations_dir, filename)
        content = _read_file_safe(full)
        if content is None:
            continue

        for pattern, msg in bad_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                rel = os.path.relpath(full, project_path)
                issues.append(RepairIssue(
                    id=_next_id("sql_syntax"),
                    severity="warning",
                    category="migrations",
                    file_path=rel,
                    description=f"SQL migration '{rel}' may have syntax issue: {msg}",
                    fix_description=f"Review and fix SQL syntax in '{rel}'",
                    auto_fixable=False,
                ))

    return issues


def _scan_missing_requirements(
    project_path: str,
    module_ids: list[str],
) -> list[RepairIssue]:
    """Detect Python packages from modules missing in ``requirements.txt``."""
    issues: list[RepairIssue] = []
    req_path = os.path.join(project_path, "requirements.txt")
    content = _read_file_safe(req_path)

    if content is None:
        # No requirements.txt at all -- quality_gate already flags this
        return issues

    # Parse installed package names (strip versions)
    installed: set[str] = set()
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("-"):
            continue
        pkg_name = re.split(r"[>=<!\[]", line)[0].strip().lower()
        if pkg_name:
            installed.add(pkg_name)

    for mod_id in module_ids:
        entry = COMPATIBILITY_MATRIX.get(mod_id)
        if entry is None:
            continue
        for pkg_spec in entry["python_packages"]:
            pkg_name = re.split(r"[>=<!\[]", pkg_spec)[0].strip().lower()
            if pkg_name not in installed:
                issues.append(RepairIssue(
                    id=_next_id("missing_req"),
                    severity="warning",
                    category="dependencies",
                    file_path="requirements.txt",
                    description=f"Package '{pkg_spec}' required by module '{mod_id}' is not in requirements.txt",
                    fix_description=f"Add '{pkg_spec}' to requirements.txt",
                    auto_fixable=True,
                ))

    return issues


# ---------------------------------------------------------------------------
# Fix appliers
# ---------------------------------------------------------------------------

def _fix_missing_init_py(project_path: str, issue: RepairIssue) -> RepairResult:
    """Create an empty ``__init__.py``."""
    target = os.path.join(project_path, issue.file_path, "__init__.py")
    ok = _write_file_safe(target, "")
    return RepairResult(
        issue_id=issue.id,
        applied=ok,
        detail=f"Created {os.path.relpath(target, project_path)}" if ok else "Failed to create __init__.py",
    )


def _fix_missing_import(project_path: str, issue: RepairIssue) -> RepairResult:
    """Add a missing router import to ``main.py``."""
    main_py = os.path.join(project_path, "main.py")
    content = _read_file_safe(main_py)
    if content is None:
        return RepairResult(issue_id=issue.id, applied=False, detail="main.py not readable")

    # Extract module id from fix_description
    match = re.search(r"from src\.(\w+)\.router", issue.fix_description)
    if not match:
        return RepairResult(issue_id=issue.id, applied=False, detail="Could not parse module id")

    mod_id = match.group(1)
    import_line = f"from src.{mod_id}.router import router as {mod_id}_router"
    include_line = f'app.include_router({mod_id}_router, prefix="/api/{mod_id}", tags=["{mod_id}"])'

    lines = content.split("\n")

    # Add import after last import
    last_import_idx = 0
    for i, line in enumerate(lines):
        if line.startswith(("import ", "from ")):
            last_import_idx = i
    if import_line not in content:
        lines.insert(last_import_idx + 1, import_line)

    # Add include_router before first @app route or at end
    if include_line not in content:
        insert_idx = len(lines)
        for i, line in enumerate(lines):
            if line.strip().startswith("@app."):
                insert_idx = i
                break
        lines.insert(insert_idx, include_line)

    ok = _write_file_safe(main_py, "\n".join(lines))
    return RepairResult(
        issue_id=issue.id,
        applied=ok,
        detail=f"Added import and include_router for '{mod_id}' in main.py" if ok else "Failed to update main.py",
    )


def _fix_missing_env_var(project_path: str, issue: RepairIssue) -> RepairResult:
    """Append a missing env var to ``.env.example``."""
    env_path = os.path.join(project_path, ".env.example")
    match = re.search(r"'(\w+)='", issue.fix_description)
    if not match:
        return RepairResult(issue_id=issue.id, applied=False, detail="Could not parse var name")

    var_name = match.group(1)
    existing = _read_file_safe(env_path) or ""
    if not existing.endswith("\n") and existing:
        existing += "\n"
    new_content = existing + f"{var_name}=\n"

    ok = _write_file_safe(env_path, new_content)
    return RepairResult(
        issue_id=issue.id,
        applied=ok,
        detail=f"Added '{var_name}' to .env.example" if ok else "Failed to update .env.example",
    )


def _fix_empty_file(project_path: str, issue: RepairIssue) -> RepairResult:
    """Add placeholder content to an empty file."""
    full = os.path.join(project_path, issue.file_path)
    ext = os.path.splitext(issue.file_path)[1]

    placeholders = {
        ".py": f'"""TODO: Implement {os.path.basename(issue.file_path)}"""\n',
        ".sql": f"-- TODO: Implement migration {os.path.basename(issue.file_path)}\n",
        ".md": f"# {os.path.splitext(os.path.basename(issue.file_path))[0]}\n\nTODO: Add content.\n",
        ".txt": f"# {os.path.basename(issue.file_path)}\n",
        ".yaml": f"# {os.path.basename(issue.file_path)}\n",
        ".yml": f"# {os.path.basename(issue.file_path)}\n",
        ".json": "{}\n",
    }

    content = placeholders.get(ext, f"# TODO: Implement {os.path.basename(issue.file_path)}\n")
    ok = _write_file_safe(full, content)
    return RepairResult(
        issue_id=issue.id,
        applied=ok,
        detail=f"Added placeholder content to '{issue.file_path}'" if ok else "Failed to write placeholder",
    )


def _fix_missing_requirement(project_path: str, issue: RepairIssue) -> RepairResult:
    """Append a missing package to ``requirements.txt``."""
    req_path = os.path.join(project_path, "requirements.txt")
    match = re.search(r"'([^']+)'", issue.fix_description)
    if not match:
        return RepairResult(issue_id=issue.id, applied=False, detail="Could not parse package spec")

    pkg_spec = match.group(1)
    existing = _read_file_safe(req_path) or ""
    if not existing.endswith("\n") and existing:
        existing += "\n"
    new_content = existing + f"{pkg_spec}\n"

    ok = _write_file_safe(req_path, new_content)
    return RepairResult(
        issue_id=issue.id,
        applied=ok,
        detail=f"Added '{pkg_spec}' to requirements.txt" if ok else "Failed to update requirements.txt",
    )


# ---------------------------------------------------------------------------
# Fix dispatcher
# ---------------------------------------------------------------------------

_FIX_DISPATCH = {
    "missing_init_py": _fix_missing_init_py,
    "missing_import": _fix_missing_import,
    "missing_env": _fix_missing_env_var,
    "empty_file": _fix_empty_file,
    "missing_req": _fix_missing_requirement,
}


def fix_issue(project_path: str, issue: RepairIssue) -> RepairResult:
    """Apply a fix for a single :class:`RepairIssue`.

    Args:
        project_path: Absolute path to the project root.
        issue: The issue to fix.

    Returns:
        A :class:`RepairResult` describing what happened.
    """
    if not issue.auto_fixable:
        return RepairResult(
            issue_id=issue.id,
            applied=False,
            detail="Issue is not auto-fixable; manual intervention required",
        )

    # Dispatch by issue id prefix
    prefix = issue.id.rsplit("_", 1)[0] if "_" in issue.id else issue.id
    # The prefix is like "missing_init_py" -- strip the trailing counter
    for key, handler in _FIX_DISPATCH.items():
        if prefix.startswith(key) or issue.id.startswith(key):
            return handler(project_path, issue)

    return RepairResult(
        issue_id=issue.id,
        applied=False,
        detail=f"No fix handler registered for issue type '{prefix}'",
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def scan_project(project_path: str) -> list[RepairIssue]:
    """Scan a project and return all detected issues.

    Args:
        project_path: Absolute path to the project root.

    Returns:
        List of :class:`RepairIssue` objects found.
    """
    global _ISSUE_COUNTER
    _ISSUE_COUNTER = 0

    project_path = os.path.abspath(project_path)

    if not os.path.isdir(project_path):
        return [RepairIssue(
            id="project_not_found_1",
            severity="critical",
            category="structure",
            file_path=project_path,
            description=f"Project directory not found: {project_path}",
            fix_description="Verify the project path is correct",
            auto_fixable=False,
        )]

    manifest = _load_manifest(project_path)
    module_ids = _get_installed_module_ids(manifest)

    issues: list[RepairIssue] = []

    # Run all scanners
    issues.extend(_scan_missing_init_py(project_path))
    issues.extend(_scan_missing_imports_in_main(project_path, module_ids))
    issues.extend(_scan_broken_dependencies(module_ids))
    issues.extend(_scan_missing_env_vars(project_path, module_ids))
    issues.extend(_scan_empty_files(project_path))
    issues.extend(_scan_sql_migrations(project_path))
    issues.extend(_scan_missing_requirements(project_path, module_ids))

    return issues


def repair_project(
    project_path: str,
    auto_fix: bool = False,
    dry_run: bool = False,
) -> RepairReport:
    """Scan a project and optionally apply fixes.

    Args:
        project_path: Absolute path to the project root.
        auto_fix: If True, apply all auto-fixable repairs.
        dry_run: If True with ``auto_fix``, show what would be fixed
            but do not write anything to disk.

    Returns:
        A :class:`RepairReport` with all findings and applied fixes.
    """
    project_path = os.path.abspath(project_path)
    issues = scan_project(project_path)

    report = RepairReport(project_path=project_path, issues=issues)

    # Summary counts
    report.summary = {
        "critical": sum(1 for i in issues if i.severity == "critical"),
        "warning": sum(1 for i in issues if i.severity == "warning"),
        "info": sum(1 for i in issues if i.severity == "info"),
        "total": len(issues),
        "auto_fixable": sum(1 for i in issues if i.auto_fixable),
    }

    if auto_fix:
        for issue in issues:
            if not issue.auto_fixable:
                report.fixes.append(RepairResult(
                    issue_id=issue.id,
                    applied=False,
                    detail="Not auto-fixable",
                ))
                continue

            if dry_run:
                report.fixes.append(RepairResult(
                    issue_id=issue.id,
                    applied=False,
                    detail=f"[DRY RUN] Would apply: {issue.fix_description}",
                ))
            else:
                result = fix_issue(project_path, issue)
                report.fixes.append(result)

    return report

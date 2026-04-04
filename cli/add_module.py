#!/usr/bin/env python3
"""Add a module to an existing NexusForge project.

Reads the project manifest, checks compatibility, resolves dependencies,
renders module templates, updates main.py / requirements.txt / .env.example,
and runs quality gates.

Usage::

    # Add a module
    python cli/add_module.py --project ./my_project --module billing

    # Dry-run: preview what would change
    python cli/add_module.py --project ./my_project --module billing --dry-run

    # List all available modules
    python cli/add_module.py --project ./my_project --list

    # Check compatibility without installing
    python cli/add_module.py --project ./my_project --check billing
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import yaml

from core.module_composer import get_module, inject_module, load_all_modules
from core.compatibility import (
    COMPATIBILITY_MATRIX,
    check_compatibility,
    get_all_env_vars,
    get_all_packages,
    get_missing_dependencies,
)
from core.quality_gate import run_quality_gates


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_manifest(project_path: str) -> dict | None:
    """Load and return the project manifest, or ``None``."""
    manifest_path = os.path.join(project_path, "project_manifest.yaml")
    if not os.path.isfile(manifest_path):
        return None
    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    except Exception:
        return None


def _get_installed_module_ids(manifest: dict | None) -> list[str]:
    """Extract the list of module IDs already installed."""
    if manifest is None:
        return []
    return [m.get("id", "") for m in manifest.get("modules", []) if m.get("id")]


def _get_blueprint_id(manifest: dict | None) -> str:
    """Extract the blueprint ID from the manifest."""
    if manifest is None:
        return ""
    bp = manifest.get("blueprint", {})
    return bp.get("id", "")


def _update_requirements_txt(project_path: str, packages: list[str]) -> int:
    """Append missing packages to requirements.txt.

    Returns:
        Number of packages added.
    """
    req_path = os.path.join(project_path, "requirements.txt")
    existing_content = ""
    if os.path.isfile(req_path):
        with open(req_path, "r", encoding="utf-8") as f:
            existing_content = f.read()

    # Parse existing package names
    import re
    installed: set[str] = set()
    for line in existing_content.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("-"):
            continue
        pkg_name = re.split(r"[>=<!\[]", line)[0].strip().lower()
        if pkg_name:
            installed.add(pkg_name)

    added = 0
    lines_to_add: list[str] = []
    for pkg_spec in packages:
        pkg_name = re.split(r"[>=<!\[]", pkg_spec)[0].strip().lower()
        if pkg_name not in installed:
            lines_to_add.append(pkg_spec)
            installed.add(pkg_name)
            added += 1

    if lines_to_add:
        if existing_content and not existing_content.endswith("\n"):
            existing_content += "\n"
        new_content = existing_content + "\n".join(lines_to_add) + "\n"
        with open(req_path, "w", encoding="utf-8") as f:
            f.write(new_content)

    return added


def _update_env_example(project_path: str, env_vars: list[str]) -> int:
    """Append missing env vars to .env.example.

    Returns:
        Number of vars added.
    """
    env_path = os.path.join(project_path, ".env.example")
    existing_content = ""
    if os.path.isfile(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            existing_content = f.read()

    defined: set[str] = set()
    for line in existing_content.splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            defined.add(line.split("=", 1)[0].strip())

    added = 0
    lines_to_add: list[str] = []
    for var in env_vars:
        if var not in defined:
            lines_to_add.append(f"{var}=")
            defined.add(var)
            added += 1

    if lines_to_add:
        if existing_content and not existing_content.endswith("\n"):
            existing_content += "\n"
        new_content = existing_content + "\n".join(lines_to_add) + "\n"
        with open(env_path, "w", encoding="utf-8") as f:
            f.write(new_content)

    return added


def _update_manifest(project_path: str, module_def: dict) -> bool:
    """Add the module entry to the project manifest.

    Returns:
        True if manifest was updated, False otherwise.
    """
    manifest_path = os.path.join(project_path, "project_manifest.yaml")
    if not os.path.isfile(manifest_path):
        return False

    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = yaml.safe_load(f)

        if not isinstance(manifest, dict):
            return False

        modules = manifest.setdefault("modules", [])
        existing_ids = {m.get("id") for m in modules}

        mod_id = module_def.get("id", "")
        if mod_id in existing_ids:
            return False

        modules.append({
            "id": mod_id,
            "name": module_def.get("name", ""),
            "requires": module_def.get("requires", []),
        })

        with open(manifest_path, "w", encoding="utf-8") as f:
            yaml.dump(manifest, f, default_flow_style=False, sort_keys=False, allow_unicode=True)

        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# CLI actions
# ---------------------------------------------------------------------------

def _action_list(project_path: str) -> None:
    """List all available modules and their status."""
    manifest = _load_manifest(project_path)
    installed = set(_get_installed_module_ids(manifest))
    blueprint_id = _get_blueprint_id(manifest)
    all_modules = load_all_modules()

    print(f"Available modules ({len(all_modules)}):\n")

    for mod_id, mod in sorted(all_modules.items()):
        status = "INSTALLED" if mod_id in installed else "available"
        compat_entry = COMPATIBILITY_MATRIX.get(mod_id, {})
        bp_compat = compat_entry.get("compatible_blueprints", [])
        bp_ok = blueprint_id in bp_compat if blueprint_id else True
        compat_tag = "" if bp_ok else f" [incompatible with {blueprint_id}]"

        deps = mod.get("requires", [])
        dep_str = f" (requires: {', '.join(deps)})" if deps else ""

        print(f"  [{status:>9}] {mod_id:<20} {mod.get('name', '')}{dep_str}{compat_tag}")

    print()


def _action_check(project_path: str, module_id: str) -> None:
    """Check compatibility of a module without installing."""
    manifest = _load_manifest(project_path)
    installed = _get_installed_module_ids(manifest)
    blueprint_id = _get_blueprint_id(manifest)

    if not blueprint_id:
        print("[WARNING] Could not determine blueprint from manifest")

    # Build proposed composition
    proposed = list(set(installed + [module_id]))
    result = check_compatibility(blueprint_id, proposed)

    print(f"Compatibility check: '{module_id}' + blueprint '{blueprint_id}'\n")

    if result.compatible:
        print("  COMPATIBLE -- module can be added")
    else:
        print("  INCOMPATIBLE -- issues found:")
        for issue in result.issues:
            print(f"    - {issue}")

    if result.missing_deps:
        print(f"\n  Missing dependencies: {', '.join(result.missing_deps)}")

    if result.conflicts:
        print(f"\n  Conflicts: {result.conflicts}")

    entry = COMPATIBILITY_MATRIX.get(module_id)
    if entry:
        print(f"\n  Packages needed: {entry['python_packages']}")
        print(f"  Env vars needed: {entry['env_vars']}")

    print()


def _action_add(project_path: str, module_id: str, dry_run: bool = False) -> None:
    """Add a module to the project."""
    manifest = _load_manifest(project_path)
    installed = _get_installed_module_ids(manifest)
    blueprint_id = _get_blueprint_id(manifest)

    # Check if already installed
    if module_id in installed:
        print(f"[INFO] Module '{module_id}' is already installed")
        sys.exit(0)

    # Load module definition
    module_def = get_module(module_id)
    if module_def is None:
        print(f"[ERROR] Unknown module: '{module_id}'")
        print("Use --list to see available modules")
        sys.exit(1)

    # Check compatibility
    proposed = list(set(installed + [module_id]))
    compat = check_compatibility(blueprint_id, proposed)

    if not compat.compatible:
        print(f"[ERROR] Module '{module_id}' is not compatible:")
        for issue in compat.issues:
            print(f"  - {issue}")

        # Check if it's just missing deps that we can auto-add
        if compat.missing_deps and not compat.conflicts:
            print(f"\n[INFO] Missing dependencies: {', '.join(compat.missing_deps)}")
            print("Install those modules first, or they will be skipped.")
        sys.exit(1)

    # Check dependencies
    missing_deps = get_missing_dependencies(proposed)
    if missing_deps:
        print(f"[WARNING] Missing module dependencies: {', '.join(missing_deps)}")
        print("These modules should be installed first for full functionality.")

    if dry_run:
        print(f"\n[DRY RUN] Would add module '{module_id}':")
        entry = COMPATIBILITY_MATRIX.get(module_id, {})
        print(f"  Files: module templates rendered to project")
        print(f"  Packages to add: {entry.get('python_packages', [])}")
        print(f"  Env vars to add: {entry.get('env_vars', [])}")
        print(f"  main.py: router import + include_router")
        print(f"  Manifest: add module entry")
        return

    # Inject module files
    print(f"Adding module: {module_def.get('name', module_id)}")
    result = inject_module(project_path, module_def)
    print(f"  Files created: {result['files_created']}")
    print(f"  Files modified: {result['files_modified']}")

    # Update requirements.txt
    entry = COMPATIBILITY_MATRIX.get(module_id, {})
    pkgs_added = _update_requirements_txt(project_path, entry.get("python_packages", []))
    if pkgs_added:
        print(f"  Packages added to requirements.txt: {pkgs_added}")

    # Update .env.example
    vars_added = _update_env_example(project_path, entry.get("env_vars", []))
    if vars_added:
        print(f"  Env vars added to .env.example: {vars_added}")

    # Update manifest
    if _update_manifest(project_path, module_def):
        print(f"  Manifest updated")

    # Run quality gates
    print(f"\nRunning quality gates...")
    qg = run_quality_gates(project_path)
    print(f"  Passed: {qg['passed']}/{qg['total']}")
    if qg['failures']:
        for f in qg['failures']:
            print(f"  [FAIL] {f}")

    print(f"\nModule '{module_id}' added successfully")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    """CLI entry point for the add-module tool."""
    parser = argparse.ArgumentParser(
        description="NexusForge -- Add a module to an existing project",
    )
    parser.add_argument(
        "--project", "-p",
        type=str,
        required=True,
        help="Path to the NexusForge project",
    )
    parser.add_argument(
        "--module", "-m",
        type=str,
        default=None,
        help="Module ID to add (e.g. 'billing')",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        default=False,
        help="List all available modules",
    )
    parser.add_argument(
        "--check",
        type=str,
        default=None,
        metavar="MODULE",
        help="Check compatibility of a module without installing",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Preview what would change without writing",
    )
    args = parser.parse_args()

    project_path = os.path.abspath(args.project)

    if not os.path.isdir(project_path):
        print(f"[ERROR] Project not found: {project_path}")
        sys.exit(1)

    if args.list:
        _action_list(project_path)
        return

    if args.check:
        _action_check(project_path, args.check)
        return

    if not args.module:
        parser.print_help()
        print("\nSpecify --module, --list, or --check")
        sys.exit(1)

    _action_add(project_path, args.module, dry_run=args.dry_run)


if __name__ == "__main__":
    main()

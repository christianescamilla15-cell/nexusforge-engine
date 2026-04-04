#!/usr/bin/env python3
"""Upgrade a NexusForge project to a newer engine version.

Reads the project manifest to determine which engine version was used to
generate it, compares current templates against the project's files, and
shows a diff.  For v0.5, this tool is **diff-only** -- full auto-merge
is planned for v1.0.

Usage::

    # Show what would change
    python cli/upgrade_project.py --project ./my_project --diff

    # Apply upgrade to v0.5
    python cli/upgrade_project.py --project ./my_project --target-version 0.5
"""

import argparse
import difflib
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import yaml

# Engine version shipped with this release
CURRENT_ENGINE_VERSION = "0.5"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_manifest(project_path: str) -> dict | None:
    """Load the project manifest, or ``None``."""
    manifest_path = os.path.join(project_path, "project_manifest.yaml")
    if not os.path.isfile(manifest_path):
        return None
    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    except Exception:
        return None


def _read_file(path: str) -> str | None:
    """Return file contents or ``None`` on error."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return None


def _get_project_version(manifest: dict | None) -> str:
    """Extract the ``created_with_version`` or ``version`` field."""
    if manifest is None:
        return "unknown"
    return manifest.get("created_with_version", manifest.get("version", "unknown"))


def _collect_template_originals(
    blueprint_id: str,
    module_ids: list[str],
) -> dict[str, str]:
    """Collect the "current engine" template contents keyed by relative path.

    This simulates what the engine would generate for the same blueprint
    and module set, so we can compare against the user's project.

    Returns:
        Dict mapping relative_path -> expected content (unrendered template
        comment markers stripped for comparison purposes).
    """
    engine_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    originals: dict[str, str] = {}

    # Shared templates
    shared_dir = os.path.join(engine_root, "templates", "shared")
    if os.path.isdir(shared_dir):
        for root, _dirs, files in os.walk(shared_dir):
            for fname in files:
                if fname.endswith(".j2"):
                    full = os.path.join(root, fname)
                    rel = os.path.relpath(full, shared_dir)
                    if rel.endswith(".j2"):
                        rel = rel[:-3]
                    content = _read_file(full)
                    if content:
                        originals[rel] = content

    # Blueprint templates
    bp_template_dir = os.path.join(engine_root, "blueprints", blueprint_id, "template")
    if os.path.isdir(bp_template_dir):
        for root, _dirs, files in os.walk(bp_template_dir):
            for fname in files:
                if fname.endswith(".j2"):
                    full = os.path.join(root, fname)
                    rel = os.path.relpath(full, bp_template_dir)
                    if rel.endswith(".j2"):
                        rel = rel[:-3]
                    content = _read_file(full)
                    if content:
                        originals[rel] = content

    return originals


def _compute_diffs(
    project_path: str,
    originals: dict[str, str],
) -> list[dict]:
    """Compare project files against template originals.

    Returns:
        List of dicts with 'path', 'status' (modified/missing/new), and 'diff'.
    """
    diffs: list[dict] = []

    for rel_path, template_content in sorted(originals.items()):
        project_file = os.path.join(project_path, rel_path)
        project_content = _read_file(project_file)

        if project_content is None:
            diffs.append({
                "path": rel_path,
                "status": "missing",
                "diff": f"File '{rel_path}' exists in templates but not in project",
            })
            continue

        if project_content.strip() == template_content.strip():
            continue  # No changes

        diff_lines = list(difflib.unified_diff(
            project_content.splitlines(keepends=True),
            template_content.splitlines(keepends=True),
            fromfile=f"project/{rel_path}",
            tofile=f"template/{rel_path}",
            lineterm="",
        ))

        if diff_lines:
            diffs.append({
                "path": rel_path,
                "status": "modified",
                "diff": "\n".join(diff_lines),
            })

    return diffs


def _apply_version_bump(project_path: str, target_version: str) -> bool:
    """Update the manifest with the new engine version.

    Returns:
        True if the manifest was updated.
    """
    manifest_path = os.path.join(project_path, "project_manifest.yaml")
    manifest = _load_manifest(project_path)
    if manifest is None:
        return False

    manifest["created_with_version"] = target_version

    try:
        with open(manifest_path, "w", encoding="utf-8") as f:
            yaml.dump(manifest, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# CLI actions
# ---------------------------------------------------------------------------

def _action_diff(project_path: str) -> None:
    """Show what templates have changed compared to the project."""
    manifest = _load_manifest(project_path)
    current_version = _get_project_version(manifest)

    blueprint_id = ""
    if manifest:
        blueprint_id = manifest.get("blueprint", {}).get("id", "")

    module_ids = []
    if manifest:
        module_ids = [m.get("id", "") for m in manifest.get("modules", []) if m.get("id")]

    print(f"Project version: {current_version}")
    print(f"Engine version:  {CURRENT_ENGINE_VERSION}")
    print(f"Blueprint:       {blueprint_id}")
    print(f"Modules:         {', '.join(module_ids) or 'none'}")
    print("=" * 60)

    originals = _collect_template_originals(blueprint_id, module_ids)

    if not originals:
        print("\nNo template originals found for comparison.")
        return

    diffs = _compute_diffs(project_path, originals)

    if not diffs:
        print("\nNo differences found -- project matches current templates.")
        return

    print(f"\n{len(diffs)} file(s) differ:\n")
    for d in diffs:
        print(f"  [{d['status'].upper():>8}] {d['path']}")

    print("\nDetailed diffs:\n")
    for d in diffs:
        print(f"--- {d['path']} ({d['status']}) ---")
        print(d["diff"])
        print()


def _action_upgrade(project_path: str, target_version: str) -> None:
    """Apply upgrade to the target version.

    For v0.5 this only bumps the version in the manifest and shows
    the diff.  Full template merging comes in v1.0.
    """
    manifest = _load_manifest(project_path)
    current_version = _get_project_version(manifest)

    print(f"Upgrading project from v{current_version} to v{target_version}")
    print("=" * 60)

    # Show diff first
    _action_diff(project_path)

    print("\n" + "=" * 60)
    print("NOTE: Full auto-merge of template changes is planned for v1.0.")
    print("For now, review the diffs above and apply changes manually.")

    # Bump version in manifest
    if _apply_version_bump(project_path, target_version):
        print(f"\nManifest updated: created_with_version = {target_version}")
    else:
        print("\n[WARNING] Could not update manifest version")

    print(f"\nUpgrade to v{target_version} complete (version bumped).")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    """CLI entry point for the project upgrade tool."""
    parser = argparse.ArgumentParser(
        description="NexusForge -- Upgrade a project to a newer engine version",
    )
    parser.add_argument(
        "--project", "-p",
        type=str,
        required=True,
        help="Path to the NexusForge project",
    )
    parser.add_argument(
        "--target-version", "-t",
        type=str,
        default=CURRENT_ENGINE_VERSION,
        help=f"Target engine version (default: {CURRENT_ENGINE_VERSION})",
    )
    parser.add_argument(
        "--diff",
        action="store_true",
        default=False,
        help="Show what would change without applying",
    )
    args = parser.parse_args()

    project_path = os.path.abspath(args.project)

    if not os.path.isdir(project_path):
        print(f"[ERROR] Project not found: {project_path}")
        sys.exit(1)

    if args.diff:
        _action_diff(project_path)
    else:
        _action_upgrade(project_path, args.target_version)


if __name__ == "__main__":
    main()

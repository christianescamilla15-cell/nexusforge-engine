"""Module Composer -- Loads, filters, orders, and injects project modules.

Modules are self-contained feature packages (auth, billing, etc.) that get
composed into a project based on the selected blueprint and user intent.
The composer handles dependency resolution and topological sorting.
"""

import os
import glob
from typing import Any, Optional

import yaml


_ENGINE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_MODULES_DIR = os.path.join(_ENGINE_ROOT, "modules")


def _load_module(path: str) -> dict[str, Any]:
    """Load a single module definition from a YAML file.

    Args:
        path: Absolute path to the module.yaml file.

    Returns:
        Dictionary with all module fields.

    Raises:
        FileNotFoundError: If the module file does not exist.
        yaml.YAMLError: If the file contains invalid YAML.
        ValueError: If the module is missing the required 'id' field.
    """
    if not os.path.isfile(path):
        raise FileNotFoundError(f"Module file not found: {path}")

    with open(path, "r", encoding="utf-8") as f:
        try:
            data = yaml.safe_load(f)
        except yaml.YAMLError as exc:
            raise yaml.YAMLError(f"Invalid YAML in {path}: {exc}") from exc

    if not isinstance(data, dict):
        raise ValueError(f"Module file must contain a YAML mapping: {path}")

    if "id" not in data:
        raise ValueError(f"Module missing required 'id' field: {path}")

    return data


def load_all_modules(modules_dir: Optional[str] = None) -> dict[str, dict[str, Any]]:
    """Load every module definition from the modules directory.

    Scans for */module.yaml under the given directory.

    Args:
        modules_dir: Path to the modules directory.
            Defaults to <engine_root>/modules/.

    Returns:
        Dictionary mapping module id -> module dict.
    """
    base = modules_dir or _MODULES_DIR

    if not os.path.isdir(base):
        raise FileNotFoundError(f"Modules directory not found: {base}")

    modules: dict[str, dict[str, Any]] = {}
    pattern = os.path.join(base, "*", "module.yaml")

    for mod_path in sorted(glob.glob(pattern)):
        try:
            mod = _load_module(mod_path)
            modules[mod["id"]] = mod
        except (ValueError, yaml.YAMLError, FileNotFoundError) as exc:
            print(f"[WARNING] Skipping module at {mod_path}: {exc}")

    return modules


def _is_compatible(module: dict[str, Any], blueprint: dict[str, Any]) -> bool:
    """Check if a module is compatible with the given blueprint.

    Checks both project_type and platform compatibility.

    Args:
        module: Module definition dictionary.
        blueprint: Blueprint definition dictionary.

    Returns:
        True if the module is compatible with the blueprint.
    """
    compat = module.get("compatible_with", {})
    project_types = compat.get("project_types", [])
    platforms = compat.get("platforms", [])

    bp_id = blueprint.get("id", "")
    bp_framework = blueprint.get("stack", {}).get("framework", "")

    type_ok = not project_types or bp_id in project_types
    platform_ok = not platforms or bp_framework in platforms

    return type_ok and platform_ok


def _topological_sort(
    modules: dict[str, dict[str, Any]],
    selected_ids: list[str],
) -> list[str]:
    """Sort module IDs by dependency order using Kahn's algorithm.

    Args:
        modules: All available module definitions.
        selected_ids: List of module IDs to sort.

    Returns:
        List of module IDs in dependency order (dependencies first).

    Raises:
        ValueError: If a circular dependency is detected.
    """
    in_degree: dict[str, int] = {mid: 0 for mid in selected_ids}
    dependents: dict[str, list[str]] = {mid: [] for mid in selected_ids}

    for mid in selected_ids:
        mod = modules.get(mid, {})
        for dep in mod.get("requires", []):
            if dep in in_degree:
                in_degree[mid] += 1
                dependents[dep].append(mid)

    queue = [mid for mid in selected_ids if in_degree[mid] == 0]
    sorted_ids: list[str] = []

    while queue:
        current = queue.pop(0)
        sorted_ids.append(current)
        for dependent in dependents.get(current, []):
            in_degree[dependent] -= 1
            if in_degree[dependent] == 0:
                queue.append(dependent)

    if len(sorted_ids) != len(selected_ids):
        missing = set(selected_ids) - set(sorted_ids)
        raise ValueError(
            f"Circular dependency detected among modules: {missing}. "
            "Check the 'requires' fields in module definitions."
        )

    return sorted_ids


def compose_modules(
    intent: dict[str, Any],
    blueprint: dict[str, Any],
    modules_dir: Optional[str] = None,
) -> list[dict[str, Any]]:
    """Compose the list of modules for a project based on intent and blueprint.

    Steps:
    1. Load all module definitions from disk.
    2. Start with the blueprint's required_modules.
    3. Add modules requested in the intent.
    4. Filter by compatibility with the blueprint.
    5. Resolve dependencies (add missing required modules).
    6. Sort by dependency order.

    Args:
        intent: Intent dictionary, may contain a 'modules' list.
        blueprint: Selected blueprint dictionary.
        modules_dir: Optional override for the modules directory.

    Returns:
        Ordered list of module dictionaries, dependencies first.
    """
    all_modules = load_all_modules(modules_dir)

    # Gather requested module IDs
    requested: set[str] = set()

    for mid in blueprint.get("required_modules", []):
        requested.add(mid)

    for mid in intent.get("modules", []):
        requested.add(mid)

    # Filter by compatibility
    compatible_ids: set[str] = set()
    for mid in requested:
        if mid in all_modules:
            if _is_compatible(all_modules[mid], blueprint):
                compatible_ids.add(mid)
            else:
                print(
                    f"[WARNING] Module '{mid}' is not compatible with "
                    f"blueprint '{blueprint.get('id')}', skipping."
                )
        else:
            print(f"[WARNING] Module '{mid}' not found in modules directory, skipping.")

    # Resolve dependencies -- add any required modules that are missing
    resolved: set[str] = set(compatible_ids)
    to_check = list(compatible_ids)

    while to_check:
        mid = to_check.pop()
        mod = all_modules.get(mid)
        if not mod:
            continue
        for dep_id in mod.get("requires", []):
            if dep_id not in resolved and dep_id in all_modules:
                if _is_compatible(all_modules[dep_id], blueprint):
                    resolved.add(dep_id)
                    to_check.append(dep_id)
                else:
                    print(
                        f"[WARNING] Dependency '{dep_id}' of module '{mid}' "
                        f"is not compatible with blueprint '{blueprint.get('id')}'."
                    )

    # Sort by dependency order
    try:
        sorted_ids = _topological_sort(all_modules, list(resolved))
    except ValueError as exc:
        print(f"[ERROR] {exc}")
        sorted_ids = sorted(resolved)

    return [all_modules[mid] for mid in sorted_ids if mid in all_modules]


def get_module(
    name: str,
    modules_dir: Optional[str] = None,
) -> Optional[dict[str, Any]]:
    """Retrieve a single module definition by name.

    Args:
        name: The module ID (e.g., 'auth', 'billing').
        modules_dir: Optional override for the modules directory.

    Returns:
        Module dictionary if found, None otherwise.
    """
    all_modules = load_all_modules(modules_dir)
    return all_modules.get(name)


def inject_module(
    project_path: str,
    module: dict[str, Any],
) -> dict[str, Any]:
    """Inject a module's files and directories into an existing project.

    Creates the directories and placeholder files specified in the module's
    'injects' section.

    Args:
        project_path: Absolute path to the project root.
        module: Module definition dictionary with 'injects' field.

    Returns:
        Summary dict with 'files_created' and 'files_modified' counts.

    Raises:
        FileNotFoundError: If the project path does not exist.
    """
    if not os.path.isdir(project_path):
        raise FileNotFoundError(f"Project directory not found: {project_path}")

    injects = module.get("injects", {})
    files_created = 0
    files_modified = 0

    # Create directories
    for folder in injects.get("folders", []):
        dir_path = os.path.join(project_path, folder)
        os.makedirs(dir_path, exist_ok=True)

    # Create files
    for file_def in injects.get("files", []):
        file_path = os.path.join(project_path, file_def["path"])

        os.makedirs(os.path.dirname(file_path), exist_ok=True)

        if os.path.exists(file_path):
            files_modified += 1
        else:
            files_created += 1

        content = file_def.get("content")
        if not content:
            description = file_def.get("description", f"Module: {module['id']}")
            content = (
                f"\"\"\"{description}\"\"\"\n\n"
                f"# TODO: Implement {file_def['path']}\n"
                f"# Module: {module['id']}\n"
            )

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)

    return {
        "files_created": files_created,
        "files_modified": files_modified,
    }

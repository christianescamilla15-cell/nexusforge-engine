"""Module Composer -- Loads, filters, orders, and injects project modules.

Modules are self-contained feature packages (auth, billing, etc.) that get
composed into a project based on the selected blueprint and user intent.
The composer handles dependency resolution, topological sorting, template
file discovery, and Jinja2-based module injection.
"""

import os
import glob
from typing import Any, Optional

import yaml

try:
    from jinja2 import Environment, BaseLoader, TemplateError
    HAS_JINJA2 = True
except ImportError:
    HAS_JINJA2 = False


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


def _discover_template_files(
    module_id: str,
    modules_dir: Optional[str] = None,
) -> list[dict[str, str]]:
    """Discover all .j2 template files for a module.

    Scans modules/{module_id}/template/ for *.j2 files recursively.

    Args:
        module_id: The module's ID (directory name).
        modules_dir: Optional override for the modules directory.

    Returns:
        List of dicts with 'template_path' (absolute path to .j2 file),
        'relative_path' (output path without .j2 extension), and
        'filename' (just the basename).
    """
    base = modules_dir or _MODULES_DIR
    template_dir = os.path.join(base, module_id, "template")

    if not os.path.isdir(template_dir):
        return []

    templates: list[dict[str, str]] = []
    pattern = os.path.join(template_dir, "**", "*.j2")

    for tpl_path in sorted(glob.glob(pattern, recursive=True)):
        rel = os.path.relpath(tpl_path, template_dir)
        # Strip .j2 extension for the output path
        if rel.endswith(".j2"):
            rel = rel[:-3]

        templates.append({
            "template_path": tpl_path,
            "relative_path": rel,
            "filename": os.path.basename(rel),
        })

    return templates


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


def _validate_dependencies(
    module_ids: list[str],
    all_modules: dict[str, dict[str, Any]],
) -> list[str]:
    """Validate that all module dependencies are satisfied.

    Args:
        module_ids: List of module IDs being composed.
        all_modules: All available module definitions.

    Returns:
        List of warning messages for missing dependencies.
    """
    warnings: list[str] = []
    selected_set = set(module_ids)

    for mid in module_ids:
        mod = all_modules.get(mid)
        if not mod:
            continue
        for dep in mod.get("requires", []):
            if dep not in selected_set:
                warnings.append(
                    f"Module '{mid}' requires '{dep}' which is not in the composition"
                )

    return warnings


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
    7. Discover and attach template files for each module.

    Args:
        intent: Intent dictionary, may contain a 'modules' list.
        blueprint: Selected blueprint dictionary.
        modules_dir: Optional override for the modules directory.

    Returns:
        Ordered list of module dictionaries, dependencies first.
        Each module dict includes a 'template_files' key with the
        list of discovered template files and their contents.
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

    # Validate all dependencies are present
    dep_warnings = _validate_dependencies(list(resolved), all_modules)
    for warning in dep_warnings:
        print(f"[WARNING] {warning}")

    # Sort by dependency order
    try:
        sorted_ids = _topological_sort(all_modules, list(resolved))
    except ValueError as exc:
        print(f"[ERROR] {exc}")
        sorted_ids = sorted(resolved)

    # Attach template files to each module
    result: list[dict[str, Any]] = []
    for mid in sorted_ids:
        if mid not in all_modules:
            continue
        mod = dict(all_modules[mid])  # Copy to avoid mutating the original

        # Discover template files
        tpl_files = _discover_template_files(mid, modules_dir)
        tpl_with_content: list[dict[str, str]] = []

        for tpl in tpl_files:
            try:
                with open(tpl["template_path"], "r", encoding="utf-8") as f:
                    content = f.read()
                tpl_with_content.append({
                    "template_path": tpl["template_path"],
                    "relative_path": tpl["relative_path"],
                    "filename": tpl["filename"],
                    "content": content,
                })
            except OSError as exc:
                print(
                    f"[WARNING] Failed to read template {tpl['template_path']}: {exc}"
                )

        mod["template_files"] = tpl_with_content
        result.append(mod)

    return result


def get_module(
    name: str,
    modules_dir: Optional[str] = None,
) -> Optional[dict[str, Any]]:
    """Retrieve a single module definition by name.

    Args:
        name: The module ID (e.g., 'auth', 'billing').
        modules_dir: Optional override for the modules directory.

    Returns:
        Module dictionary if found (with template_files), None otherwise.
    """
    all_modules = load_all_modules(modules_dir)
    mod = all_modules.get(name)
    if mod is None:
        return None

    # Attach template files
    mod = dict(mod)
    tpl_files = _discover_template_files(name, modules_dir)
    tpl_with_content: list[dict[str, str]] = []

    for tpl in tpl_files:
        try:
            with open(tpl["template_path"], "r", encoding="utf-8") as f:
                content = f.read()
            tpl_with_content.append({
                "template_path": tpl["template_path"],
                "relative_path": tpl["relative_path"],
                "filename": tpl["filename"],
                "content": content,
            })
        except OSError:
            pass

    mod["template_files"] = tpl_with_content
    return mod


def _render_template_string(template_str: str, variables: dict[str, Any]) -> str:
    """Render a Jinja2 template string with variables.

    Args:
        template_str: The raw template content.
        variables: Template variables to substitute.

    Returns:
        Rendered string.
    """
    if HAS_JINJA2:
        try:
            env = Environment(
                keep_trailing_newline=True,
                trim_blocks=True,
                lstrip_blocks=True,
            )
            template = env.from_string(template_str)
            return template.render(**variables)
        except TemplateError as exc:
            print(f"[WARNING] Jinja2 render error: {exc}")
            return template_str
    else:
        # Simple fallback
        result = template_str
        for key, value in variables.items():
            result = result.replace("{{" + key + "}}", str(value))
            result = result.replace("{{ " + key + " }}", str(value))
        return result


def _get_module_output_prefix(module: dict[str, Any]) -> str:
    """Determine the output directory prefix for a module's files.

    Uses the first folder in the module's 'injects' section, or
    falls back to src/{module_id}/.

    Args:
        module: Module definition dictionary.

    Returns:
        Relative path prefix for the module's output files.
    """
    injects = module.get("injects", {})
    folders = injects.get("folders", [])
    if folders:
        return folders[0].rstrip("/")
    return f"src/{module['id']}"


def inject_module(
    project_path: str,
    module: dict[str, Any],
    variables: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Inject a module's rendered template files into an existing project.

    Reads each .j2 template from the module's template directory,
    renders it with Jinja2 variables, writes it to the correct location
    in the project, and updates main.py to import the new router.

    Args:
        project_path: Absolute path to the project root.
        module: Module definition dictionary (with 'template_files' key).
        variables: Jinja2 template variables.

    Returns:
        Summary dict with:
        - files_created (int): Number of new files written.
        - files_modified (int): Number of existing files overwritten.
        - files (list[str]): List of relative paths written.

    Raises:
        FileNotFoundError: If the project path does not exist.
    """
    if not os.path.isdir(project_path):
        raise FileNotFoundError(f"Project directory not found: {project_path}")

    vars_dict = variables or {}
    mod_id = module.get("id", "unknown")
    prefix = _get_module_output_prefix(module)
    template_files = module.get("template_files", [])

    files_created = 0
    files_modified = 0
    written_files: list[str] = []

    # Step 1: Render and write template files
    for tpl in template_files:
        raw_content = tpl.get("content", "")
        rel_path = tpl.get("relative_path", "")

        if not rel_path or not raw_content:
            continue

        # Determine output path
        # If the relative path contains 'migrations/', put under src/db/migrations/
        if "migrations/" in rel_path or rel_path.startswith("migrations"):
            out_rel = os.path.join("src", "db", rel_path)
        else:
            out_rel = os.path.join(prefix, rel_path)

        # Normalize path separators
        out_rel = out_rel.replace("\\", "/")
        full_path = os.path.join(project_path, out_rel)

        # Render template
        rendered = _render_template_string(raw_content, vars_dict)

        # Ensure directory exists
        os.makedirs(os.path.dirname(full_path), exist_ok=True)

        # Track created vs modified
        if os.path.exists(full_path):
            files_modified += 1
        else:
            files_created += 1

        with open(full_path, "w", encoding="utf-8") as f:
            f.write(rendered)

        written_files.append(out_rel)

    # Step 2: Create __init__.py if missing
    init_path = os.path.join(project_path, prefix, "__init__.py")
    if not os.path.exists(init_path):
        os.makedirs(os.path.dirname(init_path), exist_ok=True)
        with open(init_path, "w", encoding="utf-8") as f:
            f.write(f'"""Module: {module.get("name", mod_id)}"""\n')
        files_created += 1
        written_files.append(f"{prefix}/__init__.py")

    # Step 3: Update main.py to import the module router
    main_py = os.path.join(project_path, "main.py")
    if os.path.isfile(main_py):
        _update_main_py(main_py, module, prefix)
        if "main.py" not in written_files:
            files_modified += 1

    return {
        "files_created": files_created,
        "files_modified": files_modified,
        "files": written_files,
    }


def _update_main_py(
    main_py_path: str,
    module: dict[str, Any],
    prefix: str,
) -> None:
    """Add router import and include_router to main.py if not already present.

    Args:
        main_py_path: Absolute path to main.py.
        module: Module definition.
        prefix: Module source prefix (e.g., 'src/auth').
    """
    mod_id = module.get("id", "unknown")

    # Build import path (src/auth -> src.auth)
    import_module = prefix.replace("/", ".").replace("\\", ".")
    import_line = f"from {import_module}.router import router as {mod_id}_router"
    include_line = f'app.include_router({mod_id}_router, prefix="/api/{mod_id}", tags=["{mod_id}"])'

    try:
        with open(main_py_path, "r", encoding="utf-8") as f:
            content = f.read()

        modified = False

        # Add import if missing
        if import_line not in content:
            # Insert after the last import line
            lines = content.split("\n")
            last_import_idx = 0
            for i, line in enumerate(lines):
                if line.startswith(("import ", "from ")):
                    last_import_idx = i

            lines.insert(last_import_idx + 1, import_line)
            content = "\n".join(lines)
            modified = True

        # Add include_router if missing
        if include_line not in content:
            # Insert before the first @app route or at the end
            lines = content.split("\n")
            insert_idx = len(lines)
            for i, line in enumerate(lines):
                if line.strip().startswith("@app."):
                    insert_idx = i
                    break

            lines.insert(insert_idx, include_line)
            content = "\n".join(lines)
            modified = True

        if modified:
            with open(main_py_path, "w", encoding="utf-8") as f:
                f.write(content)

    except OSError as exc:
        print(f"[WARNING] Failed to update main.py: {exc}")

"""Execution Engine -- Creates files and directories on disk.

Takes the output from the spec generator and template engine,
then physically scaffolds the project by creating all directories
and writing all files. Renders both blueprint and module Jinja2
templates through the template engine. Tracks everything that was created.
"""

import os
from typing import Any

try:
    from jinja2 import Environment, TemplateError
    HAS_JINJA2 = True
except ImportError:
    HAS_JINJA2 = False


_ENGINE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _ensure_directory(path: str) -> bool:
    """Create a directory if it does not exist.

    Args:
        path: Absolute path to the directory.

    Returns:
        True if the directory was created, False if it already existed.
    """
    if os.path.isdir(path):
        return False

    try:
        os.makedirs(path, exist_ok=True)
        return True
    except OSError as exc:
        print(f"[ERROR] Failed to create directory {path}: {exc}")
        return False


def _write_file(path: str, content: str) -> int:
    """Write content to a file, creating parent directories as needed.

    Args:
        path: Absolute path to the file.
        content: String content to write.

    Returns:
        Number of bytes written, or 0 on failure.
    """
    try:
        parent = os.path.dirname(path)
        if parent:
            os.makedirs(parent, exist_ok=True)

        with open(path, "w", encoding="utf-8") as f:
            f.write(content)

        return len(content.encode("utf-8"))
    except OSError as exc:
        print(f"[ERROR] Failed to write file {path}: {exc}")
        return 0


def _render_template_string(template_str: str, variables: dict[str, Any]) -> str:
    """Render a Jinja2 template string with variables.

    Falls back to simple string replacement if Jinja2 is not available.

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
        result = template_str
        for key, value in variables.items():
            result = result.replace("{{" + key + "}}", str(value))
            result = result.replace("{{ " + key + " }}", str(value))
        return result


def _collect_blueprint_templates(blueprint: dict[str, Any]) -> list[dict[str, str]]:
    """Collect .j2 template files from the blueprint's template directory.

    Args:
        blueprint: Blueprint definition dictionary.

    Returns:
        List of dicts with 'template_path', 'relative_path', and 'content'.
    """
    import glob

    bp_id = blueprint.get("id", "")
    template_dir = os.path.join(_ENGINE_ROOT, "blueprints", bp_id, "template")

    if not os.path.isdir(template_dir):
        return []

    templates: list[dict[str, str]] = []
    pattern = os.path.join(template_dir, "**", "*.j2")

    for tpl_path in sorted(glob.glob(pattern, recursive=True)):
        rel = os.path.relpath(tpl_path, template_dir)
        if rel.endswith(".j2"):
            rel = rel[:-3]

        try:
            with open(tpl_path, "r", encoding="utf-8") as f:
                content = f.read()
            templates.append({
                "template_path": tpl_path,
                "relative_path": rel,
                "content": content,
            })
        except OSError as exc:
            print(f"[WARNING] Failed to read blueprint template {tpl_path}: {exc}")

    return templates


def _get_module_output_prefix(module: dict[str, Any]) -> str:
    """Determine output directory prefix for a module's files.

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


def _build_template_variables(
    specs: dict[str, Any],
    blueprint: dict[str, Any] | None,
    modules: list[dict[str, Any]] | None,
    extra_vars: dict[str, Any] | None,
) -> dict[str, Any]:
    """Build the complete variables dictionary for template rendering.

    Combines project metadata from specs, blueprint info, module
    presence flags, and any user-provided extras.

    Args:
        specs: Specs dictionary from the spec generator.
        blueprint: Optional blueprint dict.
        modules: Optional list of module dicts.
        extra_vars: Optional extra variables.

    Returns:
        Merged variables dictionary.
    """
    variables: dict[str, Any] = {}

    # Extract from project_manifest.yaml in specs
    import yaml
    for file_entry in specs.get("files", []):
        if file_entry.get("path") == "project_manifest.yaml":
            try:
                manifest = yaml.safe_load(file_entry["content"])
                if isinstance(manifest, dict):
                    project = manifest.get("project", {})
                    variables["PROJECT_NAME"] = project.get("name", "MyProject")
                    variables["PROJECT_DESCRIPTION"] = project.get("description", "")

                    stack = manifest.get("stack", {})
                    variables["FRAMEWORK"] = stack.get("framework", "fastapi")
                    variables["DATABASE"] = stack.get("database", "postgresql")
            except Exception:
                pass
            break

    # Blueprint metadata
    if blueprint:
        variables.setdefault("PROJECT_NAME", blueprint.get("id", "MyProject"))
        variables["BLUEPRINT_ID"] = blueprint.get("id", "")

    # Module presence flags
    module_ids: list[str] = []
    if modules:
        module_ids = [m.get("id", "") for m in modules]

    variables["MODULES"] = module_ids
    variables["HAS_AUTH"] = "auth" in module_ids
    variables["HAS_BILLING"] = "billing" in module_ids
    variables["HAS_ANALYTICS"] = "analytics" in module_ids
    variables["HAS_AI_CHAT"] = "ai_chat" in module_ids
    variables["HAS_NOTIFICATIONS"] = "notifications" in module_ids
    variables["HAS_CONNECTORS"] = "connectors" in module_ids
    variables["HAS_OBSERVABILITY"] = "observability" in module_ids
    variables["HAS_ADMIN_PANEL"] = "admin_panel" in module_ids

    # LLM provider default
    variables.setdefault("LLM_PROVIDER", "anthropic")

    # User extras override everything
    if extra_vars:
        variables.update(extra_vars)

    return variables


def execute_scaffold(
    specs: dict[str, Any],
    output_dir: str,
    blueprint: dict[str, Any] | None = None,
    modules: list[dict[str, Any]] | None = None,
    rendered_templates: list[dict[str, str]] | None = None,
    template_variables: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create all files and directories for a NexusForge project.

    This is the main entry point for project scaffolding. It:
    1. Creates the output directory.
    2. Creates all directories from the blueprint's base_structure.
    3. Writes all spec files (manifest, requirements, design, tasks).
    4. Renders and writes blueprint templates from blueprints/{name}/template/.
    5. Renders and writes module templates from modules/{name}/template/.
    6. Writes any pre-rendered template files.
    7. Injects fallback module files for modules without templates.
    8. Tracks and returns a summary of what was created.

    Args:
        specs: Specs dictionary from the spec generator, containing a
            'files' list of {path, content} dicts.
        output_dir: Path to the project output directory.
        blueprint: Optional blueprint dict for creating base_structure dirs.
        modules: Optional list of module dicts for injecting module files.
        rendered_templates: Optional list of pre-rendered template {path, content} dicts.
        template_variables: Optional extra variables for Jinja2 rendering.

    Returns:
        Summary dictionary with:
        - files_created (int): Number of files written.
        - dirs_created (int): Number of directories created.
        - total_bytes (int): Total bytes written across all files.
        - files (list[str]): List of relative paths of created files.
        - dirs (list[str]): List of relative paths of created directories.

    Raises:
        ValueError: If specs is not a valid dictionary with 'files' key.
        OSError: If the output directory cannot be created.
    """
    if not isinstance(specs, dict):
        raise ValueError(f"specs must be a dict, got {type(specs).__name__}")

    if "files" not in specs:
        raise ValueError("specs must contain a 'files' key with list of file definitions")

    # Normalize output_dir
    output_dir = os.path.abspath(output_dir)

    files_created = 0
    dirs_created = 0
    total_bytes = 0
    created_files: list[str] = []
    created_dirs: list[str] = []

    # Build template variables
    variables = _build_template_variables(
        specs, blueprint, modules, template_variables
    )

    # Step 1: Create output directory
    if _ensure_directory(output_dir):
        dirs_created += 1
        created_dirs.append(".")

    # Step 2: Create base_structure directories from blueprint
    if blueprint:
        for dir_path in blueprint.get("base_structure", []):
            full_path = os.path.join(output_dir, dir_path)
            if _ensure_directory(full_path):
                dirs_created += 1
                created_dirs.append(dir_path)

    # Step 3: Write spec files
    for file_entry in specs.get("files", []):
        rel_path = file_entry.get("path", "")
        content = file_entry.get("content", "")

        if not rel_path:
            continue

        full_path = os.path.join(output_dir, rel_path)

        # Ensure parent directory
        parent = os.path.dirname(full_path)
        if parent and _ensure_directory(parent):
            parent_rel = os.path.relpath(parent, output_dir)
            if parent_rel not in created_dirs:
                dirs_created += 1
                created_dirs.append(parent_rel)

        bytes_written = _write_file(full_path, content)
        if bytes_written > 0:
            files_created += 1
            total_bytes += bytes_written
            created_files.append(rel_path)

    # Step 4: Render and write blueprint templates
    if blueprint:
        bp_templates = _collect_blueprint_templates(blueprint)
        for tpl in bp_templates:
            rel_path = tpl["relative_path"]
            raw_content = tpl["content"]

            rendered_content = _render_template_string(raw_content, variables)
            full_path = os.path.join(output_dir, rel_path)

            parent = os.path.dirname(full_path)
            if parent and _ensure_directory(parent):
                parent_rel = os.path.relpath(parent, output_dir)
                if parent_rel not in created_dirs:
                    dirs_created += 1
                    created_dirs.append(parent_rel)

            bytes_written = _write_file(full_path, rendered_content)
            if bytes_written > 0:
                files_created += 1
                total_bytes += bytes_written
                created_files.append(rel_path)

    # Step 5: Render and write module templates
    if modules:
        for mod in modules:
            mod_id = mod.get("id", "unknown")
            prefix = _get_module_output_prefix(mod)
            template_files = mod.get("template_files", [])

            if template_files:
                # Create __init__.py for the module
                init_rel = f"{prefix}/__init__.py"
                init_path = os.path.join(output_dir, init_rel)
                if not os.path.exists(init_path):
                    init_content = f'"""Module: {mod.get("name", mod_id)}"""\n'
                    bw = _write_file(init_path, init_content)
                    if bw > 0:
                        files_created += 1
                        total_bytes += bw
                        created_files.append(init_rel)

                # Render each template file
                for tpl in template_files:
                    raw_content = tpl.get("content", "")
                    tpl_rel = tpl.get("relative_path", "")

                    if not tpl_rel or not raw_content:
                        continue

                    # Determine output path
                    if "migrations/" in tpl_rel or tpl_rel.startswith("migrations"):
                        out_rel = f"src/db/{tpl_rel}"
                    else:
                        out_rel = f"{prefix}/{tpl_rel}"

                    out_rel = out_rel.replace("\\", "/")
                    full_path = os.path.join(output_dir, out_rel)

                    rendered_content = _render_template_string(raw_content, variables)

                    parent = os.path.dirname(full_path)
                    if parent and _ensure_directory(parent):
                        parent_rel = os.path.relpath(parent, output_dir)
                        if parent_rel not in created_dirs:
                            dirs_created += 1
                            created_dirs.append(parent_rel)

                    bytes_written = _write_file(full_path, rendered_content)
                    if bytes_written > 0:
                        files_created += 1
                        total_bytes += bytes_written
                        created_files.append(out_rel)

                # Handle subdirectories with __init__.py (e.g., channels/)
                seen_dirs: set[str] = set()
                for tpl in template_files:
                    tpl_rel = tpl.get("relative_path", "")
                    if "/" in tpl_rel:
                        subdir = tpl_rel.rsplit("/", 1)[0]
                        if subdir not in seen_dirs:
                            seen_dirs.add(subdir)
                            sub_init_rel = f"{prefix}/{subdir}/__init__.py"
                            sub_init_path = os.path.join(output_dir, sub_init_rel)
                            if not os.path.exists(sub_init_path):
                                sub_content = f'"""Submodule: {subdir}"""\n'
                                bw = _write_file(sub_init_path, sub_content)
                                if bw > 0:
                                    files_created += 1
                                    total_bytes += bw
                                    created_files.append(sub_init_rel)

            else:
                # Fallback: inject placeholder files from module definition
                injects = mod.get("injects", {})

                for folder in injects.get("folders", []):
                    full_path = os.path.join(output_dir, folder)
                    if _ensure_directory(full_path):
                        dirs_created += 1
                        created_dirs.append(folder)

                for file_def in injects.get("files", []):
                    rel_path = file_def.get("path", "")
                    if not rel_path:
                        continue

                    full_path = os.path.join(output_dir, rel_path)
                    parent = os.path.dirname(full_path)
                    if parent:
                        _ensure_directory(parent)

                    content = file_def.get("content")
                    if not content:
                        description = file_def.get("description", f"Module: {mod_id}")
                        content = (
                            f'"""{description}"""\n\n'
                            f"# TODO: Implement {rel_path}\n"
                            f"# Module: {mod_id}\n"
                        )

                    bytes_written = _write_file(full_path, content)
                    if bytes_written > 0:
                        files_created += 1
                        total_bytes += bytes_written
                        created_files.append(rel_path)

    # Step 6: Write pre-rendered templates (from template_engine.render_templates)
    if rendered_templates:
        for tpl in rendered_templates:
            rel_path = tpl.get("path", "")
            content = tpl.get("content", "")

            if not rel_path:
                continue

            full_path = os.path.join(output_dir, rel_path)

            parent = os.path.dirname(full_path)
            if parent and _ensure_directory(parent):
                parent_rel = os.path.relpath(parent, output_dir)
                if parent_rel not in created_dirs:
                    dirs_created += 1
                    created_dirs.append(parent_rel)

            bytes_written = _write_file(full_path, content)
            if bytes_written > 0:
                files_created += 1
                total_bytes += bytes_written
                created_files.append(rel_path)

    return {
        "files_created": files_created,
        "dirs_created": dirs_created,
        "total_bytes": total_bytes,
        "files": created_files,
        "dirs": created_dirs,
    }

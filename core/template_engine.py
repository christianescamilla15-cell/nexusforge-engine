"""Template Engine -- Renders Jinja2 templates with project-specific variables.

Walks template files from the blueprint and modules, replaces variables
using Jinja2 syntax, and returns rendered file contents ready for writing.
"""

import os
import glob
from typing import Any, Optional

try:
    from jinja2 import Environment, FileSystemLoader, BaseLoader, TemplateError
    HAS_JINJA2 = True
except ImportError:
    HAS_JINJA2 = False


_ENGINE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_TEMPLATES_DIR = os.path.join(_ENGINE_ROOT, "templates")


def _get_jinja_env(template_dirs: list[str]) -> Any:
    """Create a Jinja2 Environment with the given template directories.

    Args:
        template_dirs: List of directories to search for templates.

    Returns:
        Jinja2 Environment instance.

    Raises:
        ImportError: If Jinja2 is not installed.
    """
    if not HAS_JINJA2:
        raise ImportError(
            "Jinja2 is required for template rendering. "
            "Install it with: pip install Jinja2"
        )

    valid_dirs = [d for d in template_dirs if os.path.isdir(d)]
    if not valid_dirs:
        raise FileNotFoundError(
            f"No valid template directories found in: {template_dirs}"
        )

    return Environment(
        loader=FileSystemLoader(valid_dirs),
        keep_trailing_newline=True,
        trim_blocks=True,
        lstrip_blocks=True,
    )


def _render_string(template_str: str, variables: dict[str, Any]) -> str:
    """Render a Jinja2 template string with the given variables.

    Falls back to simple string replacement if Jinja2 is not available.

    Args:
        template_str: Template string with Jinja2 syntax.
        variables: Dictionary of variables to substitute.

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
        # Simple fallback: replace {{VAR}} patterns
        result = template_str
        for key, value in variables.items():
            result = result.replace("{{" + key + "}}", str(value))
            result = result.replace("{{ " + key + " }}", str(value))
        return result


def _collect_template_files(template_dirs: list[str]) -> list[dict[str, str]]:
    """Collect all .j2 template files from the given directories.

    Args:
        template_dirs: List of directories to scan for .j2 files.

    Returns:
        List of dicts with 'template_path' (absolute), 'relative_path'
        (output path without .j2 extension), and 'base_dir'.
    """
    templates = []

    for base_dir in template_dirs:
        if not os.path.isdir(base_dir):
            continue

        pattern = os.path.join(base_dir, "**", "*.j2")
        for tpl_path in sorted(glob.glob(pattern, recursive=True)):
            # Output path: strip base_dir prefix and .j2 suffix
            rel = os.path.relpath(tpl_path, base_dir)
            if rel.endswith(".j2"):
                rel = rel[:-3]

            # Convention: files named "dot-X" produce ".X" on output
            # This avoids glob/OS issues with dotfiles in templates
            basename = os.path.basename(rel)
            if basename.startswith("dot-"):
                dirname = os.path.dirname(rel)
                new_basename = "." + basename[4:]
                rel = os.path.join(dirname, new_basename) if dirname else new_basename

            templates.append({
                "template_path": tpl_path,
                "relative_path": rel,
                "base_dir": base_dir,
            })

    return templates


def _build_variables(
    specs: dict[str, Any],
    extra_variables: dict[str, Any],
) -> dict[str, Any]:
    """Build the full variables dictionary for template rendering.

    Merges spec-derived variables with user-provided extras.

    Args:
        specs: Specs dictionary from the spec generator.
        extra_variables: Additional variables to include.

    Returns:
        Merged variables dictionary.
    """
    variables: dict[str, Any] = {}

    # Extract common variables from specs
    for file_entry in specs.get("files", []):
        if file_entry.get("path") == "project_manifest.yaml":
            import yaml
            try:
                manifest = yaml.safe_load(file_entry["content"])
                if isinstance(manifest, dict):
                    project = manifest.get("project", {})
                    variables["PROJECT_NAME"] = project.get("name", "MyProject")
                    variables["PROJECT_DESCRIPTION"] = project.get("description", "")
                    variables["PROJECT_TYPE"] = project.get("type", "")

                    stack = manifest.get("stack", {})
                    variables["FRAMEWORK"] = stack.get("framework", "fastapi")
                    variables["LANGUAGE"] = stack.get("language", "python")
                    variables["DATABASE"] = stack.get("database", "postgresql")

                    # Module presence flags
                    module_ids = [m.get("id", "") for m in manifest.get("modules", [])]
                    variables["HAS_AUTH"] = "auth" in module_ids
                    variables["HAS_BILLING"] = "billing" in module_ids
                    variables["HAS_ANALYTICS"] = "analytics" in module_ids
                    variables["HAS_AI_CHAT"] = "ai_chat" in module_ids
                    variables["HAS_NOTIFICATIONS"] = "notifications" in module_ids
                    variables["HAS_CONNECTORS"] = "connectors" in module_ids
                    variables["HAS_OBSERVABILITY"] = "observability" in module_ids
                    variables["HAS_ADMIN_PANEL"] = "admin_panel" in module_ids
                    variables["MODULES"] = module_ids

                    # Env vars
                    variables["ENV_VARS"] = manifest.get("env_contract", [])
            except Exception:
                pass
            break

    # User-provided extras override everything
    variables.update(extra_variables)

    return variables


def render_templates(
    specs: dict[str, Any],
    variables: Optional[dict[str, Any]] = None,
    template_dirs: Optional[list[str]] = None,
) -> list[dict[str, str]]:
    """Render all Jinja2 templates with project-specific variables.

    Walks template files from shared templates and any additional directories,
    renders them with the merged variable set, and returns the results.

    Args:
        specs: Specs dictionary from the spec generator (used to extract
            project metadata for template variables).
        variables: Optional extra variables to merge into the template context.
            These override auto-detected values.
        template_dirs: Optional list of directories to search for templates.
            Defaults to [<engine_root>/templates/shared/].

    Returns:
        List of dicts with 'path' (relative output path) and 'content'
        (rendered string) for each template file.
    """
    extra_vars = variables or {}

    # Default template directories
    if template_dirs is None:
        template_dirs = [os.path.join(_TEMPLATES_DIR, "shared")]

    # Build variables
    all_vars = _build_variables(specs, extra_vars)

    # Collect templates
    template_files = _collect_template_files(template_dirs)

    rendered: list[dict[str, str]] = []

    for tpl_info in template_files:
        tpl_path = tpl_info["template_path"]
        out_path = tpl_info["relative_path"]

        try:
            with open(tpl_path, "r", encoding="utf-8") as f:
                template_content = f.read()

            rendered_content = _render_string(template_content, all_vars)

            rendered.append({
                "path": out_path,
                "content": rendered_content,
            })
        except Exception as exc:
            print(f"[WARNING] Failed to render template {tpl_path}: {exc}")

    return rendered

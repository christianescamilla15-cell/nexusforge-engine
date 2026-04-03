"""Spec Generator -- Generates specification files for a NexusForge project.

Produces the core project documentation and manifest:
- project_manifest.yaml -- machine-readable project definition
- requirements.md -- what the project does (functional requirements)
- design.md -- architecture and technical decisions
- tasks.md -- implementation checklist with status tracking
"""

from datetime import datetime
from typing import Any

import yaml


def _generate_manifest(
    intent: dict[str, Any],
    blueprint: dict[str, Any],
    modules: list[dict[str, Any]],
) -> str:
    """Generate the project_manifest.yaml content.

    The manifest is the single source of truth for what the project contains,
    its configuration, and its dependencies.

    Args:
        intent: Intent dictionary from the router.
        blueprint: Selected blueprint dictionary.
        modules: Ordered list of module dictionaries.

    Returns:
        YAML string of the project manifest.
    """
    # Collect all env vars from blueprint and modules, deduplicating by name
    all_env_vars: list[dict[str, Any]] = []
    seen_env_names: set[str] = set()

    for env_var in blueprint.get("env_contract", []):
        if env_var["name"] not in seen_env_names:
            all_env_vars.append(env_var)
            seen_env_names.add(env_var["name"])

    for mod in modules:
        for env_var in mod.get("env_contract", []):
            if env_var["name"] not in seen_env_names:
                all_env_vars.append(env_var)
                seen_env_names.add(env_var["name"])

    manifest = {
        "version": "1.0",
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "project": {
            "name": intent.get("project_name", blueprint.get("name", "Untitled Project")),
            "description": intent.get("description", blueprint.get("description", "")),
            "type": intent.get("project_type", blueprint.get("id", "")),
        },
        "blueprint": {
            "id": blueprint.get("id"),
            "name": blueprint.get("name"),
        },
        "stack": blueprint.get("stack", {}),
        "modules": [
            {
                "id": mod["id"],
                "name": mod.get("name", ""),
                "requires": mod.get("requires", []),
            }
            for mod in modules
        ],
        "env_contract": all_env_vars,
        "base_structure": blueprint.get("base_structure", []),
        "post_generation_hooks": blueprint.get("post_generation_hooks", []),
    }

    return yaml.dump(manifest, default_flow_style=False, sort_keys=False, allow_unicode=True)


def _generate_requirements_md(
    intent: dict[str, Any],
    blueprint: dict[str, Any],
    modules: list[dict[str, Any]],
) -> str:
    """Generate requirements.md -- functional requirements document.

    Args:
        intent: Intent dictionary from the router.
        blueprint: Selected blueprint dictionary.
        modules: Ordered list of module dictionaries.

    Returns:
        Markdown string with functional requirements.
    """
    project_name = intent.get("project_name", blueprint.get("name", "Project"))
    description = intent.get("description", blueprint.get("description", ""))

    lines = [
        f"# Requirements -- {project_name}",
        "",
        "## Overview",
        "",
        str(description).strip(),
        "",
        "## Project Type",
        "",
        f"- **Blueprint:** {blueprint.get('name', blueprint.get('id', 'N/A'))}",
        f"- **Framework:** {blueprint.get('stack', {}).get('framework', 'N/A')}",
        f"- **Language:** {blueprint.get('stack', {}).get('language', 'N/A')}",
        f"- **Database:** {blueprint.get('stack', {}).get('database', 'N/A')}",
        "",
        "## Functional Requirements",
        "",
    ]

    for i, mod in enumerate(modules, 1):
        lines.append(f"### FR-{i:03d}: {mod.get('name', mod['id'])}")
        lines.append("")
        lines.append(str(mod.get("description", "No description.")).strip())
        lines.append("")

    lines.extend([
        "## Non-Functional Requirements",
        "",
        "- **NFR-001:** All API responses must complete within 500ms for standard operations.",
        "- **NFR-002:** The system must handle at least 100 concurrent users.",
        "- **NFR-003:** All endpoints must require authentication except health checks.",
        "- **NFR-004:** Sensitive data must be encrypted at rest and in transit.",
        "- **NFR-005:** The system must log all operations with structured logging.",
        "",
        "## Environment Variables",
        "",
        "| Variable | Required | Description |",
        "|----------|----------|-------------|",
    ])

    seen: set[str] = set()
    for source in [blueprint] + modules:
        for env_var in source.get("env_contract", []):
            name = env_var.get("name", "")
            if name not in seen:
                seen.add(name)
                required = "Yes" if env_var.get("required", False) else "No"
                desc = env_var.get("description", "")
                lines.append(f"| `{name}` | {required} | {desc} |")

    lines.append("")
    return "\n".join(lines)


def _generate_design_md(
    intent: dict[str, Any],
    blueprint: dict[str, Any],
    modules: list[dict[str, Any]],
) -> str:
    """Generate design.md -- architecture and technical decisions.

    Args:
        intent: Intent dictionary from the router.
        blueprint: Selected blueprint dictionary.
        modules: Ordered list of module dictionaries.

    Returns:
        Markdown string with architecture documentation.
    """
    project_name = intent.get("project_name", blueprint.get("name", "Project"))
    stack = blueprint.get("stack", {})

    lines = [
        f"# Design Document -- {project_name}",
        "",
        "## Architecture Overview",
        "",
        "This project follows a modular monolith architecture where each feature",
        "is encapsulated in a self-contained module with clear interfaces.",
        "",
        "## Technology Stack",
        "",
        f"- **Backend Framework:** {stack.get('framework', 'N/A')}",
        f"- **Language:** {stack.get('language', 'N/A')}",
        f"- **Database:** {stack.get('database', 'N/A')}",
        f"- **State/Cache:** {stack.get('state_management', 'N/A')}",
        f"- **Task Queue:** {stack.get('queue', 'N/A')}",
        f"- **Frontend:** {stack.get('frontend', 'N/A')}",
        "",
        "## Module Architecture",
        "",
        "Each module provides:",
        "- API routes (router.py)",
        "- Data models (models.py)",
        "- Request/response schemas (schemas.py)",
        "- Business logic (service.py)",
        "",
        "### Module Dependency Graph",
        "",
        "```",
    ]

    for mod in modules:
        deps = mod.get("requires", [])
        if deps:
            lines.append(f"  {mod['id']} -> {', '.join(deps)}")
        else:
            lines.append(f"  {mod['id']} (no dependencies)")

    lines.extend([
        "```",
        "",
        "### Installed Modules",
        "",
    ])

    for mod in modules:
        desc_text = str(mod.get("description", "")).strip()[:120]
        lines.append(f"- **{mod.get('name', mod['id'])}** (`{mod['id']}`): {desc_text}")

    lines.extend([
        "",
        "## Directory Structure",
        "",
        "```",
    ])

    for d in blueprint.get("base_structure", []):
        lines.append(f"  {d}")

    lines.extend([
        "```",
        "",
        "## Design Decisions",
        "",
        "1. **Modular Monolith over Microservices:** Simpler deployment and debugging",
        "   while maintaining clean module boundaries for future extraction.",
        "2. **JWT Authentication:** Stateless auth that scales horizontally.",
        "3. **Structured Logging:** JSON logs for easy parsing in production.",
        "4. **Database Migrations:** SQL-based migrations for explicit schema control.",
        "",
    ])

    return "\n".join(lines)


def _generate_tasks_md(
    intent: dict[str, Any],
    blueprint: dict[str, Any],
    modules: list[dict[str, Any]],
) -> str:
    """Generate tasks.md -- implementation checklist.

    Args:
        intent: Intent dictionary from the router.
        blueprint: Selected blueprint dictionary.
        modules: Ordered list of module dictionaries.

    Returns:
        Markdown string with task checklist.
    """
    project_name = intent.get("project_name", blueprint.get("name", "Project"))

    lines = [
        f"# Implementation Tasks -- {project_name}",
        "",
        "## Phase 1: Project Setup",
        "",
        "- [ ] Initialize project directory structure",
        "- [ ] Configure environment variables (.env)",
        "- [ ] Install Python dependencies",
        "- [ ] Set up database and run migrations",
        "- [ ] Verify dev server starts cleanly",
        "",
        "## Phase 2: Core Modules",
        "",
    ]

    for mod in modules:
        lines.append(f"### {mod.get('name', mod['id'])}")
        lines.append("")
        for file_def in mod.get("injects", {}).get("files", []):
            path = file_def.get("path", "")
            desc = file_def.get("description", path)
            lines.append(f"- [ ] Implement `{path}` -- {desc}")
        lines.append("")

    lines.extend([
        "## Phase 3: Integration & Testing",
        "",
        "- [ ] Write unit tests for each module service layer",
        "- [ ] Write integration tests for API routes",
        "- [ ] Test module interactions (e.g., auth + billing)",
        "- [ ] Verify all environment variables are documented",
        "",
        "## Phase 4: Frontend",
        "",
        "- [ ] Set up React frontend with Vite",
        "- [ ] Implement authentication flow (login/register)",
        "- [ ] Build main dashboard page",
        "- [ ] Connect frontend to backend API",
        "",
        "## Phase 5: Deployment",
        "",
        "- [ ] Create Dockerfile and docker-compose.yaml",
        "- [ ] Configure CI/CD pipeline",
        "- [ ] Set up production environment variables",
        "- [ ] Deploy and verify health checks",
        "",
    ])

    return "\n".join(lines)


def generate_specs(
    intent: dict[str, Any],
    blueprint: dict[str, Any],
    modules: list[dict[str, Any]],
) -> dict[str, Any]:
    """Generate all specification files for a NexusForge project.

    Produces four files:
    - project_manifest.yaml -- machine-readable project definition
    - requirements.md -- functional and non-functional requirements
    - design.md -- architecture and design decisions
    - tasks.md -- implementation checklist

    Args:
        intent: Intent dictionary from the router, containing at minimum
            project_type and optionally project_name, description, and modules.
        blueprint: Selected blueprint dictionary with id, name, stack,
            base_structure, etc.
        modules: Ordered list of module dictionaries from the composer.

    Returns:
        Dictionary with a 'files' key containing a list of dicts,
        each with 'path' (relative) and 'content' (string) keys.

    Raises:
        TypeError: If any of the required arguments are not the expected type.
    """
    if not isinstance(intent, dict):
        raise TypeError(f"intent must be a dict, got {type(intent).__name__}")
    if not isinstance(blueprint, dict):
        raise TypeError(f"blueprint must be a dict, got {type(blueprint).__name__}")
    if not isinstance(modules, list):
        raise TypeError(f"modules must be a list, got {type(modules).__name__}")

    files = [
        {
            "path": "project_manifest.yaml",
            "content": _generate_manifest(intent, blueprint, modules),
        },
        {
            "path": "docs/requirements.md",
            "content": _generate_requirements_md(intent, blueprint, modules),
        },
        {
            "path": "docs/design.md",
            "content": _generate_design_md(intent, blueprint, modules),
        },
        {
            "path": "docs/tasks.md",
            "content": _generate_tasks_md(intent, blueprint, modules),
        },
    ]

    return {"files": files}

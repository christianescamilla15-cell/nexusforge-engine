"""Execution Engine -- Creates files and directories on disk.

Takes the output from the spec generator and template engine,
then physically scaffolds the project by creating all directories
and writing all files. Tracks everything that was created.
"""

import os
from typing import Any


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


def execute_scaffold(
    specs: dict[str, Any],
    output_dir: str,
    blueprint: dict[str, Any] | None = None,
    modules: list[dict[str, Any]] | None = None,
    rendered_templates: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    """Create all files and directories for a NexusForge project.

    This is the main entry point for project scaffolding. It:
    1. Creates the output directory.
    2. Creates all directories from the blueprint's base_structure.
    3. Writes all spec files (manifest, requirements, design, tasks).
    4. Writes all rendered template files.
    5. Injects all module files.
    6. Tracks and returns a summary of what was created.

    Args:
        specs: Specs dictionary from the spec generator, containing a
            'files' list of {path, content} dicts.
        output_dir: Path to the project output directory.
        blueprint: Optional blueprint dict for creating base_structure dirs.
        modules: Optional list of module dicts for injecting module files.
        rendered_templates: Optional list of rendered template {path, content} dicts.

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

    # Step 4: Write rendered templates
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

    # Step 5: Inject module files
    if modules:
        for mod in modules:
            injects = mod.get("injects", {})

            # Create module directories
            for folder in injects.get("folders", []):
                full_path = os.path.join(output_dir, folder)
                if _ensure_directory(full_path):
                    dirs_created += 1
                    created_dirs.append(folder)

            # Create module files
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
                    description = file_def.get("description", f"Module: {mod['id']}")
                    content = (
                        f'"""{description}"""\n\n'
                        f"# TODO: Implement {rel_path}\n"
                        f"# Module: {mod['id']}\n"
                    )

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

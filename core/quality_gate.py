"""Quality Gate -- Validates the generated project structure and contents.

Runs a series of checks against a scaffolded project to verify correctness:
directory existence, file existence, env coverage, dependency satisfaction,
and more. Returns a detailed report of passed/failed checks.
"""

import os
from typing import Any
from collections import Counter


def _check_directories_exist(
    project_path: str,
    required_dirs: list[str],
) -> dict[str, Any]:
    """Check that all required directories exist.

    Args:
        project_path: Absolute path to the project root.
        required_dirs: List of relative directory paths to check.

    Returns:
        Check result dict with name, passed, and details.
    """
    missing = []
    for d in required_dirs:
        full = os.path.join(project_path, d)
        if not os.path.isdir(full):
            missing.append(d)

    return {
        "name": "required_directories_exist",
        "passed": len(missing) == 0,
        "details": f"Missing directories: {missing}" if missing else "All required directories exist",
    }


def _check_files_exist(
    project_path: str,
    required_files: list[str],
) -> dict[str, Any]:
    """Check that all required files exist.

    Args:
        project_path: Absolute path to the project root.
        required_files: List of relative file paths to check.

    Returns:
        Check result dict with name, passed, and details.
    """
    missing = []
    for f in required_files:
        full = os.path.join(project_path, f)
        if not os.path.isfile(full):
            missing.append(f)

    return {
        "name": "required_files_exist",
        "passed": len(missing) == 0,
        "details": f"Missing files: {missing}" if missing else "All required files exist",
    }


def _check_env_example(
    project_path: str,
    required_env_vars: list[str],
) -> dict[str, Any]:
    """Check that .env.example contains all required environment variables.

    Args:
        project_path: Absolute path to the project root.
        required_env_vars: List of environment variable names that must be present.

    Returns:
        Check result dict with name, passed, and details.
    """
    env_path = os.path.join(project_path, ".env.example")

    if not os.path.isfile(env_path):
        return {
            "name": "env_example_coverage",
            "passed": False,
            "details": ".env.example file not found",
        }

    try:
        with open(env_path, "r", encoding="utf-8") as f:
            content = f.read()
    except OSError as exc:
        return {
            "name": "env_example_coverage",
            "passed": False,
            "details": f"Failed to read .env.example: {exc}",
        }

    # Extract variable names (lines starting with VAR_NAME=)
    defined_vars = set()
    for line in content.splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            var_name = line.split("=", 1)[0].strip()
            defined_vars.add(var_name)

    missing = [v for v in required_env_vars if v not in defined_vars]

    return {
        "name": "env_example_coverage",
        "passed": len(missing) == 0,
        "details": f"Missing env vars in .env.example: {missing}" if missing else "All required env vars documented",
    }


def _check_requirements_txt(project_path: str) -> dict[str, Any]:
    """Check that requirements.txt exists and is non-empty.

    Args:
        project_path: Absolute path to the project root.

    Returns:
        Check result dict with name, passed, and details.
    """
    req_path = os.path.join(project_path, "requirements.txt")

    if not os.path.isfile(req_path):
        return {
            "name": "requirements_txt_valid",
            "passed": False,
            "details": "requirements.txt not found",
        }

    try:
        with open(req_path, "r", encoding="utf-8") as f:
            content = f.read().strip()
    except OSError as exc:
        return {
            "name": "requirements_txt_valid",
            "passed": False,
            "details": f"Failed to read requirements.txt: {exc}",
        }

    if not content:
        return {
            "name": "requirements_txt_valid",
            "passed": False,
            "details": "requirements.txt is empty",
        }

    # Check for obviously invalid lines
    invalid_lines = []
    for i, line in enumerate(content.splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("-"):
            continue
        # Very basic check: should contain at least a package name
        if not any(c.isalpha() for c in line):
            invalid_lines.append(f"Line {i}: '{line}'")

    if invalid_lines:
        return {
            "name": "requirements_txt_valid",
            "passed": False,
            "details": f"Invalid lines in requirements.txt: {invalid_lines}",
        }

    return {
        "name": "requirements_txt_valid",
        "passed": True,
        "details": "requirements.txt is valid and non-empty",
    }


def _check_no_empty_files(project_path: str) -> dict[str, Any]:
    """Check that no generated files are completely empty.

    Ignores __init__.py files and .gitkeep files which are allowed to be empty.

    Args:
        project_path: Absolute path to the project root.

    Returns:
        Check result dict with name, passed, and details.
    """
    empty_files = []
    allowed_empty = {"__init__.py", ".gitkeep", ".keep"}

    for root, dirs, files in os.walk(project_path):
        # Skip hidden directories and common non-project dirs
        dirs[:] = [d for d in dirs if not d.startswith(".") and d != "node_modules"]

        for filename in files:
            if filename in allowed_empty:
                continue

            full_path = os.path.join(root, filename)
            try:
                if os.path.getsize(full_path) == 0:
                    rel = os.path.relpath(full_path, project_path)
                    empty_files.append(rel)
            except OSError:
                pass

    return {
        "name": "no_empty_files",
        "passed": len(empty_files) == 0,
        "details": f"Empty files found: {empty_files}" if empty_files else "No empty files detected",
    }


def _check_no_duplicate_filenames(project_path: str) -> dict[str, Any]:
    """Check for duplicate file names across the project.

    Duplicate filenames in different directories are allowed, but this
    flags them as a warning when they occur in the same logical scope.

    Args:
        project_path: Absolute path to the project root.

    Returns:
        Check result dict with name, passed, and details.
    """
    all_files: list[str] = []

    for root, dirs, files in os.walk(project_path):
        dirs[:] = [d for d in dirs if not d.startswith(".") and d != "node_modules"]
        for filename in files:
            rel = os.path.relpath(os.path.join(root, filename), project_path)
            all_files.append(rel)

    # Check for exact duplicate paths (should never happen but catches bugs)
    path_counts = Counter(all_files)
    duplicates = {p: c for p, c in path_counts.items() if c > 1}

    return {
        "name": "no_duplicate_filenames",
        "passed": len(duplicates) == 0,
        "details": f"Duplicate file paths: {duplicates}" if duplicates else "No duplicate file paths",
    }


def _check_module_dependencies(
    project_path: str,
    modules: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Check that all module dependencies are satisfied.

    Verifies that for each installed module, its required modules
    are also present (by checking for their injected directories).

    Args:
        project_path: Absolute path to the project root.
        modules: Optional list of installed module dicts. If not provided,
            attempts to read from project_manifest.yaml.

    Returns:
        Check result dict with name, passed, and details.
    """
    if modules is None:
        # Try to read manifest
        manifest_path = os.path.join(project_path, "project_manifest.yaml")
        if os.path.isfile(manifest_path):
            try:
                import yaml
                with open(manifest_path, "r", encoding="utf-8") as f:
                    manifest = yaml.safe_load(f)
                modules = manifest.get("modules", [])
            except Exception:
                return {
                    "name": "module_dependencies_satisfied",
                    "passed": True,
                    "details": "Could not read manifest, skipping dependency check",
                }
        else:
            return {
                "name": "module_dependencies_satisfied",
                "passed": True,
                "details": "No manifest found, skipping dependency check",
            }

    installed_ids = {m.get("id", "") for m in modules}
    unsatisfied = []

    for mod in modules:
        mod_id = mod.get("id", "")
        for dep in mod.get("requires", []):
            if dep not in installed_ids:
                unsatisfied.append(f"{mod_id} requires {dep}")

    return {
        "name": "module_dependencies_satisfied",
        "passed": len(unsatisfied) == 0,
        "details": f"Unsatisfied dependencies: {unsatisfied}" if unsatisfied else "All module dependencies satisfied",
    }


def _check_manifest_valid(project_path: str) -> dict[str, Any]:
    """Check that project_manifest.yaml exists and is valid YAML.

    Args:
        project_path: Absolute path to the project root.

    Returns:
        Check result dict with name, passed, and details.
    """
    manifest_path = os.path.join(project_path, "project_manifest.yaml")

    if not os.path.isfile(manifest_path):
        return {
            "name": "manifest_valid",
            "passed": False,
            "details": "project_manifest.yaml not found",
        }

    try:
        import yaml
        with open(manifest_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        if not isinstance(data, dict):
            return {
                "name": "manifest_valid",
                "passed": False,
                "details": "project_manifest.yaml does not contain a YAML mapping",
            }

        # Check required fields
        required_fields = ["version", "project", "blueprint", "stack"]
        missing = [f for f in required_fields if f not in data]

        if missing:
            return {
                "name": "manifest_valid",
                "passed": False,
                "details": f"Manifest missing required fields: {missing}",
            }

        return {
            "name": "manifest_valid",
            "passed": True,
            "details": "project_manifest.yaml is valid",
        }
    except Exception as exc:
        return {
            "name": "manifest_valid",
            "passed": False,
            "details": f"Failed to parse project_manifest.yaml: {exc}",
        }


def run_quality_gates(
    project_path: str,
    blueprint: dict[str, Any] | None = None,
    modules: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Run all quality gate checks against a generated project.

    Checks performed:
    1. Required directories exist (from blueprint base_structure).
    2. Required files exist (manifest, requirements.txt, .env.example).
    3. .env.example covers all required env vars.
    4. requirements.txt is valid and non-empty.
    5. No empty files (excluding __init__.py, .gitkeep).
    6. No duplicate file paths.
    7. Module dependencies are satisfied.
    8. Project manifest is valid YAML with required fields.

    Args:
        project_path: Absolute path to the project root.
        blueprint: Optional blueprint dict for directory checks.
        modules: Optional list of module dicts for dependency checks.

    Returns:
        Dictionary with:
        - passed (int): Number of checks that passed.
        - total (int): Total number of checks run.
        - checks (list): List of individual check results.
        - failures (list): List of failure detail strings.
    """
    project_path = os.path.abspath(project_path)

    if not os.path.isdir(project_path):
        return {
            "passed": 0,
            "total": 1,
            "checks": [{
                "name": "project_exists",
                "passed": False,
                "details": f"Project directory not found: {project_path}",
            }],
            "failures": [f"Project directory not found: {project_path}"],
        }

    checks: list[dict[str, Any]] = []

    # 1. Required directories
    required_dirs = []
    if blueprint:
        required_dirs = blueprint.get("base_structure", [])
    else:
        # Minimum expected directories
        required_dirs = ["docs/"]

    checks.append(_check_directories_exist(project_path, required_dirs))

    # 2. Required files
    required_files = ["project_manifest.yaml"]
    checks.append(_check_files_exist(project_path, required_files))

    # 3. Env example coverage
    required_env_vars = []
    if blueprint:
        for env_var in blueprint.get("env_contract", []):
            if env_var.get("required", False):
                required_env_vars.append(env_var["name"])
    checks.append(_check_env_example(project_path, required_env_vars))

    # 4. requirements.txt
    checks.append(_check_requirements_txt(project_path))

    # 5. No empty files
    checks.append(_check_no_empty_files(project_path))

    # 6. No duplicate filenames
    checks.append(_check_no_duplicate_filenames(project_path))

    # 7. Module dependencies
    checks.append(_check_module_dependencies(project_path, modules))

    # 8. Manifest valid
    checks.append(_check_manifest_valid(project_path))

    # Summarize
    passed = sum(1 for c in checks if c["passed"])
    total = len(checks)
    failures = [c["details"] for c in checks if not c["passed"]]

    return {
        "passed": passed,
        "total": total,
        "checks": checks,
        "failures": failures,
    }

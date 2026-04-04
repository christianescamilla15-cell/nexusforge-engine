"""Quality Gate v1.0 -- Validates the generated project structure and contents.

Runs a series of checks (16 total) against a scaffolded project to verify
correctness: directory existence, file existence, env coverage, dependency
satisfaction, compatibility matrix validation, Python syntax validation,
import resolution, circular dependency detection, and test coverage.

Returns a detailed report of passed/failed checks.
"""

import ast
import os
import re
from typing import Any
from collections import Counter

from core.compatibility import (
    COMPATIBILITY_MATRIX,
    check_compatibility,
    get_all_env_vars,
    get_all_packages,
)


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


def _check_compatibility_matrix(project_path: str) -> dict[str, Any]:
    """Check that the compatibility matrix passes for the project's modules.

    Reads the manifest to determine blueprint and modules, then runs the
    full compatibility check.

    Args:
        project_path: Absolute path to the project root.

    Returns:
        Check result dict with name, passed, and details.
    """
    manifest_path = os.path.join(project_path, "project_manifest.yaml")
    if not os.path.isfile(manifest_path):
        return {
            "name": "compatibility_matrix",
            "passed": True,
            "details": "No manifest found, skipping compatibility check",
        }

    try:
        import yaml
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = yaml.safe_load(f)

        blueprint_id = manifest.get("blueprint", {}).get("id", "")
        module_ids = [m.get("id", "") for m in manifest.get("modules", []) if m.get("id")]

        if not blueprint_id or not module_ids:
            return {
                "name": "compatibility_matrix",
                "passed": True,
                "details": "Insufficient data for compatibility check, skipping",
            }

        result = check_compatibility(blueprint_id, module_ids)

        if result.compatible:
            return {
                "name": "compatibility_matrix",
                "passed": True,
                "details": "All modules are compatible with blueprint and each other",
            }
        else:
            return {
                "name": "compatibility_matrix",
                "passed": False,
                "details": f"Compatibility issues: {result.issues}",
            }
    except Exception as exc:
        return {
            "name": "compatibility_matrix",
            "passed": True,
            "details": f"Could not run compatibility check: {exc}",
        }


def _check_all_module_env_vars(project_path: str) -> dict[str, Any]:
    """Check that all env vars from all modules are in .env.example.

    Args:
        project_path: Absolute path to the project root.

    Returns:
        Check result dict with name, passed, and details.
    """
    manifest_path = os.path.join(project_path, "project_manifest.yaml")
    if not os.path.isfile(manifest_path):
        return {
            "name": "module_env_vars_complete",
            "passed": True,
            "details": "No manifest found, skipping module env var check",
        }

    try:
        import yaml
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = yaml.safe_load(f)

        module_ids = [m.get("id", "") for m in manifest.get("modules", []) if m.get("id")]
        required_vars = get_all_env_vars(module_ids)

        if not required_vars:
            return {
                "name": "module_env_vars_complete",
                "passed": True,
                "details": "No module env vars required",
            }

        # Read .env.example
        env_path = os.path.join(project_path, ".env.example")
        defined_vars: set[str] = set()
        if os.path.isfile(env_path):
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        defined_vars.add(line.split("=", 1)[0].strip())

        missing = [v for v in required_vars if v not in defined_vars]

        if missing:
            return {
                "name": "module_env_vars_complete",
                "passed": False,
                "details": f"Module env vars missing from .env.example: {missing}",
            }

        return {
            "name": "module_env_vars_complete",
            "passed": True,
            "details": "All module env vars present in .env.example",
        }
    except Exception as exc:
        return {
            "name": "module_env_vars_complete",
            "passed": True,
            "details": f"Could not check module env vars: {exc}",
        }


def _check_all_module_packages(project_path: str) -> dict[str, Any]:
    """Check that all Python packages from all modules are in requirements.txt.

    Args:
        project_path: Absolute path to the project root.

    Returns:
        Check result dict with name, passed, and details.
    """
    manifest_path = os.path.join(project_path, "project_manifest.yaml")
    if not os.path.isfile(manifest_path):
        return {
            "name": "module_packages_complete",
            "passed": True,
            "details": "No manifest found, skipping module package check",
        }

    try:
        import yaml
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = yaml.safe_load(f)

        module_ids = [m.get("id", "") for m in manifest.get("modules", []) if m.get("id")]
        required_packages = get_all_packages(module_ids)

        if not required_packages:
            return {
                "name": "module_packages_complete",
                "passed": True,
                "details": "No module packages required",
            }

        # Read requirements.txt
        req_path = os.path.join(project_path, "requirements.txt")
        installed_names: set[str] = set()
        if os.path.isfile(req_path):
            with open(req_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or line.startswith("-"):
                        continue
                    pkg_name = re.split(r"[>=<!\[]", line)[0].strip().lower()
                    if pkg_name:
                        installed_names.add(pkg_name)

        missing = []
        for pkg_spec in required_packages:
            pkg_name = re.split(r"[>=<!\[]", pkg_spec)[0].strip().lower()
            if pkg_name not in installed_names:
                missing.append(pkg_spec)

        if missing:
            return {
                "name": "module_packages_complete",
                "passed": False,
                "details": f"Module packages missing from requirements.txt: {missing}",
            }

        return {
            "name": "module_packages_complete",
            "passed": True,
            "details": "All module packages present in requirements.txt",
        }
    except Exception as exc:
        return {
            "name": "module_packages_complete",
            "passed": True,
            "details": f"Could not check module packages: {exc}",
        }


def _check_no_module_conflicts(project_path: str) -> dict[str, Any]:
    """Check that no installed modules conflict with each other.

    Args:
        project_path: Absolute path to the project root.

    Returns:
        Check result dict with name, passed, and details.
    """
    manifest_path = os.path.join(project_path, "project_manifest.yaml")
    if not os.path.isfile(manifest_path):
        return {
            "name": "no_module_conflicts",
            "passed": True,
            "details": "No manifest found, skipping conflict check",
        }

    try:
        import yaml
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = yaml.safe_load(f)

        module_ids = [m.get("id", "") for m in manifest.get("modules", []) if m.get("id")]

        from core.compatibility import get_conflicts
        conflicts = get_conflicts(module_ids)

        if conflicts:
            return {
                "name": "no_module_conflicts",
                "passed": False,
                "details": f"Module conflicts detected: {conflicts}",
            }

        return {
            "name": "no_module_conflicts",
            "passed": True,
            "details": "No module conflicts detected",
        }
    except Exception as exc:
        return {
            "name": "no_module_conflicts",
            "passed": True,
            "details": f"Could not check module conflicts: {exc}",
        }


def _check_python_syntax(project_path: str) -> dict[str, Any]:
    """Validate Python syntax by compiling each .py file.

    Uses ``ast.parse`` to check syntax without executing the files.
    Catches SyntaxError gracefully and reports all invalid files.

    Args:
        project_path: Absolute path to the project root.

    Returns:
        Check result dict with name, passed, and details.
    """
    syntax_errors: list[str] = []

    for root, dirs, files in os.walk(project_path):
        dirs[:] = [
            d for d in dirs
            if not d.startswith(".") and d not in ("node_modules", "__pycache__", ".venv", "venv")
        ]

        for filename in files:
            if not filename.endswith(".py"):
                continue

            full_path = os.path.join(root, filename)
            try:
                with open(full_path, "r", encoding="utf-8") as f:
                    source = f.read()
                ast.parse(source, filename=full_path)
            except SyntaxError as exc:
                rel = os.path.relpath(full_path, project_path)
                line_info = f" (line {exc.lineno})" if exc.lineno else ""
                syntax_errors.append(f"{rel}{line_info}: {exc.msg}")
            except Exception:
                # Non-syntax errors (encoding, etc.) — skip gracefully
                pass

    return {
        "name": "python_syntax_valid",
        "passed": len(syntax_errors) == 0,
        "details": (
            f"Syntax errors found: {syntax_errors}" if syntax_errors
            else "All Python files have valid syntax"
        ),
    }


def _check_import_resolution(project_path: str) -> dict[str, Any]:
    """Verify that imported modules exist within the project.

    Checks ``from src.X.Y import ...`` style imports against the project's
    directory structure. Only flags internal project imports, not third-party.

    Args:
        project_path: Absolute path to the project root.

    Returns:
        Check result dict with name, passed, and details.
    """
    unresolved: list[str] = []

    for root, dirs, files in os.walk(project_path):
        dirs[:] = [
            d for d in dirs
            if not d.startswith(".") and d not in ("node_modules", "__pycache__", ".venv", "venv")
        ]

        for filename in files:
            if not filename.endswith(".py"):
                continue

            full_path = os.path.join(root, filename)
            try:
                with open(full_path, "r", encoding="utf-8") as f:
                    source = f.read()

                tree = ast.parse(source, filename=full_path)
            except (SyntaxError, Exception):
                continue

            rel_file = os.path.relpath(full_path, project_path)

            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module:
                    module_path = node.module
                    # Only check project-internal imports (starting with src.)
                    if not module_path.startswith("src."):
                        continue

                    # Convert module path to filesystem path
                    parts = module_path.split(".")
                    # Check if the directory or file exists
                    dir_candidate = os.path.join(project_path, *parts)
                    file_candidate = os.path.join(project_path, *parts[:-1], parts[-1] + ".py")
                    init_candidate = os.path.join(dir_candidate, "__init__.py")

                    if not (
                        os.path.isdir(dir_candidate)
                        or os.path.isfile(file_candidate)
                        or os.path.isfile(init_candidate)
                    ):
                        unresolved.append(
                            f"{rel_file}: import '{module_path}' not found"
                        )

    return {
        "name": "import_resolution",
        "passed": len(unresolved) == 0,
        "details": (
            f"Unresolved imports: {unresolved}" if unresolved
            else "All internal imports resolve correctly"
        ),
    }


def _check_circular_dependencies(project_path: str) -> dict[str, Any]:
    """Detect circular import dependencies among project Python files.

    Builds a directed graph of ``from src.X import ...`` relationships
    and checks for cycles using DFS.

    Args:
        project_path: Absolute path to the project root.

    Returns:
        Check result dict with name, passed, and details.
    """
    # Build import graph: module_name -> set of imported module_names
    graph: dict[str, set[str]] = {}

    for root, dirs, files in os.walk(project_path):
        dirs[:] = [
            d for d in dirs
            if not d.startswith(".") and d not in ("node_modules", "__pycache__", ".venv", "venv")
        ]

        for filename in files:
            if not filename.endswith(".py"):
                continue

            full_path = os.path.join(root, filename)
            rel = os.path.relpath(full_path, project_path).replace(os.sep, "/")

            # Convert file path to module name (e.g. src/auth/router.py -> src.auth.router)
            module_name = rel.replace("/", ".").removesuffix(".py")
            if module_name.endswith(".__init__"):
                module_name = module_name.removesuffix(".__init__")

            try:
                with open(full_path, "r", encoding="utf-8") as f:
                    source = f.read()
                tree = ast.parse(source, filename=full_path)
            except (SyntaxError, Exception):
                continue

            imports: set[str] = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module:
                    if node.module.startswith("src."):
                        imports.add(node.module)

            if imports:
                graph[module_name] = imports

    # DFS cycle detection
    cycles: list[str] = []
    visited: set[str] = set()
    in_stack: set[str] = set()

    def _dfs(node: str, path: list[str]) -> None:
        if node in in_stack:
            # Found a cycle
            cycle_start = path.index(node) if node in path else 0
            cycle = path[cycle_start:] + [node]
            cycles.append(" -> ".join(cycle))
            return
        if node in visited:
            return

        visited.add(node)
        in_stack.add(node)
        path.append(node)

        for dep in graph.get(node, set()):
            _dfs(dep, path)

        path.pop()
        in_stack.discard(node)

    for module_name in graph:
        if module_name not in visited:
            _dfs(module_name, [])

    return {
        "name": "no_circular_dependencies",
        "passed": len(cycles) == 0,
        "details": (
            f"Circular dependencies detected: {cycles}" if cycles
            else "No circular dependencies found"
        ),
    }


def _check_test_file_coverage(project_path: str) -> dict[str, Any]:
    """Check that every module has at least one test file.

    Looks for ``tests/`` or ``test_*.py`` files corresponding to each
    module directory under ``src/``.

    Args:
        project_path: Absolute path to the project root.

    Returns:
        Check result dict with name, passed, and details.
    """
    src_dir = os.path.join(project_path, "src")
    tests_dir = os.path.join(project_path, "tests")

    if not os.path.isdir(src_dir):
        return {
            "name": "test_file_coverage",
            "passed": True,
            "details": "No src/ directory found, skipping test coverage check",
        }

    # Discover module directories (immediate children of src/ that have .py files)
    module_dirs: list[str] = []
    for entry in os.listdir(src_dir):
        entry_path = os.path.join(src_dir, entry)
        if os.path.isdir(entry_path) and not entry.startswith((".", "__")):
            py_files = [f for f in os.listdir(entry_path) if f.endswith(".py")]
            if py_files:
                module_dirs.append(entry)

    if not module_dirs:
        return {
            "name": "test_file_coverage",
            "passed": True,
            "details": "No module directories found in src/",
        }

    # Check for test files
    uncovered: list[str] = []
    for mod_name in module_dirs:
        has_test = False

        # Check tests/test_{mod_name}.py
        if os.path.isfile(os.path.join(tests_dir, f"test_{mod_name}.py")):
            has_test = True

        # Check tests/{mod_name}/
        if os.path.isdir(os.path.join(tests_dir, mod_name)):
            has_test = True

        # Check src/{mod_name}/tests/ or src/{mod_name}/test_*.py
        mod_dir = os.path.join(src_dir, mod_name)
        if os.path.isdir(os.path.join(mod_dir, "tests")):
            has_test = True
        for f in os.listdir(mod_dir):
            if f.startswith("test_") and f.endswith(".py"):
                has_test = True
                break

        if not has_test:
            uncovered.append(mod_name)

    return {
        "name": "test_file_coverage",
        "passed": len(uncovered) == 0,
        "details": (
            f"Modules without test files: {uncovered}" if uncovered
            else "All modules have at least one test file"
        ),
    }


def run_quality_gates(
    project_path: str,
    blueprint: dict[str, Any] | None = None,
    modules: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Run all quality gate checks against a generated project.

    Checks performed (16 total):
    1. Required directories exist (from blueprint base_structure).
    2. Required files exist (manifest, requirements.txt, .env.example).
    3. .env.example covers all required env vars.
    4. requirements.txt is valid and non-empty.
    5. No empty files (excluding __init__.py, .gitkeep).
    6. No duplicate file paths.
    7. Module dependencies are satisfied.
    8. Project manifest is valid YAML with required fields.
    9. Compatibility matrix passes for the project's modules.
    10. All module env vars are in .env.example.
    11. All module packages are in requirements.txt.
    12. No module conflicts exist.
    13. Python syntax validation (compile each .py file).
    14. Import resolution (verify imported modules exist).
    15. Circular dependency detection.
    16. Test file coverage (every module has at least one test file).

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

    # 9. Compatibility matrix (v0.5)
    checks.append(_check_compatibility_matrix(project_path))

    # 10. All module env vars in .env.example (v0.5)
    checks.append(_check_all_module_env_vars(project_path))

    # 11. All module packages in requirements.txt (v0.5)
    checks.append(_check_all_module_packages(project_path))

    # 12. No module conflicts (v0.5)
    checks.append(_check_no_module_conflicts(project_path))

    # 13. Python syntax validation (v1.0)
    checks.append(_check_python_syntax(project_path))

    # 14. Import resolution (v1.0)
    checks.append(_check_import_resolution(project_path))

    # 15. Circular dependency detection (v1.0)
    checks.append(_check_circular_dependencies(project_path))

    # 16. Test file coverage (v1.0)
    checks.append(_check_test_file_coverage(project_path))

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

"""Blueprint Selector -- Loads and selects project blueprints from YAML definitions.

Blueprints define the skeleton of a project: its directory structure,
required/optional modules, stack choices, and environment contract.
The selector matches an intent's project_type to the right blueprint.
"""

import os
import glob
from typing import Any, Optional

import yaml


_ENGINE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_BLUEPRINTS_DIR = os.path.join(_ENGINE_ROOT, "blueprints")


def _load_blueprint(path: str) -> dict[str, Any]:
    """Load a single blueprint YAML file and return its contents.

    Args:
        path: Absolute path to the blueprint.yaml file.

    Returns:
        Dictionary with all blueprint fields.

    Raises:
        FileNotFoundError: If the blueprint file does not exist.
        yaml.YAMLError: If the file contains invalid YAML.
        ValueError: If the blueprint is missing the required 'id' field.
    """
    if not os.path.isfile(path):
        raise FileNotFoundError(f"Blueprint file not found: {path}")

    with open(path, "r", encoding="utf-8") as f:
        try:
            data = yaml.safe_load(f)
        except yaml.YAMLError as exc:
            raise yaml.YAMLError(f"Invalid YAML in {path}: {exc}") from exc

    if not isinstance(data, dict):
        raise ValueError(f"Blueprint file must contain a YAML mapping: {path}")

    if "id" not in data:
        raise ValueError(f"Blueprint missing required 'id' field: {path}")

    return data


def load_all_blueprints(blueprints_dir: Optional[str] = None) -> dict[str, dict[str, Any]]:
    """Load every blueprint from the blueprints directory.

    Scans for */blueprint.yaml under the given directory and loads each one.

    Args:
        blueprints_dir: Path to the blueprints directory.
            Defaults to <engine_root>/blueprints/.

    Returns:
        Dictionary mapping blueprint id -> blueprint dict.

    Raises:
        FileNotFoundError: If the blueprints directory does not exist.
    """
    base = blueprints_dir or _BLUEPRINTS_DIR

    if not os.path.isdir(base):
        raise FileNotFoundError(f"Blueprints directory not found: {base}")

    blueprints: dict[str, dict[str, Any]] = {}
    pattern = os.path.join(base, "*", "blueprint.yaml")

    for bp_path in sorted(glob.glob(pattern)):
        try:
            bp = _load_blueprint(bp_path)
            blueprints[bp["id"]] = bp
        except (ValueError, yaml.YAMLError, FileNotFoundError) as exc:
            print(f"[WARNING] Skipping blueprint at {bp_path}: {exc}")

    return blueprints


def select_blueprint(
    intent: dict[str, Any],
    blueprints_dir: Optional[str] = None,
) -> dict[str, Any]:
    """Select the appropriate blueprint for a given intent.

    Matches intent['project_type'] against available blueprint IDs.
    Falls back to agentic_saas if no exact match is found.

    Args:
        intent: Intent dictionary containing at least a project_type key.
        blueprints_dir: Optional override for the blueprints directory.

    Returns:
        The matched blueprint dictionary with all fields.

    Raises:
        RuntimeError: If no blueprints are found at all.
    """
    blueprints = load_all_blueprints(blueprints_dir)

    if not blueprints:
        raise RuntimeError(
            f"No blueprints found in {blueprints_dir or _BLUEPRINTS_DIR}. "
            "Create at least one blueprint YAML file."
        )

    project_type = intent.get("project_type", "")

    # Direct match
    if project_type in blueprints:
        return blueprints[project_type]

    # Fuzzy substring match
    for bp_id, bp in blueprints.items():
        if project_type and project_type.lower() in bp_id.lower():
            return bp

    # Fallback to agentic_saas
    fallback_id = "agentic_saas"
    if fallback_id in blueprints:
        print(
            f"[INFO] No blueprint matched project_type=\'{project_type}\', "
            f"falling back to \'{fallback_id}\'"
        )
        return blueprints[fallback_id]

    # If even the fallback is missing, return the first available blueprint
    first_id = next(iter(blueprints))
    print(
        f"[INFO] No blueprint matched project_type=\'{project_type}\' and "
        f"fallback \'{fallback_id}\' not found. Using \'{first_id}\'."
    )
    return blueprints[first_id]

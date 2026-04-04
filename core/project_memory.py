"""Project Memory v1.0 — Persistent memory across projects and sessions.

Stores learned patterns, user preferences, and project history to provide
intelligent suggestions for future project generation.

Memory is stored in ``~/.nexusforge/memory.json`` and is opt-out
(disabled when ``--no-telemetry`` is passed).
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any


_DEFAULT_MEMORY_PATH = os.path.join(os.path.expanduser("~"), ".nexusforge", "memory.json")

# Default structure for a fresh memory file
_EMPTY_MEMORY: dict[str, Any] = {
    "version": "1.0",
    "projects": [],
    "preferences": {
        "preferred_stack": "",
        "default_modules": [],
        "naming_convention": "",
    },
    "module_usage": {},
    "repair_patterns": [],
    "type_frequency": {},
}


class ProjectMemory:
    """Stores learned patterns, user preferences, and project history.

    Args:
        memory_path: Path to the memory JSON file.
            Defaults to ``~/.nexusforge/memory.json``.
        enabled: If False, all write operations are silently skipped.
    """

    def __init__(
        self,
        memory_path: str = _DEFAULT_MEMORY_PATH,
        enabled: bool = True,
    ) -> None:
        self.memory_path: str = os.path.expanduser(memory_path)
        self.enabled: bool = enabled
        self._data: dict[str, Any] | None = None

    def _load(self) -> dict[str, Any]:
        """Load memory from disk, caching in memory.

        Returns:
            The full memory dictionary.
        """
        if self._data is not None:
            return self._data

        if not os.path.isfile(self.memory_path):
            self._data = dict(_EMPTY_MEMORY)
            return self._data

        try:
            with open(self.memory_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                self._data = dict(_EMPTY_MEMORY)
            else:
                # Merge with defaults for forward-compatibility
                merged = dict(_EMPTY_MEMORY)
                merged.update(data)
                self._data = merged
        except Exception:
            self._data = dict(_EMPTY_MEMORY)

        return self._data

    def _save(self) -> None:
        """Persist memory to disk."""
        if not self.enabled:
            return

        data = self._load()
        try:
            os.makedirs(os.path.dirname(self.memory_path), exist_ok=True)
            with open(self.memory_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except OSError:
            pass  # Non-critical

    def remember_project(self, manifest: dict[str, Any], result: dict[str, Any]) -> None:
        """Record a completed project generation for future reference.

        Args:
            manifest: The project manifest dict (project type, modules, stack, etc.).
            result: The execution result (files created, quality gate results, etc.).
        """
        if not self.enabled:
            return

        data = self._load()

        project_type = manifest.get("project", {}).get("type", "")
        modules = [m.get("id", "") for m in manifest.get("modules", []) if m.get("id")]
        stack = manifest.get("stack", {}).get("framework", "fastapi")

        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "project_type": project_type,
            "stack": stack,
            "modules": modules,
            "files_created": result.get("files_created", 0),
            "quality_passed": result.get("quality_passed", 0),
            "quality_total": result.get("quality_total", 0),
        }

        data["projects"].append(record)

        # Keep last 50 projects
        if len(data["projects"]) > 50:
            data["projects"] = data["projects"][-50:]

        # Update module usage counts
        for mod in modules:
            data["module_usage"][mod] = data["module_usage"].get(mod, 0) + 1

        # Update type frequency
        if project_type:
            data["type_frequency"][project_type] = data["type_frequency"].get(project_type, 0) + 1

        # Auto-learn preferred stack
        if not data["preferences"]["preferred_stack"]:
            data["preferences"]["preferred_stack"] = stack

        self._save()

    def get_user_preferences(self) -> dict[str, Any]:
        """Return the current user preferences.

        Returns:
            Preferences dict with ``preferred_stack``, ``default_modules``,
            and ``naming_convention``.
        """
        data = self._load()
        return dict(data.get("preferences", _EMPTY_MEMORY["preferences"]))

    def set_preference(self, key: str, value: Any) -> None:
        """Update a single user preference.

        Args:
            key: Preference key (e.g. ``"preferred_stack"``).
            value: The new value.
        """
        if not self.enabled:
            return

        data = self._load()
        data.setdefault("preferences", {})
        data["preferences"][key] = value
        self._save()

    def suggest_modules(self, project_type: str) -> list[str]:
        """Suggest modules based on past projects of the same type.

        Recommends modules that the user chose in >50% of past projects
        with the same type.

        Args:
            project_type: The project type to match against.

        Returns:
            Sorted list of suggested module IDs.
        """
        data = self._load()
        projects = data.get("projects", [])

        # Filter by type
        matching = [p for p in projects if p.get("project_type") == project_type]
        if not matching:
            return []

        module_counts: dict[str, int] = {}
        for proj in matching:
            for mod in proj.get("modules", []):
                module_counts[mod] = module_counts.get(mod, 0) + 1

        threshold = max(1, len(matching) // 2)
        suggestions = [
            mod for mod, count in sorted(module_counts.items(), key=lambda x: -x[1])
            if count >= threshold
        ]

        return suggestions

    def get_common_patterns(self, project_type: str) -> dict[str, Any]:
        """Analyze past projects of a type for common patterns.

        Args:
            project_type: The project type to analyze.

        Returns:
            Dict with ``common_modules``, ``avg_files``, ``avg_quality_rate``,
            and ``total_projects``.
        """
        data = self._load()
        projects = data.get("projects", [])

        matching = [p for p in projects if p.get("project_type") == project_type]
        if not matching:
            return {
                "common_modules": [],
                "avg_files": 0,
                "avg_quality_rate": 0.0,
                "total_projects": 0,
            }

        module_counts: dict[str, int] = {}
        total_files = 0
        quality_rates: list[float] = []

        for proj in matching:
            for mod in proj.get("modules", []):
                module_counts[mod] = module_counts.get(mod, 0) + 1
            total_files += proj.get("files_created", 0)

            total_qg = proj.get("quality_total", 0)
            if total_qg > 0:
                quality_rates.append(proj.get("quality_passed", 0) / total_qg)

        threshold = max(1, len(matching) // 2)
        common_modules = [
            mod for mod, count in sorted(module_counts.items(), key=lambda x: -x[1])
            if count >= threshold
        ]

        avg_files = int(total_files / len(matching)) if matching else 0
        avg_quality = round(sum(quality_rates) / len(quality_rates), 2) if quality_rates else 0.0

        return {
            "common_modules": common_modules,
            "avg_files": avg_files,
            "avg_quality_rate": avg_quality,
            "total_projects": len(matching),
        }

    def learn_from_repair(self, repair_report: dict[str, Any]) -> None:
        """Store lessons learned from a project repair.

        Records which issues were found and fixed so the engine can warn
        users about common problems during generation.

        Args:
            repair_report: Report dict from :func:`repair_project`, containing
                ``issues`` and ``fixes`` lists.
        """
        if not self.enabled:
            return

        data = self._load()

        issues = repair_report.get("issues", [])
        for issue in issues:
            category = issue.get("category", "unknown") if isinstance(issue, dict) else "unknown"
            description = issue.get("description", "") if isinstance(issue, dict) else str(issue)

            pattern = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "category": category,
                "description": description,
                "auto_fixed": issue.get("auto_fixable", False) if isinstance(issue, dict) else False,
            }

            data["repair_patterns"].append(pattern)

        # Keep last 100 repair patterns
        if len(data["repair_patterns"]) > 100:
            data["repair_patterns"] = data["repair_patterns"][-100:]

        self._save()

    def get_repair_warnings(self, project_type: str) -> list[str]:
        """Return warnings about common repairs for a project type.

        Args:
            project_type: The project type being generated.

        Returns:
            List of human-readable warning strings.
        """
        data = self._load()
        patterns = data.get("repair_patterns", [])

        if not patterns:
            return []

        # Count categories
        category_counts: dict[str, int] = {}
        for pattern in patterns:
            cat = pattern.get("category", "unknown")
            category_counts[cat] = category_counts.get(cat, 0) + 1

        warnings: list[str] = []
        for cat, count in sorted(category_counts.items(), key=lambda x: -x[1]):
            if count >= 3:
                warnings.append(
                    f"Common issue: '{cat}' has occurred {count} times in past repairs"
                )

        return warnings[:5]

    def get_most_generated_types(self) -> list[tuple[str, int]]:
        """Return project types sorted by generation frequency.

        Returns:
            List of ``(project_type, count)`` tuples, most frequent first.
        """
        data = self._load()
        freq = data.get("type_frequency", {})
        return sorted(freq.items(), key=lambda x: -x[1])

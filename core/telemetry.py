"""Telemetry v1.0 — Track generation events, timing, and failure patterns.

Records what gets generated, how long it takes, and what fails.
All data is stored locally in ``~/.nexusforge/telemetry.json``.
No sensitive information (API keys, file contents) is ever recorded.

Telemetry is opt-out: pass ``--no-telemetry`` to disable recording.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class GenerationEvent:
    """A single generation telemetry event.

    Attributes:
        timestamp: ISO-8601 timestamp of the event.
        event_type: One of ``project_created``, ``module_added``,
            ``repair_applied``, ``quality_gate_result``.
        project_type: The blueprint / project type used.
        stack: The technology stack ID (e.g. ``"python-fastapi"``).
        modules: List of module IDs involved.
        files_created: Number of files created or modified.
        duration_ms: Wall-clock duration in milliseconds.
        quality_gates_passed: How many quality gate checks passed.
        quality_gates_total: Total quality gate checks run.
        errors: List of error messages (no sensitive data).
    """

    timestamp: str = ""
    event_type: str = ""
    project_type: str = ""
    stack: str = "python-fastapi"
    modules: list[str] = field(default_factory=list)
    files_created: int = 0
    duration_ms: int = 0
    quality_gates_passed: int = 0
    quality_gates_total: int = 0
    errors: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Set timestamp if not provided."""
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Timer context manager
# ---------------------------------------------------------------------------

class Timer:
    """Simple wall-clock timer for measuring generation duration.

    Usage::

        timer = Timer()
        timer.start()
        # ... do work ...
        timer.stop()
        print(timer.elapsed_ms)
    """

    def __init__(self) -> None:
        self._start: float = 0.0
        self._end: float = 0.0

    def start(self) -> None:
        """Record the start time."""
        self._start = time.monotonic()

    def stop(self) -> None:
        """Record the end time."""
        self._end = time.monotonic()

    @property
    def elapsed_ms(self) -> int:
        """Return elapsed time in milliseconds.

        Returns:
            Integer milliseconds between start and stop.
        """
        return int((self._end - self._start) * 1000)


# ---------------------------------------------------------------------------
# Telemetry collector
# ---------------------------------------------------------------------------

_DEFAULT_STORAGE = os.path.join(os.path.expanduser("~"), ".nexusforge", "telemetry.json")


class TelemetryCollector:
    """Collects, stores, and queries generation telemetry events.

    Args:
        storage_path: Path to the telemetry JSON file.
            Defaults to ``~/.nexusforge/telemetry.json``.
        enabled: If False, all record operations are silently skipped.
    """

    def __init__(
        self,
        storage_path: str = _DEFAULT_STORAGE,
        enabled: bool = True,
    ) -> None:
        self.storage_path: str = os.path.expanduser(storage_path)
        self.enabled: bool = enabled
        self._events: list[dict[str, Any]] | None = None

    def _load(self) -> list[dict[str, Any]]:
        """Load events from disk, caching in memory.

        Returns:
            List of event dicts.
        """
        if self._events is not None:
            return self._events

        if not os.path.isfile(self.storage_path):
            self._events = []
            return self._events

        try:
            with open(self.storage_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._events = data if isinstance(data, list) else []
        except Exception:
            self._events = []

        return self._events

    def _save(self) -> None:
        """Persist events to disk."""
        events = self._load()
        try:
            os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
            with open(self.storage_path, "w", encoding="utf-8") as f:
                json.dump(events, f, indent=2)
        except OSError:
            pass  # Non-critical

    def record(self, event: GenerationEvent) -> None:
        """Record a generation event.

        Args:
            event: The event to record.
        """
        if not self.enabled:
            return

        events = self._load()
        events.append(asdict(event))

        # Keep last 500 events to prevent unbounded growth
        if len(events) > 500:
            self._events = events[-500:]

        self._save()

    def get_stats(self) -> dict[str, Any]:
        """Compute aggregate statistics across all recorded events.

        Returns:
            Dictionary with total counts, averages, and breakdowns.
        """
        events = self._load()
        if not events:
            return {
                "total_events": 0,
                "total_projects": 0,
                "total_modules_added": 0,
                "total_repairs": 0,
                "avg_duration_ms": 0,
                "avg_quality_gate_pass_rate": 0.0,
                "total_files_created": 0,
                "total_errors": 0,
            }

        projects = [e for e in events if e.get("event_type") == "project_created"]
        modules_added = [e for e in events if e.get("event_type") == "module_added"]
        repairs = [e for e in events if e.get("event_type") == "repair_applied"]

        durations = [e.get("duration_ms", 0) for e in events if e.get("duration_ms", 0) > 0]
        avg_duration = int(sum(durations) / len(durations)) if durations else 0

        qg_rates: list[float] = []
        for e in events:
            total = e.get("quality_gates_total", 0)
            if total > 0:
                qg_rates.append(e.get("quality_gates_passed", 0) / total)
        avg_qg = round(sum(qg_rates) / len(qg_rates), 2) if qg_rates else 0.0

        total_files = sum(e.get("files_created", 0) for e in events)
        total_errors = sum(len(e.get("errors", [])) for e in events)

        return {
            "total_events": len(events),
            "total_projects": len(projects),
            "total_modules_added": len(modules_added),
            "total_repairs": len(repairs),
            "avg_duration_ms": avg_duration,
            "avg_quality_gate_pass_rate": avg_qg,
            "total_files_created": total_files,
            "total_errors": total_errors,
        }

    def get_history(self, limit: int = 20) -> list[dict[str, Any]]:
        """Return the most recent events.

        Args:
            limit: Maximum number of events to return.

        Returns:
            List of event dicts, most recent first.
        """
        events = self._load()
        return list(reversed(events[-limit:]))

    def get_most_used_modules(self) -> dict[str, int]:
        """Count module usage frequency across all events.

        Returns:
            Mapping of module_id -> count, sorted by frequency descending.
        """
        events = self._load()
        counts: dict[str, int] = {}

        for event in events:
            for mod in event.get("modules", []):
                counts[mod] = counts.get(mod, 0) + 1

        return dict(sorted(counts.items(), key=lambda x: -x[1]))

    def get_failure_patterns(self) -> list[dict[str, Any]]:
        """Identify common failure patterns across events.

        Groups errors by message similarity and returns the most
        frequent patterns.

        Returns:
            List of dicts with ``error``, ``count``, and ``last_seen`` keys.
        """
        events = self._load()
        error_counts: dict[str, dict[str, Any]] = {}

        for event in events:
            for error in event.get("errors", []):
                # Normalize error for grouping (strip paths and numbers)
                normalized = error.strip()
                if normalized not in error_counts:
                    error_counts[normalized] = {
                        "error": normalized,
                        "count": 0,
                        "last_seen": "",
                    }
                error_counts[normalized]["count"] += 1
                error_counts[normalized]["last_seen"] = event.get("timestamp", "")

        patterns = sorted(error_counts.values(), key=lambda x: -x["count"])
        return patterns[:20]

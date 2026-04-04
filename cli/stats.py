#!/usr/bin/env python3
"""NexusForge Engine — View generation telemetry and statistics.

Usage::

    # Show generation stats
    python cli/stats.py

    # Show last 20 generations
    python cli/stats.py --history

    # Most used modules
    python cli/stats.py --modules

    # Common failure patterns
    python cli/stats.py --failures

    # Show everything
    python cli/stats.py --all
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.telemetry import TelemetryCollector
from core.project_memory import ProjectMemory


def _print_stats(telemetry: TelemetryCollector) -> None:
    """Print aggregate generation statistics.

    Args:
        telemetry: The telemetry collector instance.
    """
    stats = telemetry.get_stats()

    print("Generation Statistics")
    print("=" * 40)
    print(f"  Total events:           {stats['total_events']}")
    print(f"  Projects created:       {stats['total_projects']}")
    print(f"  Modules added:          {stats['total_modules_added']}")
    print(f"  Repairs applied:        {stats['total_repairs']}")
    print(f"  Avg duration:           {stats['avg_duration_ms']}ms")
    print(f"  Avg quality gate rate:  {stats['avg_quality_gate_pass_rate']:.0%}")
    print(f"  Total files created:    {stats['total_files_created']}")
    print(f"  Total errors:           {stats['total_errors']}")
    print()


def _print_history(telemetry: TelemetryCollector, limit: int = 20) -> None:
    """Print the most recent generation events.

    Args:
        telemetry: The telemetry collector instance.
        limit: Maximum number of events to show.
    """
    history = telemetry.get_history(limit=limit)

    print(f"Recent Events (last {limit})")
    print("=" * 60)

    if not history:
        print("  No events recorded yet.")
        print()
        return

    for i, event in enumerate(history, 1):
        event_type = event.get("event_type", "unknown")
        project_type = event.get("project_type", "?")
        stack = event.get("stack", "?")
        files = event.get("files_created", 0)
        duration = event.get("duration_ms", 0)
        timestamp = event.get("timestamp", "?")
        qg_passed = event.get("quality_gates_passed", 0)
        qg_total = event.get("quality_gates_total", 0)
        errors = event.get("errors", [])

        status = "OK" if not errors else f"{len(errors)} errors"
        qg_str = f"{qg_passed}/{qg_total}" if qg_total > 0 else "N/A"

        print(f"  {i:>3}. [{event_type}] {project_type} ({stack})")
        print(f"       Files: {files} | Duration: {duration}ms | QG: {qg_str} | {status}")
        print(f"       {timestamp}")
        if errors:
            for err in errors[:3]:
                print(f"       ERROR: {err}")
        print()


def _print_modules(telemetry: TelemetryCollector) -> None:
    """Print most used modules.

    Args:
        telemetry: The telemetry collector instance.
    """
    modules = telemetry.get_most_used_modules()

    print("Most Used Modules")
    print("=" * 40)

    if not modules:
        print("  No module data yet.")
        print()
        return

    max_count = max(modules.values()) if modules else 1
    for mod_id, count in modules.items():
        bar_len = int((count / max_count) * 20)
        bar = "#" * bar_len
        print(f"  {mod_id:<20} {count:>4}x  {bar}")

    print()


def _print_failures(telemetry: TelemetryCollector) -> None:
    """Print common failure patterns.

    Args:
        telemetry: The telemetry collector instance.
    """
    patterns = telemetry.get_failure_patterns()

    print("Failure Patterns")
    print("=" * 60)

    if not patterns:
        print("  No failures recorded. Nice!")
        print()
        return

    for i, pattern in enumerate(patterns, 1):
        print(f"  {i}. [{pattern['count']}x] {pattern['error']}")
        print(f"     Last seen: {pattern['last_seen']}")
        print()


def _print_memory_summary() -> None:
    """Print project memory summary."""
    memory = ProjectMemory()
    prefs = memory.get_user_preferences()
    types = memory.get_most_generated_types()

    print("Project Memory")
    print("=" * 40)

    if prefs.get("preferred_stack"):
        print(f"  Preferred stack:     {prefs['preferred_stack']}")
    if prefs.get("default_modules"):
        print(f"  Default modules:     {', '.join(prefs['default_modules'])}")

    if types:
        print(f"\n  Most generated types:")
        for ptype, count in types[:5]:
            print(f"    {ptype:<25} {count}x")

    print()


def main() -> None:
    """CLI entry point for the telemetry stats viewer."""
    parser = argparse.ArgumentParser(
        description="NexusForge Engine -- View generation telemetry",
    )
    parser.add_argument(
        "--history",
        action="store_true",
        help="Show last 20 generation events",
    )
    parser.add_argument(
        "--modules",
        action="store_true",
        help="Show most used modules",
    )
    parser.add_argument(
        "--failures",
        action="store_true",
        help="Show common failure patterns",
    )
    parser.add_argument(
        "--memory",
        action="store_true",
        help="Show project memory summary",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Show all telemetry data",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Number of history entries to show (default: 20)",
    )
    args = parser.parse_args()

    telemetry = TelemetryCollector()

    print("NexusForge Engine v1.0 -- Telemetry")
    print()

    # If no specific flag, show stats
    show_stats = not any([args.history, args.modules, args.failures, args.memory])

    if show_stats or args.all:
        _print_stats(telemetry)

    if args.history or args.all:
        _print_history(telemetry, limit=args.limit)

    if args.modules or args.all:
        _print_modules(telemetry)

    if args.failures or args.all:
        _print_failures(telemetry)

    if args.memory or args.all:
        _print_memory_summary()


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Repair a NexusForge project -- detect and fix common issues.

Usage::

    # Report only (default)
    python cli/repair_project.py --project ./my_project

    # Auto-fix all fixable issues
    python cli/repair_project.py --project ./my_project --fix

    # Dry-run: show what would be fixed without writing
    python cli/repair_project.py --project ./my_project --fix --dry-run
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.repair_engine import repair_project, RepairIssue, RepairResult


_SEVERITY_ICONS = {
    "critical": "[CRIT]",
    "warning": "[WARN]",
    "info": "[INFO]",
}


def _print_issue(issue: RepairIssue) -> None:
    """Pretty-print a single issue."""
    icon = _SEVERITY_ICONS.get(issue.severity, "[????]")
    print(f"  {icon} {issue.description}")
    print(f"         File: {issue.file_path}")
    print(f"         Fix:  {issue.fix_description}")
    fixable = "yes" if issue.auto_fixable else "NO (manual)"
    print(f"         Auto-fixable: {fixable}")
    print()


def _print_fix(fix: RepairResult) -> None:
    """Pretty-print a single fix result."""
    status = "APPLIED" if fix.applied else "SKIPPED"
    print(f"  [{status}] {fix.issue_id}: {fix.detail}")


def main() -> None:
    """CLI entry point for the project repair tool."""
    parser = argparse.ArgumentParser(
        description="NexusForge Repair -- detect and fix project issues",
    )
    parser.add_argument(
        "--project", "-p",
        type=str,
        required=True,
        help="Path to the NexusForge project to repair",
    )
    parser.add_argument(
        "--fix",
        action="store_true",
        default=False,
        help="Auto-fix all fixable issues (default: report only)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Show what would be fixed without writing (requires --fix)",
    )
    args = parser.parse_args()

    project_path = os.path.abspath(args.project)

    if not os.path.isdir(project_path):
        print(f"[ERROR] Project not found: {project_path}")
        sys.exit(1)

    mode = "DRY RUN" if args.fix and args.dry_run else ("AUTO-FIX" if args.fix else "REPORT ONLY")
    print(f"NexusForge Repair v0.5 -- {mode}")
    print(f"Project: {project_path}")
    print("=" * 60)

    report = repair_project(
        project_path,
        auto_fix=args.fix,
        dry_run=args.dry_run,
    )

    # Print issues
    if report.issues:
        print(f"\nFound {len(report.issues)} issue(s):\n")
        for issue in report.issues:
            _print_issue(issue)
    else:
        print("\nNo issues found -- project looks healthy!")

    # Print summary
    print("-" * 60)
    s = report.summary
    print(f"Summary: {s.get('total', 0)} issues "
          f"({s.get('critical', 0)} critical, {s.get('warning', 0)} warnings, "
          f"{s.get('info', 0)} info)")
    print(f"Auto-fixable: {s.get('auto_fixable', 0)}")

    # Print fix results
    if report.fixes:
        print(f"\nFix results:\n")
        for fix in report.fixes:
            _print_fix(fix)
        applied = sum(1 for f in report.fixes if f.applied)
        print(f"\nApplied {applied}/{len(report.fixes)} fixes")

    # Exit code: 1 if critical issues remain unfixed
    if not args.fix and s.get("critical", 0) > 0:
        sys.exit(1)
    elif args.fix and not args.dry_run:
        unfixed_critical = sum(
            1 for i in report.issues
            if i.severity == "critical" and not i.auto_fixable
        )
        if unfixed_critical > 0:
            print(f"\n[WARNING] {unfixed_critical} critical issue(s) require manual intervention")
            sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""NexusForge Engine v1.0 — Generate enterprise automation projects.

Supports intelligent intent routing, multi-stack generation, telemetry,
project memory, and interactive guided creation.

Usage::

    # Basic generation from prompt
    python cli/new_project.py --prompt "Create a ticket triage system"

    # Specify a technology stack
    python cli/new_project.py --prompt "Invoice processor" --stack python-flask

    # Interactive guided creation
    python cli/new_project.py --interactive

    # Show module suggestions from history
    python cli/new_project.py --prompt "Monitoring system" --suggest

    # Disable telemetry recording
    python cli/new_project.py --prompt "SaaS platform" --no-telemetry
"""

import argparse
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.intent_router import route_intent
from core.blueprint_selector import select_blueprint
from core.module_composer import compose_modules
from core.spec_generator import generate_specs
from core.template_engine import render_templates
from core.execution_engine import execute_scaffold
from core.quality_gate import run_quality_gates
from core.stack_manager import (
    STACKS,
    DEFAULT_STACK,
    get_stack,
    validate_stack,
    has_full_templates,
    get_skeleton_files,
)
from core.telemetry import TelemetryCollector, GenerationEvent, Timer
from core.project_memory import ProjectMemory


def _interactive_mode(args: argparse.Namespace) -> None:
    """Run the interactive guided creation flow.

    Walks the user through project creation step by step:
    1. Ask for project description
    2. Show detected intent + confidence
    3. Show suggested modules (based on history)
    4. Let user add/remove modules
    5. Show compatibility check
    6. Confirm and generate

    Args:
        args: Parsed CLI arguments (output, stack, no_telemetry are used).
    """
    telemetry_enabled = not args.no_telemetry
    memory = ProjectMemory(enabled=telemetry_enabled)

    print("NexusForge Engine v1.0 -- Interactive Mode")
    print("=" * 50)

    # Step 1: Get project description
    print("\nStep 1: Describe your project")
    prompt = input("  > ").strip()
    if not prompt:
        print("[ERROR] No description provided")
        sys.exit(1)

    # Step 2: Show detected intent
    print("\nStep 2: Intent Analysis")
    intent = route_intent(prompt, save_history=telemetry_enabled)
    print(f"  Type: {intent['project_type']} (confidence: {intent['confidence']:.0%})")
    if intent.get("alternative_types"):
        for alt in intent["alternative_types"][:3]:
            print(f"  Alternative: {alt['type']} ({alt['confidence']:.0%})")
    if intent.get("multi_intent"):
        print(f"  Multi-intent detected: {', '.join(intent['multi_intent'])}")

    if intent["confidence"] < 0.5:
        print("\n  [WARNING] Low confidence. Please provide more details or continue.")
        clarify = input("  Add more context (or press Enter to continue): ").strip()
        if clarify:
            prompt = f"{prompt}. {clarify}"
            intent = route_intent(prompt, save_history=telemetry_enabled)
            print(f"  Updated type: {intent['project_type']} ({intent['confidence']:.0%})")

    print(f"  Complexity: {intent['complexity']}")
    print(f"  Industry: {intent.get('industry', 'general')}")

    # Step 3: Show suggested modules
    print(f"\nStep 3: Module Selection")
    suggested = memory.suggest_modules(intent["project_type"])
    current_modules = list(intent["modules"])

    print(f"  Detected modules: {', '.join(current_modules)}")
    if suggested:
        print(f"  Suggested from history: {', '.join(suggested)}")
        add_suggested = input("  Add suggested modules? (y/N): ").strip().lower()
        if add_suggested == "y":
            for mod in suggested:
                if mod not in current_modules:
                    current_modules.append(mod)

    # Step 4: Add/remove modules
    print(f"\n  Current modules: {', '.join(current_modules)}")
    modify = input("  Modify? (a=add, r=remove, Enter=continue): ").strip().lower()

    while modify in ("a", "r"):
        if modify == "a":
            mod_name = input("  Module to add: ").strip()
            if mod_name and mod_name not in current_modules:
                current_modules.append(mod_name)
        elif modify == "r":
            mod_name = input("  Module to remove: ").strip()
            if mod_name in current_modules:
                current_modules.remove(mod_name)
        print(f"  Current modules: {', '.join(current_modules)}")
        modify = input("  Modify? (a=add, r=remove, Enter=continue): ").strip().lower()

    intent["modules"] = current_modules

    # Step 5: Stack selection
    stack_id = args.stack or DEFAULT_STACK
    print(f"\nStep 4: Stack")
    print(f"  Selected: {stack_id}")
    if not has_full_templates(stack_id):
        print(f"  [NOTE] '{stack_id}' uses skeleton templates (TODO markers for modules)")

    # Step 6: Confirm
    print(f"\nStep 5: Confirm")
    print(f"  Project: {intent['project_type']}")
    print(f"  Stack: {stack_id}")
    print(f"  Modules: {', '.join(current_modules)}")
    print(f"  Output: {os.path.abspath(args.output)}")
    confirm = input("  Generate? (Y/n): ").strip().lower()
    if confirm == "n":
        print("Cancelled.")
        sys.exit(0)

    # Generate
    _generate_project(intent, args, stack_id, telemetry_enabled)


def _generate_project(
    intent: dict,
    args: argparse.Namespace,
    stack_id: str,
    telemetry_enabled: bool,
) -> None:
    """Execute the full project generation pipeline.

    Args:
        intent: Structured intent from the router.
        args: Parsed CLI arguments.
        stack_id: Technology stack identifier.
        telemetry_enabled: Whether to record telemetry.
    """
    telemetry = TelemetryCollector(enabled=telemetry_enabled)
    memory = ProjectMemory(enabled=telemetry_enabled)
    timer = Timer()
    timer.start()
    errors: list[str] = []

    # Step 1: Select blueprint
    print(f"\n  Selecting blueprint...")
    blueprint = select_blueprint(intent)
    print(f"   Blueprint: {blueprint['id']}")

    # Step 2: Compose modules
    print(f"\n  Composing modules...")
    modules = compose_modules(intent, blueprint)
    print(f"   Total modules: {len(modules)}")
    for mod in modules:
        print(f"   - {mod['id']}")

    # Step 3: Generate specs
    print(f"\n  Generating specs...")
    specs = generate_specs(intent, blueprint, modules)
    print(f"   Files: {len(specs['files'])}")

    if args.dry_run:
        print(f"\n  DRY RUN -- would generate:")
        for f in specs["files"]:
            print(f"   {f['path']}")
        return

    # Step 4: Render templates
    print(f"\n  Rendering templates...")
    variables = {
        "PROJECT_NAME": intent.get("project_type", "nexusforge_project"),
        "PROJECT_DESCRIPTION": intent.get("description", ""),
        "HAS_BILLING": "billing" in [m.get("id", "") for m in modules],
        "HAS_AI": "ai_chat" in [m.get("id", "") for m in modules],
        "HAS_CELERY": True,
        "MODULES": modules,
        "BLUEPRINT": blueprint,
        "STACK": stack_id,
    }
    rendered = render_templates(specs, variables)
    print(f"   Rendered: {len(rendered)} template files")

    # Step 5: Scaffold
    print(f"\n  Scaffolding project...")
    result = execute_scaffold(
        specs, args.output,
        blueprint=blueprint, modules=modules, rendered_templates=rendered,
    )
    print(f"   Created: {result['files_created']} files")
    print(f"   Directories: {result['dirs_created']}")

    # Step 5b: For non-default stacks, add skeleton files
    if not has_full_templates(stack_id):
        skeleton_files = get_skeleton_files(
            stack_id,
            intent.get("project_type", "project"),
            intent.get("description", ""),
        )
        if skeleton_files:
            for sf in skeleton_files:
                full_path = os.path.join(os.path.abspath(args.output), sf["path"])
                os.makedirs(os.path.dirname(full_path), exist_ok=True)
                with open(full_path, "w", encoding="utf-8") as f:
                    f.write(sf["content"])
                result["files_created"] += 1
            print(f"   Skeleton files added: {len(skeleton_files)} ({stack_id})")

    # Step 6: Quality gates
    print(f"\n  Running quality gates...")
    qg = run_quality_gates(args.output)
    print(f"   Passed: {qg['passed']}/{qg['total']}")
    if qg["failures"]:
        for fail in qg["failures"]:
            print(f"   FAIL: {fail}")
            errors.append(fail)

    timer.stop()

    # Step 7: Record telemetry
    event = GenerationEvent(
        event_type="project_created",
        project_type=intent.get("project_type", ""),
        stack=stack_id,
        modules=[m.get("id", "") for m in modules],
        files_created=result["files_created"],
        duration_ms=timer.elapsed_ms,
        quality_gates_passed=qg["passed"],
        quality_gates_total=qg["total"],
        errors=errors,
    )
    telemetry.record(event)

    # Step 8: Record to project memory
    manifest_data = {
        "project": {"type": intent.get("project_type", "")},
        "modules": [{"id": m.get("id", "")} for m in modules],
        "stack": {"framework": stack_id},
    }
    memory_result = {
        "files_created": result["files_created"],
        "quality_passed": qg["passed"],
        "quality_total": qg["total"],
    }
    memory.remember_project(manifest_data, memory_result)

    # Step 9: Show repair warnings
    warnings = memory.get_repair_warnings(intent.get("project_type", ""))
    if warnings:
        print(f"\n  Warnings from past repairs:")
        for w in warnings:
            print(f"   {w}")

    stack = get_stack(stack_id)
    print(f"\n  Project generated at: {os.path.abspath(args.output)}")
    print(f"   Duration: {timer.elapsed_ms}ms")
    print(f"   Stack: {stack_id}")
    print(f"   Next: cd {args.output} && {stack['run_command']}")


def main() -> None:
    """CLI entry point for NexusForge Engine v1.0."""
    parser = argparse.ArgumentParser(
        description="NexusForge Engine v1.0 -- Generate automation projects",
    )
    parser.add_argument(
        "--prompt", "-p",
        type=str,
        help="Natural language description of the project",
    )
    parser.add_argument(
        "--manifest", "-m",
        type=str,
        help="Path to project_manifest.yaml",
    )
    parser.add_argument(
        "--output", "-o",
        type=str,
        default="./output",
        help="Output directory (default: ./output)",
    )
    parser.add_argument(
        "--blueprint", "-b",
        type=str,
        help="Blueprint name (skip intent routing)",
    )
    parser.add_argument(
        "--stack",
        type=str,
        default=None,
        choices=list(STACKS.keys()),
        help=f"Technology stack (default: {DEFAULT_STACK})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be generated without writing files",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Verbose output",
    )
    parser.add_argument(
        "--no-telemetry",
        action="store_true",
        help="Disable telemetry and project memory recording",
    )
    parser.add_argument(
        "--suggest",
        action="store_true",
        help="Show module suggestions based on project history",
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Step-by-step guided creation mode",
    )
    args = parser.parse_args()

    # Interactive mode
    if args.interactive:
        _interactive_mode(args)
        return

    if not args.prompt and not args.manifest:
        parser.print_help()
        print("\nExamples:")
        print("  python cli/new_project.py --prompt 'Create a ticket triage system'")
        print("  python cli/new_project.py --interactive")
        print("  python cli/new_project.py --prompt 'SaaS platform' --stack node-express")
        sys.exit(1)

    telemetry_enabled = not args.no_telemetry
    stack_id = args.stack or DEFAULT_STACK

    print("NexusForge Engine v1.0")
    print("=" * 50)

    # Validate stack
    if not validate_stack(stack_id):
        print(f"[ERROR] Unknown stack: {stack_id}")
        print(f"Available: {', '.join(STACKS.keys())}")
        sys.exit(1)

    if not has_full_templates(stack_id):
        print(f"[NOTE] Stack '{stack_id}' uses skeleton templates with TODO markers")

    # Step 1: Route intent
    if args.manifest:
        import yaml
        with open(args.manifest) as f:
            manifest = yaml.safe_load(f)
        intent = manifest
        print(f"  Loaded manifest: {args.manifest}")
    elif args.blueprint:
        intent = {"project_type": args.blueprint, "from_prompt": args.prompt}
        print(f"  Using blueprint: {args.blueprint}")
    else:
        print(f"  Analyzing: \"{args.prompt[:80]}...\"")
        intent = route_intent(args.prompt, save_history=telemetry_enabled)
        print(f"   Type: {intent['project_type']} (confidence: {intent['confidence']:.0%})")
        print(f"   Complexity: {intent['complexity']}")
        print(f"   Modules: {', '.join(intent.get('modules', []))}")

        if intent.get("alternative_types"):
            for alt in intent["alternative_types"][:2]:
                print(f"   Alternative: {alt['type']} ({alt['confidence']:.0%})")

        if intent.get("multi_intent"):
            print(f"   Multi-intent: {', '.join(intent['multi_intent'])}")

        if intent["confidence"] < 0.5:
            print("   [WARNING] Low confidence -- consider using --interactive for guided creation")

        if intent.get("industry") and intent["industry"] != "general":
            print(f"   Industry: {intent['industry']}")

        if intent.get("compliance"):
            print(f"   Compliance: {', '.join(intent['compliance'])}")

    # Show suggestions
    if args.suggest:
        memory = ProjectMemory(enabled=telemetry_enabled)
        project_type = intent.get("project_type", "")
        suggestions = memory.suggest_modules(project_type)
        if suggestions:
            print(f"\n  Suggested modules (from history): {', '.join(suggestions)}")
        else:
            print("\n  No suggestions available (generate more projects to build history)")

    _generate_project(intent, args, stack_id, telemetry_enabled)


if __name__ == "__main__":
    main()

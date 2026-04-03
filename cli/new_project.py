#!/usr/bin/env python3
"""NexusForge Engine — Generate enterprise automation projects."""

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

def main():
    parser = argparse.ArgumentParser(description='NexusForge Engine — Generate automation projects')
    parser.add_argument('--prompt', '-p', type=str, help='Natural language description of the project')
    parser.add_argument('--manifest', '-m', type=str, help='Path to project_manifest.yaml')
    parser.add_argument('--output', '-o', type=str, default='./output', help='Output directory')
    parser.add_argument('--blueprint', '-b', type=str, help='Blueprint name (skip intent routing)')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be generated without writing files')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
    args = parser.parse_args()

    if not args.prompt and not args.manifest:
        parser.print_help()
        print("\nExample: python cli/new_project.py --prompt 'Create a ticket triage system for customer support'")
        sys.exit(1)

    print("🚀 NexusForge Engine v0.1")
    print("=" * 50)

    # Step 1: Route intent
    if args.manifest:
        import yaml
        with open(args.manifest) as f:
            manifest = yaml.safe_load(f)
        intent = manifest
        print(f"📋 Loaded manifest: {args.manifest}")
    elif args.blueprint:
        intent = {"project_type": args.blueprint, "from_prompt": args.prompt}
        print(f"📋 Using blueprint: {args.blueprint}")
    else:
        print(f"🧠 Analyzing: \"{args.prompt[:80]}...\"")
        intent = route_intent(args.prompt)
        print(f"   Type: {intent['project_type']}")
        print(f"   Complexity: {intent['complexity']}")
        print(f"   Modules: {', '.join(intent.get('modules', []))}")

    # Step 2: Select blueprint
    print(f"\n📐 Selecting blueprint...")
    blueprint = select_blueprint(intent)
    print(f"   Blueprint: {blueprint['id']}")
    print(f"   Base modules: {len(blueprint.get('required_modules', []))}")

    # Step 3: Compose modules
    print(f"\n🧩 Composing modules...")
    modules = compose_modules(intent, blueprint)
    print(f"   Total modules: {len(modules)}")
    for mod in modules:
        print(f"   - {mod['id']}")

    # Step 4: Generate specs
    print(f"\n📝 Generating specs...")
    specs = generate_specs(intent, blueprint, modules)
    print(f"   Files: {len(specs['files'])}")

    if args.dry_run:
        print(f"\n🔍 DRY RUN — would generate:")
        for f in specs['files']:
            print(f"   {f['path']}")
        return

    # Step 5: Render templates
    print(f"\n🎨 Rendering templates...")
    from core.template_engine import render_templates
    variables = {
        "PROJECT_NAME": intent.get("project_type", "nexusforge_project"),
        "PROJECT_DESCRIPTION": intent.get("description", ""),
        "HAS_BILLING": "billing" in [m.get("id", "") for m in modules],
        "HAS_AI": "ai_chat" in [m.get("id", "") for m in modules],
        "HAS_CELERY": True,
        "MODULES": modules,
        "BLUEPRINT": blueprint,
    }
    rendered = render_templates(specs, variables)
    print(f"   Rendered: {len(rendered)} template files")

    # Step 6: Scaffold
    print(f"\n🔨 Scaffolding project...")
    result = execute_scaffold(specs, args.output, blueprint=blueprint, modules=modules, rendered_templates=rendered)
    print(f"   Created: {result['files_created']} files")
    print(f"   Directories: {result['dirs_created']}")

    # Step 6: Quality gates
    print(f"\n✅ Running quality gates...")
    qg = run_quality_gates(args.output)
    print(f"   Passed: {qg['passed']}/{qg['total']}")
    if qg['failures']:
        for f in qg['failures']:
            print(f"   ❌ {f}")

    print(f"\n🎉 Project generated at: {os.path.abspath(args.output)}")
    print(f"   Next: cd {args.output} && pip install -r requirements.txt")

if __name__ == '__main__':
    main()

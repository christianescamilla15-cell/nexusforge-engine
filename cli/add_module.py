#!/usr/bin/env python3
"""Add a module to an existing NexusForge project."""

import argparse
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.module_composer import get_module, inject_module

def main():
    parser = argparse.ArgumentParser(description='Add module to NexusForge project')
    parser.add_argument('--project', '-p', type=str, required=True, help='Path to project')
    parser.add_argument('--module', '-m', type=str, required=True, help='Module name')
    args = parser.parse_args()

    if not os.path.exists(args.project):
        print(f"❌ Project not found: {args.project}")
        sys.exit(1)

    module = get_module(args.module)
    if not module:
        print(f"❌ Unknown module: {args.module}")
        sys.exit(1)

    print(f"🧩 Adding module: {module['id']}")
    result = inject_module(args.project, module)
    print(f"   Files created: {result['files_created']}")
    print(f"   Files modified: {result['files_modified']}")
    print(f"✅ Module '{args.module}' added successfully")

if __name__ == '__main__':
    main()

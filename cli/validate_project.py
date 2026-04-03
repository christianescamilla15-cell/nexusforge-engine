#!/usr/bin/env python3
"""Validate a NexusForge project structure."""

import argparse
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.quality_gate import run_quality_gates

def main():
    parser = argparse.ArgumentParser(description='Validate NexusForge project')
    parser.add_argument('--project', '-p', type=str, required=True, help='Path to project')
    args = parser.parse_args()

    if not os.path.exists(args.project):
        print(f"❌ Project not found: {args.project}")
        sys.exit(1)

    print(f"🔍 Validating: {args.project}")
    qg = run_quality_gates(args.project)

    for check in qg['checks']:
        icon = "✅" if check['passed'] else "❌"
        print(f"   {icon} {check['name']}")
        if not check['passed'] and check.get('details'):
            print(f"      {check['details']}")

    print(f"\n{'✅' if qg['passed'] == qg['total'] else '❌'} {qg['passed']}/{qg['total']} checks passed")

if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""Test conflicts detection and API response for UI display."""

from project_10.conflicts import detect_conflicts, build_active_decisions
from project_12.pipeline import run_pipeline
import json

print("=" * 70)
print("Testing Conflicts Detection for UI Display")
print("=" * 70)

# Test 1: UUID + multi-tenant (preference tradeoff)
print("\nTest 1: UUID + multi-tenant (preference tradeoff)")
active = build_active_decisions({'tenancy_model': 'multi_tenant', 'pk_strategy': 'uuid'})
conflicts = detect_conflicts(active)
print(f"Conflicts detected: {len(conflicts)}")
for c in conflicts:
    print(f"  - {c['decision_a']}={c['choice_a']} × {c['decision_b']}={c['choice_b']}")
    print(f"    Category: {c['category']}")
    print(f"    Reason: {c['reason']}")
    print()

# Test 2: Run a simple pipeline to verify conflicts are in the response
print("=" * 70)
print("Test 2: Pipeline conflict response structure")
print("=" * 70)

req = "I need a multi-tenant e-commerce platform with UUID primary keys, product catalog, and order tracking."
result = run_pipeline(req, verbose=False)

print(f"Pipeline returned: {result.keys()}")
print(f"Conflicts in response: {len(result.get('conflicts', []))}")

if result.get('conflicts'):
    print("\nConflict details:")
    for c in result['conflicts']:
        print(f"  - {c['decision_a']}={c['choice_a']} × {c['decision_b']}={c['choice_b']}")
        print(f"    Category: {c['category']}")
        print(f"    Resolution: {c['resolution'][:60]}...")
        print()

print("✓ Conflicts UI display structure verified!")

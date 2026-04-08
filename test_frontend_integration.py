#!/usr/bin/env python3
"""
Test the frontend integration for conflicts visualization.
Verifies that the API response includes all necessary fields for the UI.
"""

import json
from project_12.pipeline import run_pipeline

print("=" * 70)
print("Frontend Integration Test: Conflicts Visualization")
print("=" * 70)

# Test 1: Verify API response structure
print("\n[TEST 1] API Response Structure for Conflicts")

req = "I need an e-commerce platform with product catalog, shopping cart, and order management"
result = run_pipeline(req, verbose=False)

required_fields = ['ddl', 'tables', 'creation_order', 'conflicts', 'explainability', 'validation']
response_fields = list(result.keys())

print(f"Response fields: {response_fields}")
missing = [f for f in required_fields if f not in response_fields]
if missing:
    print(f"❌ Missing fields: {missing}")
    exit(1)
else:
    print(f"✓ All required fields present")

# Test 2: Verify conflicts field format
print("\n[TEST 2] Conflicts Field Format")

conflicts = result.get('conflicts', [])
print(f"Conflicts found: {len(conflicts)}")

if conflicts:
    sample = conflicts[0]
    required_conflict_fields = ['decision_a', 'choice_a', 'decision_b', 'choice_b', 'category', 'reason', 'resolution']
    conflict_fields = list(sample.keys())
    
    print(f"Sample conflict structure: {conflict_fields}")
    missing_conflict_fields = [f for f in required_conflict_fields if f not in conflict_fields]
    
    if missing_conflict_fields:
        print(f"❌ Missing conflict fields: {missing_conflict_fields}")
        exit(1)
    else:
        print(f"✓ Conflict structure is correct")
    
    # Verify category values
    valid_categories = ['hard_incompatibility', 'preference_tradeoff']
    for c in conflicts:
        if c['category'] not in valid_categories:
            print(f"❌ Invalid category: {c['category']}")
            exit(1)
    print(f"✓ All conflict categories are valid")
    
    # Print sample for visual inspection
    print(f"\nSample conflict (for frontend rendering):")
    print(json.dumps(sample, indent=2))

# Test 3: Verify conflict rendering fields match JavaScript expectations
print("\n[TEST 3] Conflict Rendering Compatibility")

expected_js_usage = {
    'decision_a': 'shown as <strong>decision_a</strong>',
    'choice_a': 'shown as <code>choice_a</code>',
    'decision_b': 'shown as <strong>decision_b</strong>',
    'choice_b': 'shown as <code>choice_b</code>',
    'category': 'used for HTML class and icon selection',
    'reason': 'displayed in conflict-reason div',
    'resolution': 'displayed in conflict-resolution div',
}

if conflicts:
    sample = conflicts[0]
    for field, usage in expected_js_usage.items():
        if not isinstance(sample.get(field), (str, type(None))):
            print(f"⚠ Field {field} is not string-like (type: {type(sample.get(field)).__name__})")
        else:
            print(f"✓ {field}: {usage}")

print("\n" + "=" * 70)
print("✓ Frontend integration test PASSED!")
print("=" * 70)

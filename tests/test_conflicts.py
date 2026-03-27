import pytest
from project_10.conflicts import build_active_decisions, detect_conflicts

def test_defaults_no_conflicts():
    overrides = {}
    active = build_active_decisions(overrides)
    conflicts = detect_conflicts(active)
    
    assert len(conflicts) == 0

def test_uuid_multitenant_tradeoff():
    overrides = {
        "pk_strategy": "uuid",
        "tenancy_model": "multi_tenant",
        "tenancy_model_confidence": 0.9  # Required to overcome critical halt
    }
    active = build_active_decisions(overrides)
    conflicts = detect_conflicts(active)
    
    assert len(conflicts) == 1
    assert conflicts[0]["category"] == "preference_tradeoff"

def test_nested_set_multitenant_hard_incompatibility():
    overrides = {
        "hierarchy_approach": "nested_set",
        "tenancy_model": "multi_tenant",
        "tenancy_model_confidence": 0.95
    }
    active = build_active_decisions(overrides)
    conflicts = detect_conflicts(active)
    
    assert len(conflicts) == 1
    assert conflicts[0]["category"] == "hard_incompatibility"

def test_critical_decision_halt():
    overrides = {
        "tenancy_model": "multi_tenant",
        "tenancy_model_confidence": 0.6  # < 0.85
    }
    active = build_active_decisions(overrides)
    
    # Should be halted and have "source": "halted" instead of applying
    assert "tenancy_model" in active
    assert active["tenancy_model"]["source"] == "halted"

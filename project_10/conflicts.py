# project_10/conflicts.py

DECISIONS = {
    "pk_strategy": {
        "default":      "auto_increment",
        "alternatives": ["uuid"],
        "critical":     False
    },
    "delete_strategy": {
        "default":      "soft_delete",
        "alternatives": ["hard_delete"],
        "critical":     False
    },
    "tenancy_model": {
        "default":      "single_tenant",
        "alternatives": ["multi_tenant"],
        "critical":     True
    },
    "audit_policy": {
        "default":      "full_audit",
        "alternatives": ["no_audit"],
        "critical":     False
    },
    "hierarchy_approach": {
        "default":      "adjacency_list",
        "alternatives": ["nested_set", "closure_table"],
        "critical":     False
    },
    "temporal_strategy": {
        "default":      "current_only",
        "alternatives": ["versioned"],
        "critical":     False
    },
}

CONFLICTS = [
    {
        "decision_a": "pk_strategy",
        "choice_a":   "uuid",
        "decision_b": "tenancy_model",
        "choice_b":   "multi_tenant",
        "category":   "preference_tradeoff",
        "reason":     "UUID + multi-tenant creates wide composite keys (tenant_id, uuid)",
        "resolution": "Both valid. Warn user about composite key complexity.",
    },
    {
        "decision_a": "temporal_strategy",
        "choice_a":   "versioned",
        "decision_b": "delete_strategy",
        "choice_b":   "soft_delete",
        "category":   "preference_tradeoff",
        "reason":     "Versioned + soft-delete: is deletion itself versioned?",
        "resolution": "Apply both. Warn about semantic ambiguity.",
    },
    {
        "decision_a": "hierarchy_approach",
        "choice_a":   "nested_set",
        "decision_b": "tenancy_model",
        "choice_b":   "multi_tenant",
        "category":   "hard_incompatibility",
        "reason":     "Nested set lft/rgt must be scoped per tenant — very complex.",
        "resolution": "Recommend adjacency_list. Require explicit confirmation.",
    },
    {
        "decision_a": "audit_policy",
        "choice_a":   "no_audit",
        "decision_b": "delete_strategy",
        "choice_b":   "hard_delete",
        "category":   "preference_tradeoff",
        "reason":     "No audit + hard_delete: deleted records leave no trace whatsoever.",
        "resolution": "Strongly recommend at least soft_delete or full_audit for data safety.",
    },
    {
        "decision_a": "temporal_strategy",
        "choice_a":   "versioned",
        "decision_b": "audit_policy",
        "choice_b":   "no_audit",
        "category":   "preference_tradeoff",
        "reason":     "Versioned records with no audit trail loses who made the version.",
        "resolution": "Enable full_audit to capture created_by/updated_by on versioned rows.",
    },
]

# ── Build active decisions ─────────────────────────────────────────────────────

def build_active_decisions(user_overrides):
    active = {}

    for name, config in DECISIONS.items():
        if name in user_overrides:
            choice = user_overrides[name]
            source = "explicit"

            # Critical decision gate
            if config["critical"] and choice != config["default"]:
                confidence = user_overrides.get(f"{name}_confidence", 0.9)
                if confidence < 0.85:
                    print(f"  HALT: {name}={choice} needs confirmation "
                          f"(confidence {confidence} < 0.85, critical decision)")
                    active[name] = {
                        "choice":     choice,
                        "source":     "halted",
                        "confidence": confidence
                    }
                    continue
        else:
            choice = config["default"]
            source = "default"

        active[name] = {
            "choice": choice,
            "source": source
        }

    return active

# ── Detect conflicts ───────────────────────────────────────────────────────────

def detect_conflicts(active):
    found = []

    for conflict in CONFLICTS:
        a_name   = conflict["decision_a"]
        a_choice = conflict["choice_a"]
        b_name   = conflict["decision_b"]
        b_choice = conflict["choice_b"]

        a_active = active.get(a_name, {}).get("choice")
        b_active = active.get(b_name, {}).get("choice")

        if a_active == a_choice and b_active == b_choice:
            found.append(conflict)

    return found

# ── Main ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    scenarios = [
        (
            "Defaults only",
            {}
        ),
        (
            "UUID + multi-tenant",
            {"pk_strategy": "uuid", "tenancy_model": "multi_tenant"}
        ),
        (
            "Nested set + multi-tenant",
            {"hierarchy_approach": "nested_set", "tenancy_model": "multi_tenant"}
        ),
        (
            "Versioned + soft delete",
            {"temporal_strategy": "versioned"}
        ),
        (
            "Ambiguous tenancy (low confidence)",
            {"tenancy_model": "multi_tenant", "tenancy_model_confidence": 0.6}
        ),
    ]

    for label, overrides in scenarios:
        print(f"\n{'='*60}")
        print(f"Scenario: {label}")
        print(f"{'='*60}")

        active = build_active_decisions(overrides)

        # Show only non-default decisions
        explicit = [
            (k, v['choice'], v['source'])
            for k, v in active.items()
            if v['source'] != 'default'
        ]
        if explicit:
            print(f"  Active overrides: {explicit}")

        conflicts = detect_conflicts(active)

        if conflicts:
            for c in conflicts:
                icon = "✗" if c["category"] == "hard_incompatibility" else "⚠"
                print(f"\n  {icon} CONFLICT DETECTED!")
                print(f"    {c['decision_a']}={c['choice_a']} "
                      f"× {c['decision_b']}={c['choice_b']}")
                print(f"    Category:   {c['category']}")
                print(f"    Reason:     {c['reason']}")
                print(f"    Resolution: {c['resolution']}")
        else:
            print(f"  No conflicts detected!")
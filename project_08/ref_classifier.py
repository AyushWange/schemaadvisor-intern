# project_08/ref_classifier.py

all_references = [
    # Clean chain
    ("orders",          "customers",       True),
    ("order_items",     "orders",          True),
    ("order_items",     "products",        True),
    # Optional refs
    ("orders",          "shipping_address",False),
    ("invoices",        "sales_order",     False),
    # Cycle 1: purchase_order → supplier → supplier_group → purchase_order
    ("purchase_order",  "supplier",        True),
    ("supplier",        "supplier_group",  True),
    ("supplier_group",  "purchase_order",  True),
    # Cycle 2: employee → department → company → default_employee
    ("employee",        "department",      True),
    ("department",      "company",         True),
    ("company",         "default_employee",True),
]

KNOWN_TABLES = {
    "customers", "orders", "order_items", "products",
    "shipping_address", "invoices", "sales_order",
    "purchase_order", "supplier", "supplier_group",
    "employee", "department", "company", "default_employee",
}

# ── Pass 1: Static classification ─────────────────────────────────────────────

def pass1_classify(references, known_tables):
    candidate_enforced = []
    logical            = []

    for from_table, to_table, required in references:
        if required and to_table in known_tables:
            candidate_enforced.append((from_table, to_table))
        else:
            logical.append((from_table, to_table, "reqd=0 or target unknown"))

    print(f"Pass 1: {len(candidate_enforced)} candidate enforced, {len(logical)} logical")
    return candidate_enforced, logical

# ── Cycle detection using DFS ──────────────────────────────────────────────────

def find_cycles(edges):
    adj     = {}
    for src, dst in edges:
        adj.setdefault(src, []).append(dst)

    visited = set()
    path    = set()
    cycles  = []

    def dfs(node, current_path):
        visited.add(node)
        path.add(node)
        current_path.append(node)

        for neighbor in adj.get(node, []):
            if neighbor in path:
                cycle_start = current_path.index(neighbor)
                cycle       = current_path[cycle_start:] + [neighbor]
                cycles.append(cycle)
            elif neighbor not in visited:
                dfs(neighbor, current_path)

        path.remove(node)
        current_path.pop()

    for node in adj:
        if node not in visited:
            dfs(node, [])

    return cycles

# ── Strength scoring ───────────────────────────────────────────────────────────

def score_edge(from_table, to_table, all_enforced):
    inbound_count = sum(
        1 for s, d in all_enforced
        if d == to_table and s != from_table
    )

    if inbound_count >= 3:
        return 1.0
    elif inbound_count >= 1:
        return 0.7
    else:
        return 0.4

# ── Pass 2: Break cycles ───────────────────────────────────────────────────────

def pass2_break_cycles(candidate_enforced):
    enforced   = list(candidate_enforced)
    downgraded = []
    iteration  = 0

    while True:
        cycles = find_cycles(enforced)
        if not cycles:
            break

        iteration += 1
        cycle      = cycles[0]

        # Score all edges in this cycle
        cycle_edges = [(cycle[i], cycle[i+1]) for i in range(len(cycle)-1)]
        scored      = [(s, d, score_edge(s, d, enforced)) for s, d in cycle_edges]
        scored.sort(key=lambda x: x[2])

        # Downgrade weakest edge
        weakest = scored[0]
        enforced.remove((weakest[0], weakest[1]))
        downgraded.append({
            "from":       weakest[0],
            "to":         weakest[1],
            "strength":   weakest[2],
            "cycle_path": " → ".join(cycle),
        })

        print(f"  Iteration {iteration}: Downgraded {weakest[0]} → {weakest[1]} "
              f"(strength={weakest[2]}) | Cycle: {' → '.join(cycle)}")

    return enforced, downgraded

# ── Main ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("Pass 1: Static Classification")
    print("=" * 60)
    candidate, logical = pass1_classify(all_references, KNOWN_TABLES)
    print(f"  Candidate enforced: {candidate}")
    print(f"  Logical: {[f'{s}->{d}' for s, d, _ in logical]}")

    print()
    print("=" * 60)
    print("Pass 2: Cycle Resolution")
    print("=" * 60)
    final_enforced, downgrades = pass2_break_cycles(candidate)

    print()
    print("=" * 60)
    print("Final Result")
    print("=" * 60)
    print(f"  Enforced ({len(final_enforced)}): {final_enforced}")
    print(f"  Downgraded ({len(downgrades)}):")
    for d in downgrades:
        print(f"    {d['from']} → {d['to']} "
              f"(strength={d['strength']})")
        print(f"    Cycle was: {d['cycle_path']}")
        print(f"    Flag: downgraded_from_enforced=true")

    # Verify no cycles remain
    remaining = find_cycles(final_enforced)
    assert len(remaining) == 0, "Cycles still remain!"
    print(f"\n  Enforced graph is acyclic!")
    print(f"  {len(final_enforced)} edges survived!")
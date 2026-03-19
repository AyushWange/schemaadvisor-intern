# project_09/selector.py

CONCEPT_TABLES = {
    "e_commerce_orders": [
        {"name": "orders",        "tier": "required"},
        {"name": "order_items",   "tier": "required"},
        {"name": "customers",     "tier": "required"},
        {"name": "shopping_cart", "tier": "recommended"},
        {"name": "wishlists",     "tier": "suggested"},
        {"name": "gift_cards",    "tier": "suggested"},
    ],
    "invoicing": [
        {"name": "invoices",      "tier": "required"},
        {"name": "invoice_items", "tier": "required"},
        {"name": "tax_entries",   "tier": "required"},
        {"name": "customers",     "tier": "recommended"},
        {"name": "credit_notes",  "tier": "suggested"},
    ],
    "customer_management": [
        {"name": "customers",      "tier": "required"},
        {"name": "addresses",      "tier": "required"},
        {"name": "contacts",       "tier": "recommended"},
        {"name": "customer_notes", "tier": "suggested"},
    ],
}

CONCEPT_DEPS = {
    "invoicing":          ["customer_management"],
    "customer_management":[],
    "e_commerce_orders":  ["customer_management"],
}

TABLE_DEPS = {
    "orders":        ["customers"],
    "order_items":   ["orders", "products"],
    "invoices":      ["customers"],
    "invoice_items": ["invoices"],
    "tax_entries":   ["invoices"],
    "credit_notes":  ["invoices"],
}

COOCCURRENCE = {
    ("wishlists",      "orders"):    0.6,
    ("wishlists",      "customers"): 0.7,
    ("gift_cards",     "orders"):    0.3,
    ("gift_cards",     "customers"): 0.2,
    ("customer_notes", "customers"): 0.8,
    ("credit_notes",   "invoices"):  0.7,
}

TIER_RANK   = {"required": 3, "recommended": 2, "suggested": 1}
TIER_SCORES = {"required": 1.0, "recommended": 0.7, "suggested": 0.4}

def select_tables(active_concepts):

    # Step 1: Expand concept dependencies
    all_concepts = set()

    def expand(concept):
        if concept in all_concepts:
            return
        all_concepts.add(concept)
        for dep in CONCEPT_DEPS.get(concept, []):
            expand(dep)

    for c in active_concepts:
        expand(c)

    print(f"Step 1: Expanded concepts: {all_concepts}")

    # Step 2: Collect and merge tables
    merged = {}
    for concept in all_concepts:
        for table in CONCEPT_TABLES.get(concept, []):
            name = table["name"]
            if name not in merged or TIER_RANK[table["tier"]] > TIER_RANK[merged[name]["tier"]]:
                merged[name] = {**table, "triggered_by": [concept]}
            else:
                merged[name]["triggered_by"].append(concept)

    print(f"Step 2: Merged {len(merged)} tables")

    # Step 3: Pull in FK dependencies
    added_deps = []
    for name, table in list(merged.items()):
        if table["tier"] in ("required", "recommended"):
            for dep in TABLE_DEPS.get(name, []):
                if dep not in merged:
                    merged[dep] = {
                        "name":              dep,
                        "tier":              "required",
                        "triggered_by":      [f"dependency of {name}"],
                        "dependency_reason": f"Required by {name} (FK)",
                    }
                    added_deps.append(dep)

    if added_deps:
        print(f"Step 3: Added FK dependencies: {added_deps}")

    # Step 4: Prune suggested tables
    required_recommended = {
        n for n, t in merged.items()
        if t["tier"] in ("required", "recommended")
    }

    pruned = []
    for name, table in list(merged.items()):
        if table["tier"] == "suggested":
            max_freq = 0
            for rr in required_recommended:
                freq     = COOCCURRENCE.get((name, rr), COOCCURRENCE.get((rr, name), 0))
                max_freq = max(max_freq, freq)

            if max_freq < 0.5:
                pruned.append(f"{name} (max_freq={max_freq})")
                del merged[name]

    if pruned:
        print(f"Step 4: Pruned suggested tables: {pruned}")

    # Step 5: Compute confidence scores
    results = []
    for name, table in merged.items():
        tier_score  = TIER_SCORES.get(table["tier"], 0.5)
        confidence  = round(tier_score * 0.6 + 0.9 * 0.4, 2)
        table["inclusion_confidence"] = confidence
        results.append(table)

    results.sort(key=lambda x: -TIER_RANK.get(x["tier"], 0))
    return results


if __name__ == "__main__":
    print("=" * 60)
    print("Input: 'E-commerce platform with invoicing'")
    print("=" * 60)
    print()

    tables = select_tables(["e_commerce_orders", "invoicing"])

    print()
    print("=" * 60)
    print(f"Final Selection: {len(tables)} tables")
    print("=" * 60)
    for t in tables:
        triggered = ", ".join(t.get("triggered_by", []))
        dep       = f" [FK DEP: {t['dependency_reason']}]" if t.get("dependency_reason") else ""
        print(f"  {t['tier']:12} | {t['name']:20} | "
              f"conf={t['inclusion_confidence']} | from: {triggered}{dep}")

    # Assertions
    names = [t["name"] for t in tables]
    assert "gift_cards" not in names, "gift_cards should be pruned!"
    assert "wishlists"  in names,     "wishlists should be kept!"
    assert "customers"  in names,     "customers must be included!"
    assert "products"   in names,     "products must be pulled as FK dep!"

    print()
    print("All assertions passed!")
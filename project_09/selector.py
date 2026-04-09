# project_09/selector.py — Legacy Table Selection (test-compatible wrapper)
# Delegates to the authoritative implementation in project_08/table_selector.py
# but keeps backward-compatible local data for tests that import from here.

import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from project_08.table_selector import select_tables  # re-export

# ── Standalone test ────────────────────────────────────────────────────────────
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
        dep = f" [FK DEP: {t['dependency_reason']}]" if t.get("dependency_reason") else ""
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
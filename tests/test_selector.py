import pytest
from project_09.selector import select_tables

def test_concept_expansion():
    # Only supply invoicing, it should expand to include customer_management
    tables = select_tables(["invoicing"])
    names = [t["name"] for t in tables]
    
    # Invoicing has invoices, invoice_items, tax_entries
    assert "invoices" in names
    # Dependency customer_management has customers, addresses
    assert "customers" in names
    assert "addresses" in names

def test_tier_merge_highest_wins():
    tables = select_tables(["e_commerce_orders", "invoicing"])
    names = [t["name"] for t in tables]
    # e_commerce_orders has customers as 'required'
    # invoicing has customers as 'recommended'
    # 'required' should win.
    
    customer_table = next(t for t in tables if t["name"] == "customers")
    assert customer_table["tier"] == "required"

def test_fk_dependency_pull():
    tables = select_tables(["e_commerce_orders"])
    names = [t["name"] for t in tables]
    
    # e_commerce_orders does not explicitly list 'products'
    # but order_items has FK to products.
    # So 'products' should be pulled in.
    assert "products" in names

def test_suggested_pruning():
    tables = select_tables(["e_commerce_orders"])
    names = [t["name"] for t in tables]
    
    # wishlists has 0.6 cooccurrence with orders, 0.7 with customers -> Kept
    assert "wishlists" in names
    
    # gift_cards has 0.3 with orders, 0.2 with customers -> Pruned
    assert "gift_cards" not in names

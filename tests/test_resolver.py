import pytest
from project_01.resolver import kahns_sort

def test_simple_ecommerce_order():
    dependencies = {
        "customers": [],
        "products": [],
        "orders": ["customers"],
        "order_items": ["orders", "products"],
        "payments": ["orders"],
        "shipping": ["orders", "customers"],
    }
    
    order = kahns_sort(dependencies)
    
    # Assert all tables are present
    assert len(order) == 6
    
    # Assert correct dependency order
    assert order.index("customers") < order.index("orders")
    assert order.index("products") < order.index("order_items")
    assert order.index("orders") < order.index("order_items")
    assert order.index("orders") < order.index("payments")
    assert order.index("orders") < order.index("shipping")
    assert order.index("customers") < order.index("shipping")

def test_circular_dependency_raises():
    dependencies = {
        "A": ["B"],
        "B": ["C"],
        "C": ["A"],  # Cycle
        "D": []
    }
    
    with pytest.raises(Exception, match="Circular dependency detected"):
        kahns_sort(dependencies)

def test_single_table():
    dependencies = {"only_table": []}
    order = kahns_sort(dependencies)
    assert order == ["only_table"]

def test_independent_tables():
    dependencies = {"A": [], "B": [], "C": []}
    order = kahns_sort(dependencies)
    assert sorted(order) == ["A", "B", "C"]

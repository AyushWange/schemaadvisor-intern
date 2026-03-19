from collections import deque

def kahns_sort(dependencies: dict) -> list[str]:
    # Step 1: Initialize in-degree map
    in_degree = {table: 0 for table in dependencies}
    for table, deps in dependencies.items():
        in_degree[table] = len(deps)
    
    # Step 2: Queue tables with 0 dependencies
    queue = deque(sorted([t for t, d in in_degree.items() if d == 0]))
    
    # Step 3: Process the queue
    result = []
    # Build reverse adjacency list: who depends on me?
    dependents = {t: [] for t in dependencies}
    for table, deps in dependencies.items():
        for dep in deps:
            dependents[dep].append(table)

    while queue:
        table = queue.popleft()
        result.append(table)
        for dependent in sorted(dependents[table]):
            in_degree[dependent] -= 1
            if in_degree[dependent] == 0:
                queue.append(dependent)

    # Step 4: Detect cycles
    if len(result) != len(dependencies):
        remaining = [t for t in dependencies if t not in result]
        raise Exception(f"Circular dependency detected! Stuck tables: {remaining}")

    return result

if __name__ == "__main__":
    # Test Case 1: Simple e-commerce
    dependencies_simple = {
        "customers":[],
        "products":[],
        "orders": ["customers"],
        "order_items": ["orders", "products"],
        "payments": ["orders"],
        "shipping": ["orders", "customers"],
    }
    
    print("=== Test 1: Simple E-commerce ===")
    order = kahns_sort(dependencies_simple) # This calls your function
    print(" -> ".join(order)) # This prints the result
    print(" All dependencies satisfied!\n")
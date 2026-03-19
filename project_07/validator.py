import psycopg2
import time
import uuid

# ── Test DDL statements ────────────────────────────────────────────────────────

DDL_CORRECT = [
    (
        "customers",
        """CREATE TABLE customers (
            id         BIGSERIAL PRIMARY KEY,
            name       VARCHAR(255) NOT NULL,
            email      VARCHAR(255) UNIQUE,
            created_at TIMESTAMP NOT NULL DEFAULT NOW()
        );"""
    ),
    (
        "orders",
        """CREATE TABLE orders (
            id          BIGSERIAL PRIMARY KEY,
            customer_id BIGINT NOT NULL,
            total       DECIMAL(18,6) NOT NULL,
            status      VARCHAR(50) DEFAULT 'draft',
            created_at  TIMESTAMP NOT NULL DEFAULT NOW(),
            FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE CASCADE
        );"""
    ),
    (
        "order_items",
        """CREATE TABLE order_items (
            id           BIGSERIAL PRIMARY KEY,
            order_id     BIGINT NOT NULL,
            product_name VARCHAR(255) NOT NULL,
            quantity     INTEGER DEFAULT 1,
            unit_price   DECIMAL(18,6) NOT NULL,
            FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE
        );"""
    ),
]

# Wrong order: order_items first, then orders, then customers
DDL_WRONG_ORDER = [
    DDL_CORRECT[2],  # order_items  (needs orders!)
    DDL_CORRECT[1],  # orders       (needs customers!)
    DDL_CORRECT[0],  # customers    (no dependencies)
]

# ── Validation engine ──────────────────────────────────────────────────────────

def validate_ddl(statements, label="test"):
    # Create a unique test database name
    db = f"val_{uuid.uuid4().hex[:8]}"

    # Connect to default database first
    conn = psycopg2.connect(
        host     = "localhost",
        port     = 5432,
        user     = "postgres",
        password = "internpass",
        dbname   = "schema_test"
    )
    conn.autocommit = True
    conn.cursor().execute(f"CREATE DATABASE {db}")
    conn.close()

    # Connect to new test database
    conn = psycopg2.connect(
        host     = "localhost",
        port     = 5432,
        user     = "postgres",
        password = "internpass",
        dbname   = db
    )
    cur     = conn.cursor()
    results = []
    start   = time.time()

    # Run each statement
    for name, sql in statements:
        try:
            cur.execute(sql)
            conn.commit()
            results.append({
                "table":  name,
                "status": "success"
            })
        except Exception as e:
            results.append({
                "table":  name,
                "status": "failed",
                "error":  str(e).split("\n")[0]
            })
            conn.rollback()

    elapsed = int((time.time() - start) * 1000)
    cur.close()
    conn.close()

    # Cleanup test database
    conn = psycopg2.connect(
        host     = "localhost",
        port     = 5432,
        user     = "postgres",
        password = "internpass",
        dbname   = "schema_test"
    )
    conn.autocommit = True
    conn.cursor().execute(f"DROP DATABASE IF EXISTS {db}")
    conn.close()

    # Print results
    ok = sum(1 for r in results if r["status"] == "success")
    print(f"\n  Results ({ok}/{len(results)} in {elapsed}ms):")
    for r in results:
        icon = "✓" if r["status"] == "success" else "✗"
        line = f"    {icon} {r['table']}"
        if r.get("error"):
            line += f" — {r['error']}"
        print(line)

    return results


# ── Main ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("Test 1: Correct order (Kahn's output)")
    print("=" * 60)
    validate_ddl(DDL_CORRECT)

    print()
    print("=" * 60)
    print("Test 2: Wrong order (should fail)")
    print("=" * 60)
    validate_ddl(DDL_WRONG_ORDER)

    print()
    print("Proves that Kahn's ordering (Project 1) is essential!")
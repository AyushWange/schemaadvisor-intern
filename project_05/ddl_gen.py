from jinja2 import Environment, FileSystemLoader

tables = [
    {
        "name": "customers",
        "columns": [
            {"name": "id",         "data_type": "BIGSERIAL",    "primary_key": True,  "nullable": False},
            {"name": "name",       "data_type": "VARCHAR(255)", "primary_key": False, "nullable": False},
            {"name": "email",      "data_type": "VARCHAR(255)", "primary_key": False, "nullable": True,  "unique": True},
            {"name": "created_at", "data_type": "TIMESTAMP",    "primary_key": False, "nullable": False, "default_value": "NOW()"},
        ],
        "enforced_fks": [],
        "logical_refs":  [],
    },
    {
        "name": "orders",
        "columns": [
            {"name": "id",                  "data_type": "BIGSERIAL",    "primary_key": True,  "nullable": False},
            {"name": "customer_id",         "data_type": "BIGINT",       "primary_key": False, "nullable": False},
            {"name": "total",               "data_type": "DECIMAL(18,6)","primary_key": False, "nullable": False},
            {"name": "status",              "data_type": "VARCHAR(50)",  "primary_key": False, "nullable": False, "default_value": "'draft'"},
            {"name": "shipping_address_id", "data_type": "BIGINT",       "primary_key": False, "nullable": True},
            {"name": "created_at",          "data_type": "TIMESTAMP",    "primary_key": False, "nullable": False, "default_value": "NOW()"},
        ],
        "enforced_fks": [
            {
                "from_column": "customer_id",
                "to_table":    "customers",
                "to_column":   "id",
                "on_delete":   "CASCADE"
            }
        ],
        "logical_refs": [
            {
                "from_column": "shipping_address_id",
                "to_table":    "addresses",
                "to_column":   "id",
                "comment":     "Optional link to shipping address (not enforced)"
            }
        ],
    },
]

def generate_ddl(tables):
    env      = Environment(loader=FileSystemLoader("."))
    template = env.get_template("create_table.sql.j2")
    parts    = ["BEGIN;", ""]

    for table in tables:
        parts.append(template.render(table=table))

    parts.append("COMMIT;")
    return "\n".join(parts)

if __name__ == "__main__":
    ddl = generate_ddl(tables)
    print(ddl)

    with open("output.sql", "w") as f:
        f.write(ddl)
    print("\nDDL written to output.sql")
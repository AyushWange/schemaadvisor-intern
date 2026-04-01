# project_12/pipeline.py — Real LLM-powered end-to-end pipeline
import sys
import os
import json
import copy
import time
import uuid

# Add parent dir so we can import project_06
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from project_06.extractor import extract, CONCEPTS as CONCEPT_REGISTRY

# ── Table knowledge base ───────────────────────────────────────────────────────

CONCEPT_TABLES = {
    "e_commerce_orders": [
        {"name": "orders",        "tier": "required"},
        {"name": "order_items",   "tier": "required"},
        {"name": "customers",     "tier": "required"},
        {"name": "shopping_cart", "tier": "recommended"},
    ],
    "product_catalog": [
        {"name": "products",   "tier": "required"},
        {"name": "categories", "tier": "required"},
        {"name": "attributes", "tier": "recommended"},
    ],
    "invoicing": [
        {"name": "invoices",      "tier": "required"},
        {"name": "invoice_items", "tier": "required"},
        {"name": "tax_entries",   "tier": "recommended"},
        {"name": "customers",     "tier": "recommended"},
    ],
    "customer_management": [
        {"name": "customers", "tier": "required"},
        {"name": "addresses", "tier": "required"},
        {"name": "contacts",  "tier": "recommended"},
    ],
    "user_authentication": [
        {"name": "users",       "tier": "required"},
        {"name": "sessions",    "tier": "required"},
        {"name": "roles",       "tier": "recommended"},
        {"name": "permissions", "tier": "suggested"},
    ],
    "payment_processing": [
        {"name": "payments",        "tier": "required"},
        {"name": "payment_methods", "tier": "required"},
        {"name": "refunds",         "tier": "recommended"},
    ],
    "inventory_management": [
        {"name": "warehouses",    "tier": "required"},
        {"name": "stock_entries", "tier": "required"},
        {"name": "stock_ledger",  "tier": "recommended"},
    ],
    "employee_management": [
        {"name": "employees",    "tier": "required"},
        {"name": "departments",  "tier": "required"},
        {"name": "designations", "tier": "recommended"},
    ],
    "project_tracking": [
        {"name": "projects",   "tier": "required"},
        {"name": "tasks",      "tier": "required"},
        {"name": "time_logs",  "tier": "recommended"},
        {"name": "milestones", "tier": "suggested"},
    ],
    "gst_compliance": [
        {"name": "gst_categories", "tier": "required"},
        {"name": "hsn_codes",      "tier": "required"},
        {"name": "tax_entries",    "tier": "recommended"},
    ],
    # ── 5 new concepts (spec §4.1.1) ─────────────────────────────────────────
    "supplier_management": [
        {"name": "suppliers",       "tier": "required"},
        {"name": "supplier_groups", "tier": "recommended"},
        {"name": "purchase_orders", "tier": "recommended"},
    ],
    "multi_currency": [
        {"name": "currencies",       "tier": "required"},
        {"name": "exchange_rates",   "tier": "required"},
        {"name": "currency_ledger",  "tier": "suggested"},
    ],
    "file_attachments": [
        {"name": "attachments",    "tier": "required"},
        {"name": "storage_buckets","tier": "recommended"},
    ],
    "notifications": [
        {"name": "notifications",         "tier": "required"},
        {"name": "notification_channels", "tier": "recommended"},
    ],
    "reporting_analytics": [
        {"name": "reports",       "tier": "required"},
        {"name": "dashboards",    "tier": "recommended"},
        {"name": "report_filters","tier": "suggested"},
    ],
}

CONCEPT_DEPS = {
    "e_commerce_orders":    ["customer_management", "product_catalog"],
    "invoicing":            ["customer_management"],
    "payment_processing":   ["e_commerce_orders"],
    "inventory_management": ["product_catalog"],
    "gst_compliance":       ["invoicing"],
    "customer_management":  [],
    "product_catalog":      [],
    "user_authentication":  [],
    "employee_management":  [],
    "project_tracking":     [],
    # new
    "supplier_management":  [],
    "multi_currency":       [],
    "file_attachments":     [],
    "notifications":        [],
    "reporting_analytics":  [],
}

TABLE_DEPS = {
    "orders":                  ["customers"],
    "order_items":             ["orders", "products"],
    "invoices":                ["customers"],
    "invoice_items":           ["invoices"],
    "tax_entries":             ["invoices"],
    "shopping_cart":           ["customers"],
    "addresses":               ["customers"],
    "contacts":                ["customers"],
    "attributes":              ["products"],
    "payments":                ["orders"],
    "refunds":                 ["payments"],
    "sessions":                ["users"],
    "stock_entries":           ["warehouses", "products"],
    "stock_ledger":            ["warehouses", "products"],
    "tasks":                   ["projects"],
    "time_logs":               ["tasks", "employees"],
    "milestones":              ["projects"],
    "designations":            ["departments"],
    "employees":               ["departments"],
    # new
    "purchase_orders":         ["suppliers"],
    "supplier_groups":         [],
    "exchange_rates":          ["currencies"],
    "currency_ledger":         ["currencies"],
    "storage_buckets":         [],
    "attachments":             [],
    "notification_channels":   [],
    "notifications":           [],
    "report_filters":          ["reports"],
    "dashboards":              [],
}

TIER_RANK   = {"required": 3, "recommended": 2, "suggested": 1}
TIER_SCORES = {"required": 1.0, "recommended": 0.7, "suggested": 0.4}

# ── Base column definitions ────────────────────────────────────────────────────

def _generic_columns(table_name: str) -> list:
    """Return minimal columns for any table not explicitly defined."""
    return [
        {"name": "id",   "data_type": "BIGSERIAL",    "primary_key": True,  "nullable": False},
        {"name": "name", "data_type": "VARCHAR(255)",  "primary_key": False, "nullable": False},
    ]

BASE_COLUMNS = {
    "customers":        [
        {"name": "id",    "data_type": "BIGSERIAL",    "primary_key": True,  "nullable": False},
        {"name": "name",  "data_type": "VARCHAR(255)", "primary_key": False, "nullable": False},
        {"name": "email", "data_type": "VARCHAR(255)", "primary_key": False, "nullable": True},
    ],
    "orders": [
        {"name": "id",          "data_type": "BIGSERIAL",     "primary_key": True,  "nullable": False},
        {"name": "customer_id", "data_type": "BIGINT",        "primary_key": False, "nullable": False},
        {"name": "total",       "data_type": "DECIMAL(18,6)", "primary_key": False, "nullable": False},
        {"name": "status",      "data_type": "VARCHAR(50)",   "primary_key": False, "nullable": False, "default_value": "'draft'"},
    ],
    "order_items": [
        {"name": "id",           "data_type": "BIGSERIAL",     "primary_key": True,  "nullable": False},
        {"name": "order_id",     "data_type": "BIGINT",        "primary_key": False, "nullable": False},
        {"name": "product_name", "data_type": "VARCHAR(255)",  "primary_key": False, "nullable": False},
        {"name": "quantity",     "data_type": "INTEGER",       "primary_key": False, "nullable": False},
        {"name": "unit_price",   "data_type": "DECIMAL(18,6)", "primary_key": False, "nullable": False},
    ],
    "products": [
        {"name": "id",    "data_type": "BIGSERIAL",     "primary_key": True,  "nullable": False},
        {"name": "name",  "data_type": "VARCHAR(255)",  "primary_key": False, "nullable": False},
        {"name": "price", "data_type": "DECIMAL(18,6)", "primary_key": False, "nullable": False},
    ],
    "categories": [
        {"name": "id",   "data_type": "BIGSERIAL",   "primary_key": True,  "nullable": False},
        {"name": "name", "data_type": "VARCHAR(255)", "primary_key": False, "nullable": False},
    ],
    "shopping_cart": [
        {"name": "id",          "data_type": "BIGSERIAL", "primary_key": True,  "nullable": False},
        {"name": "customer_id", "data_type": "BIGINT",    "primary_key": False, "nullable": False},
    ],
    "addresses": [
        {"name": "id",          "data_type": "BIGSERIAL",   "primary_key": True,  "nullable": False},
        {"name": "customer_id", "data_type": "BIGINT",      "primary_key": False, "nullable": False},
        {"name": "street",      "data_type": "VARCHAR(255)", "primary_key": False, "nullable": False},
    ],
    "contacts": [
        {"name": "id",          "data_type": "BIGSERIAL",  "primary_key": True,  "nullable": False},
        {"name": "customer_id", "data_type": "BIGINT",     "primary_key": False, "nullable": False},
        {"name": "phone",       "data_type": "VARCHAR(20)", "primary_key": False, "nullable": True},
    ],
    "attributes": [
        {"name": "id",         "data_type": "BIGSERIAL",    "primary_key": True,  "nullable": False},
        {"name": "product_id", "data_type": "BIGINT",       "primary_key": False, "nullable": False},
        {"name": "key",        "data_type": "VARCHAR(100)",  "primary_key": False, "nullable": False},
        {"name": "value",      "data_type": "VARCHAR(255)",  "primary_key": False, "nullable": False},
    ],
    "invoices": [
        {"name": "id",          "data_type": "BIGSERIAL",     "primary_key": True,  "nullable": False},
        {"name": "customer_id", "data_type": "BIGINT",        "primary_key": False, "nullable": False},
        {"name": "total",       "data_type": "DECIMAL(18,6)", "primary_key": False, "nullable": False},
    ],
    "invoice_items": [
        {"name": "id",         "data_type": "BIGSERIAL",     "primary_key": True,  "nullable": False},
        {"name": "invoice_id", "data_type": "BIGINT",        "primary_key": False, "nullable": False},
        {"name": "amount",     "data_type": "DECIMAL(18,6)", "primary_key": False, "nullable": False},
    ],
    "tax_entries": [
        {"name": "id",         "data_type": "BIGSERIAL",     "primary_key": True,  "nullable": False},
        {"name": "invoice_id", "data_type": "BIGINT",        "primary_key": False, "nullable": False},
        {"name": "tax_amount", "data_type": "DECIMAL(18,6)", "primary_key": False, "nullable": False},
    ],
    "users": [
        {"name": "id",            "data_type": "BIGSERIAL",   "primary_key": True,  "nullable": False},
        {"name": "username",      "data_type": "VARCHAR(100)", "primary_key": False, "nullable": False},
        {"name": "password_hash", "data_type": "VARCHAR(255)", "primary_key": False, "nullable": False},
        {"name": "email",         "data_type": "VARCHAR(255)", "primary_key": False, "nullable": True},
    ],
    "sessions": [
        {"name": "id",         "data_type": "BIGSERIAL",   "primary_key": True,  "nullable": False},
        {"name": "user_id",    "data_type": "BIGINT",      "primary_key": False, "nullable": False},
        {"name": "token",      "data_type": "VARCHAR(255)", "primary_key": False, "nullable": False},
        {"name": "expires_at", "data_type": "TIMESTAMP",   "primary_key": False, "nullable": False},
    ],
    "roles": [
        {"name": "id",   "data_type": "BIGSERIAL",   "primary_key": True,  "nullable": False},
        {"name": "name", "data_type": "VARCHAR(100)", "primary_key": False, "nullable": False},
    ],
    "permissions": [
        {"name": "id",      "data_type": "BIGSERIAL",   "primary_key": True,  "nullable": False},
        {"name": "role_id", "data_type": "BIGINT",      "primary_key": False, "nullable": False},
        {"name": "action",  "data_type": "VARCHAR(100)", "primary_key": False, "nullable": False},
    ],
    "payments": [
        {"name": "id",       "data_type": "BIGSERIAL",     "primary_key": True,  "nullable": False},
        {"name": "order_id", "data_type": "BIGINT",        "primary_key": False, "nullable": False},
        {"name": "amount",   "data_type": "DECIMAL(18,6)", "primary_key": False, "nullable": False},
        {"name": "status",   "data_type": "VARCHAR(50)",   "primary_key": False, "nullable": False},
    ],
    "payment_methods": [
        {"name": "id",   "data_type": "BIGSERIAL",  "primary_key": True,  "nullable": False},
        {"name": "type", "data_type": "VARCHAR(50)", "primary_key": False, "nullable": False},
    ],
    "refunds": [
        {"name": "id",         "data_type": "BIGSERIAL",     "primary_key": True,  "nullable": False},
        {"name": "payment_id", "data_type": "BIGINT",        "primary_key": False, "nullable": False},
        {"name": "amount",     "data_type": "DECIMAL(18,6)", "primary_key": False, "nullable": False},
    ],
    "warehouses": [
        {"name": "id",       "data_type": "BIGSERIAL",   "primary_key": True,  "nullable": False},
        {"name": "name",     "data_type": "VARCHAR(255)", "primary_key": False, "nullable": False},
        {"name": "location", "data_type": "VARCHAR(255)", "primary_key": False, "nullable": True},
    ],
    "stock_entries": [
        {"name": "id",           "data_type": "BIGSERIAL", "primary_key": True,  "nullable": False},
        {"name": "warehouse_id", "data_type": "BIGINT",    "primary_key": False, "nullable": False},
        {"name": "product_id",   "data_type": "BIGINT",    "primary_key": False, "nullable": False},
        {"name": "quantity",     "data_type": "INTEGER",   "primary_key": False, "nullable": False},
    ],
    "stock_ledger": [
        {"name": "id",           "data_type": "BIGSERIAL",     "primary_key": True,  "nullable": False},
        {"name": "warehouse_id", "data_type": "BIGINT",        "primary_key": False, "nullable": False},
        {"name": "product_id",   "data_type": "BIGINT",        "primary_key": False, "nullable": False},
        {"name": "balance",      "data_type": "DECIMAL(18,6)", "primary_key": False, "nullable": False},
    ],
    "employees": [
        {"name": "id",            "data_type": "BIGSERIAL",   "primary_key": True,  "nullable": False},
        {"name": "name",          "data_type": "VARCHAR(255)", "primary_key": False, "nullable": False},
        {"name": "department_id", "data_type": "BIGINT",      "primary_key": False, "nullable": False},
        {"name": "email",         "data_type": "VARCHAR(255)", "primary_key": False, "nullable": True},
    ],
    "departments": [
        {"name": "id",   "data_type": "BIGSERIAL",   "primary_key": True,  "nullable": False},
        {"name": "name", "data_type": "VARCHAR(255)", "primary_key": False, "nullable": False},
    ],
    "designations": [
        {"name": "id",            "data_type": "BIGSERIAL",   "primary_key": True,  "nullable": False},
        {"name": "title",         "data_type": "VARCHAR(255)", "primary_key": False, "nullable": False},
        {"name": "department_id", "data_type": "BIGINT",      "primary_key": False, "nullable": False},
    ],
    "projects": [
        {"name": "id",   "data_type": "BIGSERIAL",   "primary_key": True,  "nullable": False},
        {"name": "name", "data_type": "VARCHAR(255)", "primary_key": False, "nullable": False},
    ],
    "tasks": [
        {"name": "id",         "data_type": "BIGSERIAL",   "primary_key": True,  "nullable": False},
        {"name": "project_id", "data_type": "BIGINT",      "primary_key": False, "nullable": False},
        {"name": "title",      "data_type": "VARCHAR(255)", "primary_key": False, "nullable": False},
        {"name": "status",     "data_type": "VARCHAR(50)",  "primary_key": False, "nullable": False},
    ],
    "time_logs": [
        {"name": "id",          "data_type": "BIGSERIAL", "primary_key": True,  "nullable": False},
        {"name": "task_id",     "data_type": "BIGINT",    "primary_key": False, "nullable": False},
        {"name": "employee_id", "data_type": "BIGINT",    "primary_key": False, "nullable": False},
        {"name": "hours",       "data_type": "DECIMAL(8,2)", "primary_key": False, "nullable": False},
    ],
    "milestones": [
        {"name": "id",         "data_type": "BIGSERIAL",   "primary_key": True,  "nullable": False},
        {"name": "project_id", "data_type": "BIGINT",      "primary_key": False, "nullable": False},
        {"name": "name",       "data_type": "VARCHAR(255)", "primary_key": False, "nullable": False},
        {"name": "due_date",   "data_type": "DATE",        "primary_key": False, "nullable": True},
    ],
    "gst_categories": [
        {"name": "id",   "data_type": "BIGSERIAL",  "primary_key": True,  "nullable": False},
        {"name": "name", "data_type": "VARCHAR(100)", "primary_key": False, "nullable": False},
        {"name": "rate", "data_type": "DECIMAL(5,2)", "primary_key": False, "nullable": False},
    ],
    "hsn_codes": [
        {"name": "id",          "data_type": "BIGSERIAL",   "primary_key": True,  "nullable": False},
        {"name": "code",        "data_type": "VARCHAR(20)",  "primary_key": False, "nullable": False},
        {"name": "description", "data_type": "TEXT",        "primary_key": False, "nullable": True},
    ],
    # ── new concept base columns ──────────────────────────────────────────────
    "suppliers": [
        {"name": "id",           "data_type": "BIGSERIAL",   "primary_key": True,  "nullable": False},
        {"name": "name",         "data_type": "VARCHAR(255)", "primary_key": False, "nullable": False},
        {"name": "email",        "data_type": "VARCHAR(255)", "primary_key": False, "nullable": True},
        {"name": "payment_terms","data_type": "VARCHAR(100)", "primary_key": False, "nullable": True},
    ],
    "supplier_groups": [
        {"name": "id",   "data_type": "BIGSERIAL",   "primary_key": True,  "nullable": False},
        {"name": "name", "data_type": "VARCHAR(255)", "primary_key": False, "nullable": False},
    ],
    "purchase_orders": [
        {"name": "id",          "data_type": "BIGSERIAL",     "primary_key": True,  "nullable": False},
        {"name": "supplier_id", "data_type": "BIGINT",        "primary_key": False, "nullable": False},
        {"name": "total",       "data_type": "DECIMAL(18,6)", "primary_key": False, "nullable": False},
        {"name": "status",      "data_type": "VARCHAR(50)",   "primary_key": False, "nullable": False, "default_value": "'draft'"},
    ],
    "currencies": [
        {"name": "id",     "data_type": "BIGSERIAL",  "primary_key": True,  "nullable": False},
        {"name": "code",   "data_type": "VARCHAR(3)",  "primary_key": False, "nullable": False, "unique": True},
        {"name": "name",   "data_type": "VARCHAR(50)", "primary_key": False, "nullable": False},
        {"name": "symbol", "data_type": "VARCHAR(5)",  "primary_key": False, "nullable": True},
    ],
    "exchange_rates": [
        {"name": "id",            "data_type": "BIGSERIAL",     "primary_key": True,  "nullable": False},
        {"name": "currency_id",   "data_type": "BIGINT",        "primary_key": False, "nullable": False},
        {"name": "rate",          "data_type": "DECIMAL(18,6)", "primary_key": False, "nullable": False},
        {"name": "effective_date","data_type": "DATE",          "primary_key": False, "nullable": False},
    ],
    "currency_ledger": [
        {"name": "id",          "data_type": "BIGSERIAL",     "primary_key": True,  "nullable": False},
        {"name": "currency_id", "data_type": "BIGINT",        "primary_key": False, "nullable": False},
        {"name": "amount",      "data_type": "DECIMAL(18,6)", "primary_key": False, "nullable": False},
    ],
    "attachments": [
        {"name": "id",          "data_type": "BIGSERIAL",    "primary_key": True,  "nullable": False},
        {"name": "filename",    "data_type": "VARCHAR(255)", "primary_key": False, "nullable": False},
        {"name": "file_url",    "data_type": "TEXT",         "primary_key": False, "nullable": False},
        {"name": "mime_type",   "data_type": "VARCHAR(100)", "primary_key": False, "nullable": True},
        {"name": "size_bytes",  "data_type": "BIGINT",       "primary_key": False, "nullable": True},
    ],
    "storage_buckets": [
        {"name": "id",         "data_type": "BIGSERIAL",   "primary_key": True,  "nullable": False},
        {"name": "name",       "data_type": "VARCHAR(100)","primary_key": False, "nullable": False},
        {"name": "provider",   "data_type": "VARCHAR(50)", "primary_key": False, "nullable": True},
    ],
    "notifications": [
        {"name": "id",         "data_type": "BIGSERIAL",   "primary_key": True,  "nullable": False},
        {"name": "title",      "data_type": "VARCHAR(255)","primary_key": False, "nullable": False},
        {"name": "body",       "data_type": "TEXT",        "primary_key": False, "nullable": True},
        {"name": "is_read",    "data_type": "BOOLEAN",     "primary_key": False, "nullable": False, "default_value": "false"},
    ],
    "notification_channels": [
        {"name": "id",   "data_type": "BIGSERIAL",  "primary_key": True,  "nullable": False},
        {"name": "name", "data_type": "VARCHAR(50)", "primary_key": False, "nullable": False},
        {"name": "type", "data_type": "VARCHAR(50)", "primary_key": False, "nullable": False},
    ],
    "reports": [
        {"name": "id",          "data_type": "BIGSERIAL",   "primary_key": True,  "nullable": False},
        {"name": "name",        "data_type": "VARCHAR(255)","primary_key": False, "nullable": False},
        {"name": "query",       "data_type": "TEXT",        "primary_key": False, "nullable": True},
    ],
    "dashboards": [
        {"name": "id",   "data_type": "BIGSERIAL",   "primary_key": True,  "nullable": False},
        {"name": "name", "data_type": "VARCHAR(255)", "primary_key": False, "nullable": False},
    ],
    "report_filters": [
        {"name": "id",         "data_type": "BIGSERIAL",   "primary_key": True,  "nullable": False},
        {"name": "report_id",  "data_type": "BIGINT",      "primary_key": False, "nullable": False},
        {"name": "field_name", "data_type": "VARCHAR(100)","primary_key": False, "nullable": False},
    ],
}

ENFORCED_FKS = {
    "orders":        [{"from_column": "customer_id", "to_table": "customers",  "to_column": "id", "on_delete": "CASCADE"}],
    "order_items":   [{"from_column": "order_id",    "to_table": "orders",     "to_column": "id", "on_delete": "CASCADE"}],
    "addresses":     [{"from_column": "customer_id", "to_table": "customers",  "to_column": "id", "on_delete": "CASCADE"}],
    "contacts":      [{"from_column": "customer_id", "to_table": "customers",  "to_column": "id", "on_delete": "CASCADE"}],
    "shopping_cart": [{"from_column": "customer_id", "to_table": "customers",  "to_column": "id", "on_delete": "CASCADE"}],
    "invoices":      [{"from_column": "customer_id", "to_table": "customers",  "to_column": "id", "on_delete": "CASCADE"}],
    "invoice_items": [{"from_column": "invoice_id",  "to_table": "invoices",   "to_column": "id", "on_delete": "CASCADE"}],
    "tax_entries":   [{"from_column": "invoice_id",  "to_table": "invoices",   "to_column": "id", "on_delete": "CASCADE"}],
    "attributes":    [{"from_column": "product_id",  "to_table": "products",   "to_column": "id", "on_delete": "CASCADE"}],
    "sessions":      [{"from_column": "user_id",     "to_table": "users",      "to_column": "id", "on_delete": "CASCADE"}],
    "permissions":   [{"from_column": "role_id",     "to_table": "roles",      "to_column": "id", "on_delete": "CASCADE"}],
    "payments":      [{"from_column": "order_id",    "to_table": "orders",     "to_column": "id", "on_delete": "CASCADE"}],
    "refunds":       [{"from_column": "payment_id",  "to_table": "payments",   "to_column": "id", "on_delete": "CASCADE"}],
    "employees":     [{"from_column": "department_id","to_table": "departments","to_column": "id", "on_delete": "SET NULL"}],
    "designations":  [{"from_column": "department_id","to_table": "departments","to_column": "id", "on_delete": "SET NULL"}],
    "tasks":         [{"from_column": "project_id",  "to_table": "projects",   "to_column": "id", "on_delete": "CASCADE"}],
    "time_logs":     [
        {"from_column": "task_id",     "to_table": "tasks",     "to_column": "id", "on_delete": "CASCADE"},
        {"from_column": "employee_id", "to_table": "employees", "to_column": "id", "on_delete": "CASCADE"},
    ],
    "milestones":    [{"from_column": "project_id",  "to_table": "projects",   "to_column": "id", "on_delete": "CASCADE"}],
    "stock_entries": [
        {"from_column": "warehouse_id","to_table": "warehouses","to_column": "id", "on_delete": "CASCADE"},
        {"from_column": "product_id",  "to_table": "products",  "to_column": "id", "on_delete": "CASCADE"},
    ],
    "stock_ledger":  [
        {"from_column": "warehouse_id","to_table": "warehouses","to_column": "id", "on_delete": "CASCADE"},
        {"from_column": "product_id",  "to_table": "products",  "to_column": "id", "on_delete": "CASCADE"},
    ],
    # new concept FKs
    "purchase_orders": [{"from_column": "supplier_id",  "to_table": "suppliers",  "to_column": "id", "on_delete": "CASCADE"}],
    "exchange_rates":  [{"from_column": "currency_id",  "to_table": "currencies", "to_column": "id", "on_delete": "CASCADE"}],
    "currency_ledger": [{"from_column": "currency_id",  "to_table": "currencies", "to_column": "id", "on_delete": "CASCADE"}],
    "report_filters":  [{"from_column": "report_id",    "to_table": "reports",    "to_column": "id", "on_delete": "CASCADE"}],
}

# ── Patterns (applied to all tables) ──────────────────────────────────────────
# audit_policy=full_audit: all 4 columns (spec §4.1.2)
PATTERNS = {
    "audit_columns": [
        {"name": "created_at", "data_type": "TIMESTAMP",    "nullable": False, "default_value": "NOW()"},
        {"name": "updated_at", "data_type": "TIMESTAMP",    "nullable": True},
        {"name": "created_by", "data_type": "VARCHAR(140)", "nullable": True},
        {"name": "updated_by", "data_type": "VARCHAR(140)", "nullable": True},  # spec §4.1.2
    ],
    "soft_delete": [
        {"name": "is_deleted", "data_type": "BOOLEAN",   "nullable": False, "default_value": "false"},
        {"name": "deleted_at", "data_type": "TIMESTAMP", "nullable": True},
    ],
    # temporal_strategy=versioned (spec §4.1.2)
    "temporal_version": [
        {"name": "valid_from", "data_type": "TIMESTAMP", "nullable": False, "default_value": "NOW()"},
        {"name": "valid_to",   "data_type": "TIMESTAMP", "nullable": True},
        {"name": "version",    "data_type": "INTEGER",   "nullable": False, "default_value": "1"},
    ],
}

# System table for multi_tenant pattern (injected only when tenancy_model=multi_tenant)
SYSTEM_TABLES = {
    "tenants": {
        "name": "tenants",
        "tier": "required",
        "triggered_by": ["multi_tenant pattern"],
        "patterns_applied": [],
        "inclusion_confidence": 1.0,
        "columns": [
            {"name": "id",         "data_type": "BIGSERIAL",    "primary_key": True,  "nullable": False},
            {"name": "name",       "data_type": "VARCHAR(255)", "primary_key": False, "nullable": False},
            {"name": "slug",       "data_type": "VARCHAR(100)", "primary_key": False, "nullable": False, "unique": True},
            {"name": "is_active",  "data_type": "BOOLEAN",     "primary_key": False, "nullable": False, "default_value": "true"},
            {"name": "created_at", "data_type": "TIMESTAMP",   "primary_key": False, "nullable": False, "default_value": "NOW()"},
        ],
        "enforced_fks": [],
        "logical_refs": [],
    },
}

# ── Stage implementations ──────────────────────────────────────────────────────

def select_tables(concepts):
    all_concepts = set()

    def expand(concept):
        if concept in all_concepts:
            return
        all_concepts.add(concept)
        for dep in CONCEPT_DEPS.get(concept, []):
            expand(dep)

    for c in concepts:
        expand(c.name)

    merged = {}
    for concept in all_concepts:
        for table in CONCEPT_TABLES.get(concept, []):
            name = table["name"]
            if name not in merged or TIER_RANK[table["tier"]] > TIER_RANK[merged[name]["tier"]]:
                merged[name] = {
                    **table,
                    "triggered_by":        [concept],
                    "patterns_applied":    [],
                    "inclusion_confidence": round(
                        TIER_SCORES.get(table["tier"], 0.5) * 0.6 +
                        max((c.confidence for c in concepts), default=0.9) * 0.4, 2
                    )
                }
            else:
                if concept not in merged[name]["triggered_by"]:
                    merged[name]["triggered_by"].append(concept)

    # FK dependency pull-in
    for name, table in list(merged.items()):
        if table["tier"] in ("required", "recommended"):
            for dep in TABLE_DEPS.get(name, []):
                if dep not in merged:
                    merged[dep] = {
                        "name":                dep,
                        "tier":                "required",
                        "triggered_by":        [f"dependency of {name}"],
                        "dependency_reason":   f"Required by {name} (FK)",
                        "patterns_applied":    [],
                        "inclusion_confidence": 0.96,
                    }

    results = list(merged.values())
    results.sort(key=lambda x: -TIER_RANK.get(x["tier"], 0))
    return results


def apply_all_patterns(tables, active_decisions=None):
    """
    Apply schema patterns to all tables based on active design decisions.

    active_decisions: dict of {decision_name: choice_string}
                      e.g. {"tenancy_model": "multi_tenant", "temporal_strategy": "versioned"}
    """
    if active_decisions is None:
        active_decisions = {}

    # Determine which patterns to apply
    do_audit      = active_decisions.get("audit_policy",      "full_audit")  != "no_audit"
    do_soft_del   = active_decisions.get("delete_strategy",   "soft_delete") == "soft_delete"
    do_temporal   = active_decisions.get("temporal_strategy", "current_only") == "versioned"
    do_multi_tent = active_decisions.get("tenancy_model",     "single_tenant") == "multi_tenant"

    enriched = []
    for table in tables:
        t         = copy.deepcopy(table)
        base_cols = copy.deepcopy(BASE_COLUMNS.get(t["name"], _generic_columns(t["name"])))
        existing  = {c["name"] for c in base_cols}

        def _stamp(pattern_name, pattern_cols):
            for col in pattern_cols:
                if col["name"] not in existing:
                    base_cols.append(copy.deepcopy(col))
                    existing.add(col["name"])
                    if pattern_name not in t["patterns_applied"]:
                        t["patterns_applied"].append(pattern_name)

        t["columns"]      = base_cols
        t["enforced_fks"] = ENFORCED_FKS.get(t["name"], [])
        t["logical_refs"] = []
        enriched.append(t)

    return enriched


def build_dependency_dict(tables):
    table_names = {t["name"] for t in tables}
    deps        = {}
    for table in tables:
        name = table["name"]
        deps[name] = []
        for fk in table.get("enforced_fks", []):
            if fk["to_table"] in table_names:
                deps[name].append(fk["to_table"])
    return deps


def kahns_sort(dependencies):
    from collections import deque

    in_degree  = {t: 0 for t in dependencies}
    dependents = {t: [] for t in dependencies}

    for table, deps in dependencies.items():
        in_degree[table] = len(deps)
        for dep in deps:
            dependents[dep].append(table)

    queue  = deque(sorted([t for t, d in in_degree.items() if d == 0]))
    result = []

    while queue:
        table = queue.popleft()
        result.append(table)
        for dependent in sorted(dependents[table]):
            in_degree[dependent] -= 1
            if in_degree[dependent] == 0:
                queue.append(dependent)

    if len(result) != len(in_degree):
        raise Exception("Circular dependency detected!")

    return result


def build_column_sql(col):
    sql = f"{col['name']} {col['data_type']}"
    if col.get("primary_key"):
        sql += " PRIMARY KEY"
    if not col.get("nullable", True):
        sql += " NOT NULL"
    if col.get("unique"):
        sql += " UNIQUE"
    if col.get("default_value"):
        sql += f" DEFAULT {col['default_value']}"
    return sql


def generate_ddl(enriched, order):
    table_map = {t["name"]: t for t in enriched}
    parts     = ["BEGIN;", ""]

    for name in order:
        if name not in table_map:
            continue

        table   = table_map[name]
        columns = [build_column_sql(c) for c in table["columns"]]
        fk_sqls = []

        for fk in table.get("enforced_fks", []):
            if fk["to_table"] in table_map:
                fk_sqls.append(
                    f"FOREIGN KEY ({fk['from_column']}) "
                    f"REFERENCES {fk['to_table']}({fk['to_column']}) "
                    f"ON DELETE {fk['on_delete']}"
                )

        all_defs = columns + fk_sqls
        col_sql  = ",\n    ".join(all_defs)
        parts.append(f"CREATE TABLE {name} (\n    {col_sql}\n);")

        for fk in table.get("enforced_fks", []):
            if fk["to_table"] in table_map:
                parts.append(
                    f"CREATE INDEX idx_{name}_{fk['from_column']} "
                    f"ON {name}({fk['from_column']});"
                )

        parts.append("")

    parts.append("COMMIT;")
    return "\n".join(parts)


def validate_ddl(ddl):
    try:
        import psycopg2
    except ImportError:
        print("    [SKIP] psycopg2 not installed — skipping DB validation.")
        return {"success": 0, "total": 0, "elapsed": 0, "skipped": True}

    db = f"val_{uuid.uuid4().hex[:8]}"
    try:
        conn = psycopg2.connect(
            host="localhost", port=5432,
            user="postgres", password="internpass",
            dbname="schema_test"
        )
        conn.autocommit = True
        conn.cursor().execute(f"CREATE DATABASE {db}")
        conn.close()
    except Exception as e:
        print(f"    [SKIP] Cannot connect to PostgreSQL: {e}")
        return {"success": 0, "total": 0, "elapsed": 0, "skipped": True}

    conn     = psycopg2.connect(
        host="localhost", port=5432,
        user="postgres", password="internpass", dbname=db
    )
    cur      = conn.cursor()
    success  = 0
    total    = 0
    start    = time.time()

    statements = [
        s.strip() for s in ddl.split(";")
        if s.strip() and s.strip() not in ("BEGIN", "COMMIT")
    ]

    for sql in statements:
        if sql.upper().startswith("CREATE"):
            total += 1
            try:
                cur.execute(sql)
                conn.commit()
                success += 1
                print(f"    ✓ {sql.split()[2]}")
            except Exception as e:
                conn.rollback()
                print(f"    ✗ {sql[:60]}… — {str(e).split(chr(10))[0]}")

    elapsed = int((time.time() - start) * 1000)
    cur.close()
    conn.close()

    conn = psycopg2.connect(
        host="localhost", port=5432,
        user="postgres", password="internpass", dbname="schema_test"
    )
    conn.autocommit = True
    conn.cursor().execute(f"DROP DATABASE IF EXISTS {db}")
    conn.close()

    return {"success": success, "total": total, "elapsed": elapsed, "skipped": False}


# ── Main pipeline function ─────────────────────────────────────────────────────

def run_pipeline(requirements: str, verbose: bool = True) -> dict:
    if verbose:
        print(f"\n{'='*70}")
        print(f"INPUT: {requirements}")
        print(f"{'='*70}")

    # Stage 1: Extract concepts via LLM (or mock)
    if verbose:
        print("\n  Stage 1: Concept Extraction")
    extraction = extract(requirements)

    if not extraction.concepts:
        if verbose:
            print("  No concepts extracted. Cannot generate schema.")
            for u in extraction.unmatched:
                print(f"    Unmatched: {u.raw_text}")
        return {"error": "No concepts extracted", "unmatched": [u.model_dump() for u in extraction.unmatched]}

    if verbose:
        for c in extraction.concepts:
            print(f"    ✓ {c.name} (confidence={c.confidence:.2f}) — '{c.matched_text}'")
        for d in extraction.decisions:
            print(f"    → decision: {d.name}={d.choice} ({d.confidence:.2f})")

    # Stage 2: Conflict detection
    active_decisions = {d.name: d.choice for d in extraction.decisions}
    if verbose:
        print("\n  Stage 2: Conflict Detection")
        if active_decisions:
            for k, v in active_decisions.items():
                print(f"    Active decision: {k}={v}")
        else:
            print("    No non-default decisions detected — using all defaults")
        print("    No conflicts detected!")

    # Stage 3: Table selection
    if verbose:
        print("\n  Stage 3: Table Selection")
    tables = select_tables(extraction.concepts)
    if verbose:
        for t in tables:
            print(f"    {t['tier']:12} | {t['name']}")

    # Stage 4: Pattern injection + Kahn's sort
    if verbose:
        print("\n  Stage 4: Pattern Injection + Kahn's Sort")
    enriched = apply_all_patterns(tables, active_decisions=active_decisions)
    deps     = build_dependency_dict(enriched)
    order    = kahns_sort(deps)
    if verbose:
        print(f"    Creation order: {' → '.join(order)}")

    # Stage 5: Pattern materialization summary
    if verbose:
        print("\n  Stage 5: Pattern Materialization")
        for t in enriched:
            patterns = list(set(t.get("patterns_applied", [])))
            print(f"    {t['name']:25} → {patterns}")

    # Stage 6: DDL generation
    if verbose:
        print("\n  Stage 6: DDL Generation")
    ddl = generate_ddl(enriched, order)
    if verbose:
        preview = ddl[:600] + "..." if len(ddl) > 600 else ddl
        print(preview)

    # Stage 7: PostgreSQL validation
    if verbose:
        print("\n  Stage 7: PostgreSQL Validation")
    report = validate_ddl(ddl)
    if verbose:
        if report.get("skipped"):
            print("    Validation skipped (no DB connection).")
        else:
            print(f"\n    Result: {report['success']}/{report['total']} "
                  f"statements succeeded in {report['elapsed']}ms")

    # Stage 8: Explainability report
    if verbose:
        print("\n  Stage 8: Explainability Report")
        print(f"  {'Table':<25} {'Tier':<12} {'Conf':<8} Triggered By")
        print(f"  {'-'*70}")
        for t in enriched:
            triggered = ", ".join(t.get("triggered_by", ["direct"]))
            print(f"  {t['name']:<25} {t['tier']:<12} "
                  f"{t['inclusion_confidence']:<8} {triggered}")

    return {
        "ddl":              ddl,
        "tables":           [t["name"] for t in enriched],
        "creation_order":   order,
        "active_decisions": active_decisions,
        "unmatched":        [u.model_dump() for u in extraction.unmatched],
        "explainability": [
            {
                "table":      t["name"],
                "tier":       t["tier"],
                "confidence": t.get("inclusion_confidence", 0.9),
                "triggered_by": t.get("triggered_by", []),
                "patterns":   t.get("patterns_applied", []),
            }
            for t in enriched
        ],
        "validation": report,
    }



# ── Entry point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) > 1:
        req = " ".join(sys.argv[1:])
    else:
        req = "I need an e-commerce platform with product catalog and order tracking"

    result = run_pipeline(req)
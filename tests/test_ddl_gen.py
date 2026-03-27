import pytest
from project_05.ddl_gen import generate_ddl, tables as sample_tables

def test_ddl_generation():
    ddl = generate_ddl(sample_tables)
    
    assert "BEGIN;" in ddl
    assert "CREATE TABLE customers (" in ddl
    assert "CREATE TABLE orders (" in ddl
    assert "COMMIT;" in ddl
    
    # Verify FK constraint
    assert "FOREIGN KEY (customer_id) REFERENCES customers(id)" in ddl

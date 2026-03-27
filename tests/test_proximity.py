import pytest
from project_11.proximity import build_search_index, find_nearest

@pytest.fixture(scope="module")
def search_index():
    return build_search_index()

def test_exact_alias_match(search_index):
    names, vectorizer, matrix = search_index
    results = find_nearest("online store", names, vectorizer, matrix)
    
    assert len(results) > 0
    top_match = results[0][0]
    assert top_match == "e_commerce_orders"

def test_similar_query(search_index):
    names, vectorizer, matrix = search_index
    results = find_nearest("staff directory", names, vectorizer, matrix)
    
    assert len(results) > 0
    top_match = results[0][0]
    assert top_match == "employee_management"

def test_out_of_domain_no_match(search_index):
    names, vectorizer, matrix = search_index
    results = find_nearest("space rockets and moon landings", names, vectorizer, matrix)
    
    # Should drop anything below min_score (default 0.1)
    assert len(results) == 0

import requests
import pytest
import os
from dotenv import load_dotenv

load_dotenv()

BASE_URL = "http://localhost:8000"

def test_admin_routes_protected():
    """Verify that admin routes return 401 without auth"""
    routes = [
        "/admin/concepts",
        "/admin/candidates",
        "/cache/stats"
    ]
    for route in routes:
        response = requests.get(f"{BASE_URL}{route}")
        assert response.status_code == 401, f"Route {route} should be protected"

def test_login_and_access():
    """Verify login and access to protected routes with JWT"""
    # 1. Login
    payload = {
        "username": "admin",
        "password": "internadmin"
    }
    response = requests.post(f"{BASE_URL}/api/token", json=payload)
    assert response.status_code == 200
    data = response.json()
    token = data["access_token"]
    assert token is not None

    # 2. Access protected route with token
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(f"{BASE_URL}/admin/concepts", headers=headers)
    assert response.status_code == 200
    assert "concepts" in response.json()

if __name__ == "__main__":
    # Manual test run
    try:
        print("Testing admin protection...")
        test_admin_routes_protected()
        print("✓ Admin routes are protected")

        print("Testing login...")
        test_login_and_access()
        print("✓ Login and token access successful")
    except Exception as e:
        print(f"✗ Test failed: {e}")

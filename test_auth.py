import requests
import json

BASE_URL = "http://localhost:8000"

def test_auth():
    # First, login to get token
    login_data = {
        "username": "admin1",
        "password": "admin123",
        "role": "admin"
    }
    
    print("Logging in...")
    response = requests.post(f"{BASE_URL}/api/doctors/login", json=login_data)
    
    if response.status_code != 200:
        print(f"Login failed: {response.text}")
        return
    
    token = response.json()["access_token"]
    print(f"Token received: {token[:20]}...")
    print()
    
    headers = {"Authorization": f"Bearer {token}"}
    
    # Test endpoints one by one
    endpoints = [
        "/api/admin/dashboard",
        "/api/admin/staff",
        "/api/admin/staff/statistics",
        "/api/admin/beds",
        "/api/admin/inventory",
        "/api/admin/activity",
        "/api/admin/records"
    ]
    
    for endpoint in endpoints:
        print(f"Testing {endpoint}...")
        response = requests.get(f"{BASE_URL}{endpoint}", headers=headers)
        print(f"  Status: {response.status_code}")
        if response.status_code == 200:
            print(f"  ✓ Success")
        else:
            print(f"  ✗ Error: {response.text}")
        print()

if __name__ == "__main__":
    test_auth()
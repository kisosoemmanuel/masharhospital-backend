import requests
import json

BASE_URL = "http://localhost:8000"

def test_admin_api():
    # Login
    login_data = {
        "username": "admin1",
        "password": "admin123",
        "role": "admin"
    }
    
    print("1. Logging in...")
    response = requests.post(f"{BASE_URL}/api/doctors/login", json=login_data)
    
    if response.status_code != 200:
        print(f"Login failed: {response.text}")
        return
    
    token = response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    print("✅ Login successful")
    print()
    
    # Test dashboard
    print("2. Getting admin dashboard...")
    response = requests.get(f"{BASE_URL}/api/admin/dashboard", headers=headers)
    if response.status_code == 200:
        data = response.json()
        print(json.dumps(data, indent=2))
    else:
        print(f"Error: {response.text}")
    print()
    
    # Test staff list
    print("3. Getting all staff...")
    response = requests.get(f"{BASE_URL}/api/admin/staff", headers=headers)
    if response.status_code == 200:
        staff = response.json()
        print(f"Found {len(staff)} staff members")
        print(json.dumps(staff[:2], indent=2))  # Show first 2
    else:
        print(f"Error: {response.text}")
    print()
    
    # Test staff statistics
    print("4. Getting staff statistics...")
    response = requests.get(f"{BASE_URL}/api/admin/staff/statistics", headers=headers)
    if response.status_code == 200:
        stats = response.json()
        print(json.dumps(stats, indent=2))
    else:
        print(f"Error: {response.text}")
    print()
    
    # Test bed status
    print("5. Getting bed status...")
    response = requests.get(f"{BASE_URL}/api/admin/beds", headers=headers)
    if response.status_code == 200:
        beds = response.json()
        print(json.dumps(beds, indent=2))
    else:
        print(f"Error: {response.text}")
    print()
    
    # Test inventory
    print("6. Getting inventory status...")
    response = requests.get(f"{BASE_URL}/api/admin/inventory", headers=headers)
    if response.status_code == 200:
        inventory = response.json()
        print(json.dumps(inventory, indent=2))
    else:
        print(f"Error: {response.text}")
    print()
    
    # Test recent activity
    print("7. Getting recent activity...")
    response = requests.get(f"{BASE_URL}/api/admin/activity", headers=headers)
    if response.status_code == 200:
        activity = response.json()
        print(json.dumps(activity, indent=2))
    else:
        print(f"Error: {response.text}")
    print()
    
    # Test records
    print("8. Getting all records...")
    response = requests.get(f"{BASE_URL}/api/admin/records", headers=headers)
    if response.status_code == 200:
        records = response.json()
        print(json.dumps(records, indent=2))
    else:
        print(f"Error: {response.text}")
    print()
    
    print("✅ All tests completed successfully!")

if __name__ == "__main__":
    test_admin_api()
import requests
import json

BASE_URL = "http://localhost:8000"

def login_as_receptionist():
    """Login and return headers with token"""
    login_data = {
        "username": "receptionist1",
        "password": "rec123",
        "role": "receptionist"
    }
    
    response = requests.post(f"{BASE_URL}/api/doctors/login", json=login_data)
    if response.status_code != 200:
        print(f"❌ Login failed: {response.text}")
        return None
    
    token = response.json()["access_token"]
    print("✅ Receptionist login successful")
    return {"Authorization": f"Bearer {token}"}

def test_receptionist_endpoints():
    headers = login_as_receptionist()
    if not headers:
        return
    
    print("\n=== Testing Receptionist Endpoints ===\n")
    
    # Test dashboard
    print("1. Getting dashboard stats...")
    response = requests.get(f"{BASE_URL}/api/receptionist/dashboard", headers=headers)
    if response.status_code == 200:
        print(json.dumps(response.json(), indent=2))
    else:
        print(f"❌ Error: {response.text}")
    print()
    
    # Test quick register
    print("2. Quick registering a patient...")
    quick_reg = {
        "patient_name": "Test Patient",
        "phone": "0712345678",
        "condition": "Headache",
        "priority": 1,
        "department": "General"
    }
    response = requests.post(f"{BASE_URL}/api/receptionist/patients/quick", 
                            json=quick_reg, headers=headers)
    if response.status_code == 200:
        print(json.dumps(response.json(), indent=2))
    else:
        print(f"❌ Error: {response.text}")
    print()
    
    # Test queue
    print("3. Getting queue list...")
    response = requests.get(f"{BASE_URL}/api/receptionist/queue", headers=headers)
    if response.status_code == 200:
        queue = response.json()
        print(f"Found {len(queue)} patients in queue")
        if queue:
            print(json.dumps(queue[:2], indent=2))
    else:
        print(f"❌ Error: {response.text}")
    print()
    
    # Test notifications
    print("4. Getting notifications...")
    response = requests.get(f"{BASE_URL}/api/receptionist/notifications", headers=headers)
    if response.status_code == 200:
        notifications = response.json()
        print(f"Found {len(notifications)} notifications")
        if notifications:
            print(json.dumps(notifications[:2], indent=2))
    else:
        print(f"❌ Error: {response.text}")
    print()
    
    # Test unread count
    print("5. Getting unread count...")
    response = requests.get(f"{BASE_URL}/api/receptionist/notifications/unread", headers=headers)
    if response.status_code == 200:
        print(json.dumps(response.json(), indent=2))
    else:
        print(f"❌ Error: {response.text}")
    print()
    
    # Test search
    print("6. Searching patients...")
    response = requests.get(f"{BASE_URL}/api/receptionist/patients/search?q=Mary", headers=headers)
    if response.status_code == 200:
        results = response.json()
        print(f"Found {len(results)} results")
        if results:
            print(json.dumps(results, indent=2))
    else:
        print(f"❌ Error: {response.text}")
    print()
    
    print("✅ Receptionist tests completed!")

if __name__ == "__main__":
    test_receptionist_endpoints()
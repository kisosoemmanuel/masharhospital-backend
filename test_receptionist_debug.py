import requests
import json
import traceback

BASE_URL = "http://localhost:8000"

def login_as_receptionist():
    """Login and return headers with token"""
    login_data = {
        "username": "receptionist1",
        "password": "rec123",
        "role": "receptionist"
    }
    
    try:
        response = requests.post(f"{BASE_URL}/api/doctors/login", json=login_data)
        if response.status_code != 200:
            print(f"❌ Login failed: {response.text}")
            return None
        
        token = response.json()["access_token"]
        print("✅ Receptionist login successful")
        return {"Authorization": f"Bearer {token}"}
    except Exception as e:
        print(f"❌ Login error: {e}")
        traceback.print_exc()
        return None

def test_quick_register(headers):
    """Test quick registration with detailed error handling"""
    print("\n=== Testing Quick Registration ===")
    
    # Test with different priorities
    test_cases = [
        {
            "name": "Normal Patient",
            "phone": "0711111111",
            "condition": "Headache",
            "priority": 1
        },
        {
            "name": "Emergency Patient",
            "phone": "0722222222",
            "condition": "Heart Attack",
            "priority": 3
        },
        {
            "name": "Urgent Patient",
            "phone": "0733333333",
            "condition": "Fracture",
            "priority": 2
        }
    ]
    
    for test in test_cases:
        print(f"\nRegistering: {test['name']} (Priority {test['priority']})")
        
        quick_reg = {
            "patient_name": test["name"],
            "phone": test["phone"],
            "condition": test["condition"],
            "priority": test["priority"],
            "department": "General"
        }
        
        try:
            response = requests.post(
                f"{BASE_URL}/api/receptionist/patients/quick", 
                json=quick_reg, 
                headers=headers
            )
            
            print(f"Status Code: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                print("✅ Success!")
                print(json.dumps(result, indent=2))
            else:
                print(f"❌ Error: {response.text}")
                
        except requests.exceptions.ConnectionError:
            print("❌ Connection Error: Is the server running?")
        except Exception as e:
            print(f"❌ Unexpected error: {e}")
            traceback.print_exc()
        
        print("-" * 50)

def test_all_endpoints():
    headers = login_as_receptionist()
    if not headers:
        return
    
    # Test quick registration
    test_quick_register(headers)
    
    # Test dashboard again after registration
    print("\n=== Dashboard After Registration ===")
    response = requests.get(f"{BASE_URL}/api/receptionist/dashboard", headers=headers)
    if response.status_code == 200:
        print(json.dumps(response.json(), indent=2))
    else:
        print(f"❌ Error: {response.text}")

if __name__ == "__main__":
    test_all_endpoints()
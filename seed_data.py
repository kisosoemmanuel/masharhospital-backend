import requests
import json

BASE_URL = "http://localhost:8000"

def login_as_admin():
    """Login and return headers with token"""
    login_data = {
        "username": "admin1",
        "password": "admin123",
        "role": "admin"
    }
    
    response = requests.post(f"{BASE_URL}/api/doctors/login", json=login_data)
    if response.status_code != 200:
        print("❌ Login failed")
        return None
    
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}

def create_staff_members(headers):
    """Create multiple staff members"""
    
    staff_members = [
        {
            "staff_id": "D003",
            "name": "Dr. Sarah Johnson",
            "role": "doctor",
            "phone": "+254700123456",
            "email": "sarah.johnson@hospital.com",
            "department": "Pediatrics",
            "specialization": "Pediatrician",
            "password": "docpass123"
        },
        {
            "staff_id": "D004",
            "name": "Dr. Michael Omondi",
            "role": "doctor",
            "phone": "+254700789012",
            "email": "michael.omondi@hospital.com",
            "department": "Cardiology",
            "specialization": "Cardiologist",
            "password": "docpass123"
        },
        {
            "staff_id": "N003",
            "name": "Nurse Brenda",
            "role": "nurse",
            "phone": "+254700345678",
            "email": "brenda@hospital.com",
            "department": "Emergency",
            "specialization": None,
            "password": "nursepass123"
        }
    ]
    
    for staff in staff_members:
        print(f"Creating {staff['name']}...")
        response = requests.post(f"{BASE_URL}/api/admin/staff", 
                                json=staff, 
                                headers=headers)
        
        if response.status_code == 200:
            print(f"  ✅ Created")
        else:
            print(f"  ❌ Failed: {response.text}")

if __name__ == "__main__":
    print("=== Seeding Database ===")
    headers = login_as_admin()
    if headers:
        create_staff_members(headers)
        print("\n✅ Seeding complete!")
    else:
        print("❌ Failed to login")

import requests
from jose import jwt
import json

BASE_URL = "http://localhost:8000"
SECRET_KEY = "your-super-secret-key-change-this-in-production"  # Match your .env file

def decode_token(token):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        print("Token payload:", payload)
        return payload
    except Exception as e:
        print(f"Error decoding token: {e}")
        return None

# Login
login_data = {
    "username": "admin1",
    "password": "admin123",
    "role": "admin"
}

print("Logging in...")
response = requests.post(f"{BASE_URL}/api/doctors/login", json=login_data)

if response.status_code != 200:
    print(f"Login failed: {response.text}")
    exit()

data = response.json()
token = data["access_token"]
print(f"Token: {token}")
print()

# Decode token to see what's inside
print("Decoding token...")
payload = decode_token(token)
print()

# Try a simple endpoint
headers = {"Authorization": f"Bearer {token}"}
print("Testing /api/health (no auth required)...")
response = requests.get(f"{BASE_URL}/api/health")
print(f"Status: {response.status_code}")
print(f"Response: {response.json()}")
print()

print("Testing /api/admin/staff with token...")
response = requests.get(f"{BASE_URL}/api/admin/staff", headers=headers)
print(f"Status: {response.status_code}")
if response.status_code == 200:
    print("Success! Staff data retrieved.")
else:
    print(f"Error: {response.text}")
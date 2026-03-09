from datetime import datetime, timedelta
from typing import Optional, Dict, List
from pydantic import BaseModel, Field
from jose import JWTError, jwt
from passlib.context import CryptContext
import os
from dotenv import load_dotenv

load_dotenv()

# Password hashing - configure with proper bcrypt settings
pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__rounds=12  # Set explicit rounds
)

# JWT settings
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-here-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

class DoctorBase(BaseModel):
    username: str
    name: str
    role: str  # doctor, receptionist, admin
    department: Optional[str] = None
    specialization: Optional[str] = None

class DoctorCreate(DoctorBase):
    password: str

class Doctor(DoctorBase):
    id: int
    is_active: bool = True
    created_at: datetime
    last_login: Optional[datetime] = None
    
    class Config:
        from_attributes = True

class DoctorLogin(BaseModel):
    username: str
    password: str
    role: str

class DoctorInDB(Doctor):
    hashed_password: str

# Helper function to hash passwords safely
def hash_password(password: str) -> str:
    """Hash a password with length checking"""
    # bcrypt has a 72-byte limit, so we truncate if necessary
    if len(password.encode('utf-8')) > 72:
        password = password[:72]  # Simple truncation
    return pwd_context.hash(password)

# Helper function to verify passwords
def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against a hash"""
    try:
        # Handle potential length issues
        if len(plain_password.encode('utf-8')) > 72:
            plain_password = plain_password[:72]
        return pwd_context.verify(plain_password, hashed_password)
    except Exception as e:
        print(f"Password verification error: {e}")
        return False

# In-memory database (replace with real database later)
doctors_db = {
    1: {
        "id": 1,
        "username": "doctor1",
        "name": "Dr. Smith",
        "role": "doctor",
        "department": "Cardiology",
        "specialization": "Cardiologist",
        "hashed_password": hash_password("doc123"),
        "is_active": True,
        "created_at": datetime.now(),
        "last_login": None
    },
    2: {
        "id": 2,
        "username": "receptionist1",
        "name": "Jane Reception",
        "role": "receptionist",
        "department": "Front Desk",
        "specialization": None,
        "hashed_password": hash_password("rec123"),
        "is_active": True,
        "created_at": datetime.now(),
        "last_login": None
    },
    3: {
        "id": 3,
        "username": "admin1",
        "name": "Admin User",
        "role": "admin",
        "department": "Administration",
        "specialization": None,
        "hashed_password": hash_password("admin123"),
        "is_active": True,
        "created_at": datetime.now(),
        "last_login": None
    }
}

class DoctorModel:
    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """Verify a plain password against a hashed password"""
        return verify_password(plain_password, hashed_password)

    @staticmethod
    def get_password_hash(password: str) -> str:
        """Hash a password"""
        return hash_password(password)

    @staticmethod
    def authenticate(username: str, password: str, role: str) -> Optional[Dict]:
        """Authenticate a user"""
        # Find user by username and role
        user = None
        for u in doctors_db.values():
            if u["username"] == username and u["role"] == role:
                user = u
                break
        
        if not user:
            return None
        
        if not DoctorModel.verify_password(password, user["hashed_password"]):
            return None
        
        # Update last login
        user["last_login"] = datetime.now()
        
        # Create access token
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = DoctorModel.create_access_token(
            data={"sub": user["username"], "role": user["role"]},
            expires_delta=access_token_expires
        )
        
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "user": {
                "id": user["id"],
                "username": user["username"],
                "name": user["name"],
                "role": user["role"],
                "department": user.get("department")
            }
        }

    @staticmethod
    def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
        """Create JWT access token"""
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=15)
        
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
        return encoded_jwt

    @staticmethod
    def get_by_username(username: str) -> Optional[Dict]:
        """Get user by username"""
        for user in doctors_db.values():
            if user["username"] == username:
                return {
                    "id": user["id"],
                    "username": user["username"],
                    "name": user["name"],
                    "role": user["role"],
                    "department": user.get("department"),
                    "specialization": user.get("specialization")
                }
        return None

    @staticmethod
    def get_by_id(user_id: int) -> Optional[Dict]:
        """Get user by ID"""
        user = doctors_db.get(user_id)
        if user:
            return {
                "id": user["id"],
                "username": user["username"],
                "name": user["name"],
                "role": user["role"],
                "department": user.get("department"),
                "specialization": user.get("specialization")
            }
        return None

    @staticmethod
    def create_doctor(doctor_data: DoctorCreate) -> Dict:
        """Create a new doctor (admin only)"""
        new_id = max(doctors_db.keys()) + 1
        new_doctor = {
            "id": new_id,
            "username": doctor_data.username,
            "name": doctor_data.name,
            "role": doctor_data.role,
            "department": doctor_data.department,
            "specialization": doctor_data.specialization,
            "hashed_password": DoctorModel.get_password_hash(doctor_data.password),
            "is_active": True,
            "created_at": datetime.now(),
            "last_login": None
        }
        doctors_db[new_id] = new_doctor
        return {
            "id": new_id,
            "username": doctor_data.username,
            "name": doctor_data.name,
            "role": doctor_data.role,
            "department": doctor_data.department,
            "specialization": doctor_data.specialization
        }

# For backward compatibility
Doctor = DoctorModel
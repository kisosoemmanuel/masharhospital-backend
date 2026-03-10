from datetime import datetime, timedelta
from typing import Optional, Dict, List
from pydantic import BaseModel
from jose import jwt
from passlib.context import CryptContext
import os
from dotenv import load_dotenv

load_dotenv()

# -----------------------------
# Password Hashing
# -----------------------------
pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__rounds=12
)

# -----------------------------
# JWT Settings
# -----------------------------
SECRET_KEY = os.getenv("SECRET_KEY", "change-this-secret")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30


# -----------------------------
# Pydantic Models
# -----------------------------
class DoctorBase(BaseModel):
    username: str
    name: str
    role: str
    department: Optional[str] = None
    specialization: Optional[str] = None


class DoctorCreate(DoctorBase):
    password: str


class DoctorLogin(BaseModel):
    username: str
    password: str
    role: str


class Doctor(DoctorBase):
    id: int
    is_active: bool = True
    created_at: datetime
    last_login: Optional[datetime] = None

    class Config:
        from_attributes = True


class DoctorInDB(Doctor):
    hashed_password: str


# -----------------------------
# Password Utilities
# -----------------------------
def hash_password(password: str) -> str:
    if len(password.encode("utf-8")) > 72:
        password = password[:72]
    return pwd_context.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    try:
        if len(password.encode("utf-8")) > 72:
            password = password[:72]
        return pwd_context.verify(password, hashed)
    except Exception:
        return False


# -----------------------------
# Fake In-Memory Database
# -----------------------------
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


# -----------------------------
# Doctor Model Service
# -----------------------------
class DoctorModel:

    # -------------------------
    # Authentication
    # -------------------------
    @staticmethod
    def authenticate(username: str, password: str, role: str) -> Optional[Dict]:

        user = None

        for u in doctors_db.values():
            if u["username"] == username and u["role"] == role:
                user = u
                break

        if not user:
            return None

        if not verify_password(password, user["hashed_password"]):
            return None

        user["last_login"] = datetime.now()

        token = DoctorModel.create_access_token(
            {"sub": user["username"], "role": user["role"]}
        )

        return {
            "access_token": token,
            "token_type": "bearer",
            "user": {
                "id": user["id"],
                "username": user["username"],
                "name": user["name"],
                "role": user["role"],
                "department": user.get("department")
            }
        }

    # -------------------------
    # JWT Token
    # -------------------------
    @staticmethod
    def create_access_token(data: dict):

        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

        to_encode = data.copy()
        to_encode.update({"exp": expire})

        return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

    # -------------------------
    # Get Doctor by Username
    # -------------------------
    @staticmethod
    def get_by_username(username: str) -> Optional[Dict]:

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

    # -------------------------
    # Get Doctor by ID
    # -------------------------
    @staticmethod
    def get_doctor_by_id(doctor_id: int) -> Optional[Dict]:

        doctor = doctors_db.get(doctor_id)

        if not doctor:
            return None

        return {
            "id": doctor["id"],
            "username": doctor["username"],
            "name": doctor["name"],
            "role": doctor["role"],
            "department": doctor.get("department"),
            "specialization": doctor.get("specialization")
        }

    # -------------------------
    # Get All Doctors
    # -------------------------
    @staticmethod
    def get_all_doctors() -> List[Dict]:

        return [
            {
                "id": d["id"],
                "username": d["username"],
                "name": d["name"],
                "role": d["role"],
                "department": d.get("department"),
                "specialization": d.get("specialization")
            }
            for d in doctors_db.values()
        ]

    # -------------------------
    # Create Doctor
    # -------------------------
    @staticmethod
    def create_doctor(doctor_data: DoctorCreate) -> Dict:

        new_id = max(doctors_db.keys()) + 1

        doctor = {
            "id": new_id,
            "username": doctor_data.username,
            "name": doctor_data.name,
            "role": doctor_data.role,
            "department": doctor_data.department,
            "specialization": doctor_data.specialization,
            "hashed_password": hash_password(doctor_data.password),
            "is_active": True,
            "created_at": datetime.now(),
            "last_login": None
        }

        doctors_db[new_id] = doctor

        return DoctorModel.get_doctor_by_id(new_id)

    # -------------------------
    # Delete Doctor
    # -------------------------
    @staticmethod
    def delete_doctor(doctor_id: int) -> bool:

        if doctor_id not in doctors_db:
            return False

        del doctors_db[doctor_id]
        return True


# Backward compatibility
Doctor = DoctorModel
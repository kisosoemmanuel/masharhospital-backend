from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any
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
    email: Optional[str] = None
    phone: Optional[str] = None


class DoctorCreate(DoctorBase):
    password: str
    employee_id: Optional[str] = None


class DoctorLogin(BaseModel):
    username: str
    password: str
    role: Optional[str] = None  # Made role optional


class DoctorUpdate(BaseModel):
    name: Optional[str] = None
    department: Optional[str] = None
    specialization: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    is_active: Optional[bool] = None


class Doctor(DoctorBase):
    id: int
    employee_id: Optional[str] = None
    is_active: bool = True
    created_at: datetime
    last_login: Optional[datetime] = None
    total_patients: Optional[int] = 0
    average_consultation_time: Optional[int] = 15  # in minutes

    class Config:
        from_attributes = True


class DoctorInDB(Doctor):
    hashed_password: str


class DoctorResponse(BaseModel):
    success: bool
    data: Optional[Dict] = None
    message: Optional[str] = None
    error: Optional[str] = None


# -----------------------------
# Password Utilities
# -----------------------------
def hash_password(password: str) -> str:
    """Hash a password using bcrypt"""
    if len(password.encode("utf-8")) > 72:
        password = password[:72]
    return pwd_context.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    """Verify a password against its hash"""
    try:
        if len(password.encode("utf-8")) > 72:
            password = password[:72]
        return pwd_context.verify(password, hashed)
    except Exception as e:
        print(f"Password verification error: {e}")
        return False


# -----------------------------
# Import admin staff database for integration
# -----------------------------
try:
    from src.models.admin import staff_db, AdminModel
    ADMIN_AVAILABLE = True
except ImportError:
    staff_db = {}
    ADMIN_AVAILABLE = False
    print("Warning: Admin model not available, doctor model running in standalone mode")


# -----------------------------
# Fake In-Memory Database
# -----------------------------
doctors_db = {
    1: {
        "id": 1,
        "employee_id": "D001",
        "username": "doctor1",
        "name": "Dr. John Kamau",
        "role": "doctor",
        "department": "Cardiology",
        "specialization": "Cardiologist",
        "email": "john.kamau@hospital.com",
        "phone": "+254700111222",
        "hashed_password": hash_password("doctor123"),
        "is_active": True,
        "created_at": datetime.now() - timedelta(days=365),
        "last_login": datetime.now() - timedelta(days=1),
        "total_patients": 1250,
        "average_consultation_time": 15
    },
    2: {
        "id": 2,
        "employee_id": "D002",
        "username": "doctor2",
        "name": "Dr. Jane Smith",
        "role": "doctor",
        "department": "Pediatrics",
        "specialization": "Pediatrician",
        "email": "jane.smith@hospital.com",
        "phone": "+254700111333",
        "hashed_password": hash_password("doctor456"),
        "is_active": True,
        "created_at": datetime.now() - timedelta(days=180),
        "last_login": None,
        "total_patients": 850,
        "average_consultation_time": 20
    },
    3: {
        "id": 3,
        "employee_id": "D003",
        "username": "doctor3",
        "name": "Dr. Michael Ochieng",
        "role": "doctor",
        "department": "Orthopedics",
        "specialization": "Orthopedic Surgeon",
        "email": "michael.ochieng@hospital.com",
        "phone": "+254700111444",
        "hashed_password": hash_password("doctor789"),
        "is_active": True,
        "created_at": datetime.now() - timedelta(days=730),
        "last_login": datetime.now() - timedelta(days=7),
        "total_patients": 2100,
        "average_consultation_time": 25
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
    def authenticate(username: str, password: str, role: Optional[str] = None) -> Optional[Dict]:
        """
        Authenticate a user.
        Checks both doctor database and admin staff database.
        If role is provided, try that role first.
        If no role provided or role-specific auth fails, try all roles.
        """
        print(f"Authentication attempt - Username: {username}, Role: {role}")
        
        user = None
        source = "doctor_db"
        
        # Try doctor database first with role
        if role:
            for u in doctors_db.values():
                if (u["username"] == username or u.get("employee_id") == username) and u["role"] == role:
                    user = u.copy()  # Create a copy to avoid modifying original
                    print(f"Found doctor with matching role: {user['name']} - {user['role']}")
                    break
        
        # Try doctor database without role
        if not user:
            print("Trying all roles in doctor database...")
            for u in doctors_db.values():
                if u["username"] == username or u.get("employee_id") == username:
                    user = u.copy()
                    print(f"Found doctor: {user['name']} with role: {user['role']}")
                    break
        
        # If not found in doctor database and admin is available, try admin staff database
        if not user and ADMIN_AVAILABLE and staff_db:
            print("Checking admin staff database...")
            for u in staff_db.values():
                if u.get("staff_id") == username or u.get("username") == username:
                    # Convert admin staff to doctor format
                    user = {
                        "id": u["id"],
                        "employee_id": u.get("staff_id"),
                        "username": u.get("staff_id"),
                        "name": u["name"],
                        "role": u["role"],
                        "department": u.get("department"),
                        "specialization": u.get("specialization"),
                        "email": u.get("email"),
                        "phone": u.get("phone"),
                        "hashed_password": u.get("hashed_password"),
                        "is_active": u.get("status") == "active",
                        "created_at": u.get("created_at", datetime.now()),
                        "last_login": u.get("last_login")
                    }
                    source = "admin_db"
                    print(f"Found staff: {user['name']} with role: {user['role']}")
                    break
        
        if not user:
            print(f"No user found with username: {username}")
            return None
        
        # Verify password
        if not verify_password(password, user["hashed_password"]):
            print("Password verification failed")
            return None
        
        print(f"Authentication successful for {username} with role {user['role']} (source: {source})")
        
        # Update last login
        user["last_login"] = datetime.now()
        
        # Update in original database if from doctor_db
        if source == "doctor_db":
            for u in doctors_db.values():
                if u["id"] == user["id"]:
                    u["last_login"] = datetime.now()
                    break
        
        # Create access token
        token = DoctorModel.create_access_token(
            {"sub": user.get("employee_id") or user["username"], "role": user["role"]}
        )
        
        return {
            "access_token": token,
            "token_type": "bearer",
            "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            "user": {
                "id": user["id"],
                "employee_id": user.get("employee_id"),
                "username": user["username"],
                "name": user["name"],
                "role": user["role"],
                "department": user.get("department"),
                "specialization": user.get("specialization"),
                "email": user.get("email"),
                "phone": user.get("phone")
            }
        }

    # -------------------------
    # JWT Token
    # -------------------------
    @staticmethod
    def create_access_token(data: dict) -> str:
        """Create JWT access token"""
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        to_encode = data.copy()
        to_encode.update({"exp": expire, "iat": datetime.utcnow()})
        return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

    @staticmethod
    def verify_token(token: str) -> Optional[Dict]:
        """Verify JWT token and return payload"""
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            return payload
        except jwt.ExpiredSignatureError:
            print("Token has expired")
            return None
        except jwt.JWTError as e:
            print(f"Token verification error: {e}")
            return None

    # -------------------------
    # Get Doctor by Username
    # -------------------------
    @staticmethod
    def get_by_username(username: str) -> Optional[Dict]:
        """Get doctor by username or employee ID"""
        # Check doctor database
        for user in doctors_db.values():
            if user["username"] == username or user.get("employee_id") == username:
                return {
                    "id": user["id"],
                    "employee_id": user.get("employee_id"),
                    "username": user["username"],
                    "name": user["name"],
                    "role": user["role"],
                    "department": user.get("department"),
                    "specialization": user.get("specialization"),
                    "email": user.get("email"),
                    "phone": user.get("phone"),
                    "is_active": user.get("is_active", True)
                }
        
        # Check admin database if available
        if ADMIN_AVAILABLE and staff_db:
            for user in staff_db.values():
                if user.get("staff_id") == username:
                    return {
                        "id": user["id"],
                        "employee_id": user.get("staff_id"),
                        "username": user.get("staff_id"),
                        "name": user["name"],
                        "role": user["role"],
                        "department": user.get("department"),
                        "specialization": user.get("specialization"),
                        "email": user.get("email"),
                        "phone": user.get("phone"),
                        "is_active": user.get("status") == "active"
                    }
        
        return None

    # -------------------------
    # Get Doctor by ID
    # -------------------------
    @staticmethod
    def get_doctor_by_id(doctor_id: int) -> Optional[Dict]:
        """Get doctor by database ID"""
        doctor = doctors_db.get(doctor_id)
        if not doctor:
            return None
        
        # Get current queue stats for this doctor
        from src.services.queue_manager import QueueManager
        queue_stats = QueueManager.get_doctor_queue_stats(doctor_id)
        
        return {
            "id": doctor["id"],
            "employee_id": doctor.get("employee_id"),
            "username": doctor["username"],
            "name": doctor["name"],
            "role": doctor["role"],
            "department": doctor.get("department"),
            "specialization": doctor.get("specialization"),
            "email": doctor.get("email"),
            "phone": doctor.get("phone"),
            "is_active": doctor.get("is_active", True),
            "total_patients": doctor.get("total_patients", 0),
            "average_consultation_time": doctor.get("average_consultation_time", 15),
            "current_queue": queue_stats.get("waiting", 0),
            "current_patient": queue_stats.get("current_patient"),
            "last_login": doctor.get("last_login")
        }

    # -------------------------
    # Get All Doctors
    # -------------------------
    @staticmethod
    def get_all_doctors(include_inactive: bool = False) -> List[Dict]:
        """Get all doctors with optional inactive inclusion"""
        doctors = []
        
        for d in doctors_db.values():
            if include_inactive or d.get("is_active", True):
                # Get queue stats for this doctor
                from src.services.queue_manager import QueueManager
                queue_stats = QueueManager.get_doctor_queue_stats(d["id"])
                
                doctors.append({
                    "id": d["id"],
                    "employee_id": d.get("employee_id"),
                    "username": d["username"],
                    "name": d["name"],
                    "role": d["role"],
                    "department": d.get("department"),
                    "specialization": d.get("specialization"),
                    "email": d.get("email"),
                    "phone": d.get("phone"),
                    "is_active": d.get("is_active", True),
                    "total_patients": d.get("total_patients", 0),
                    "current_queue": queue_stats.get("waiting", 0),
                    "last_login": d.get("last_login")
                })
        
        return doctors

    # -------------------------
    # Get Doctors by Department
    # -------------------------
    @staticmethod
    def get_doctors_by_department(department: str) -> List[Dict]:
        """Get all doctors in a specific department"""
        return [
            d for d in DoctorModel.get_all_doctors()
            if d.get("department", "").lower() == department.lower()
        ]

    # -------------------------
    # Create Doctor
    # -------------------------
    @staticmethod
    def create_doctor(doctor_data: DoctorCreate) -> Dict:
        """Create a new doctor"""
        # Check if username already exists
        for existing in doctors_db.values():
            if existing["username"] == doctor_data.username:
                return {
                    "success": False,
                    "error": f"Username {doctor_data.username} already exists"
                }
        
        new_id = max(doctors_db.keys()) + 1
        
        doctor = {
            "id": new_id,
            "employee_id": doctor_data.employee_id or f"D{new_id:03d}",
            "username": doctor_data.username,
            "name": doctor_data.name,
            "role": "doctor",  # Force role to doctor
            "department": doctor_data.department,
            "specialization": doctor_data.specialization,
            "email": doctor_data.email,
            "phone": doctor_data.phone,
            "hashed_password": hash_password(doctor_data.password),
            "is_active": True,
            "created_at": datetime.now(),
            "last_login": None,
            "total_patients": 0,
            "average_consultation_time": 15
        }
        
        doctors_db[new_id] = doctor
        
        return {
            "success": True,
            "doctor": DoctorModel.get_doctor_by_id(new_id),
            "message": f"Doctor {doctor_data.name} created successfully"
        }

    # -------------------------
    # Update Doctor
    # -------------------------
    @staticmethod
    def update_doctor(doctor_id: int, update_data: DoctorUpdate) -> Dict:
        """Update doctor information"""
        doctor = doctors_db.get(doctor_id)
        if not doctor:
            return {
                "success": False,
                "error": f"Doctor with ID {doctor_id} not found"
            }
        
        # Update fields
        update_dict = update_data.dict(exclude_unset=True)
        for key, value in update_dict.items():
            if value is not None:
                doctor[key] = value
        
        return {
            "success": True,
            "doctor": DoctorModel.get_doctor_by_id(doctor_id),
            "message": "Doctor updated successfully"
        }

    # -------------------------
    # Delete/Deactivate Doctor
    # -------------------------
    @staticmethod
    def delete_doctor(doctor_id: int, permanent: bool = False) -> bool:
        """Delete or deactivate a doctor"""
        if doctor_id not in doctors_db:
            return False
        
        if permanent:
            # Permanent delete
            del doctors_db[doctor_id]
        else:
            # Soft delete - deactivate
            doctors_db[doctor_id]["is_active"] = False
        
        return True

    # -------------------------
    # Get Doctor Statistics
    # -------------------------
    @staticmethod
    def get_doctor_statistics(doctor_id: int) -> Dict:
        """Get detailed statistics for a doctor"""
        doctor = doctors_db.get(doctor_id)
        if not doctor:
            return {"success": False, "error": "Doctor not found"}
        
        from src.services.queue_manager import QueueManager
        from src.models.patients import consultations_db
        
        # Get queue stats
        queue_stats = QueueManager.get_doctor_queue_stats(doctor_id)
        
        # Get today's consultations
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        today_consultations = [
            c for c in consultations_db.values()
            if c.get("doctor_id") == doctor_id and
            c.get("created_at", datetime.min) >= today_start
        ]
        
        # Get completed consultations
        completed = [c for c in consultations_db.values() if c.get("doctor_id") == doctor_id and c.get("status") == "completed"]
        
        return {
            "success": True,
            "doctor_id": doctor_id,
            "name": doctor["name"],
            "statistics": {
                "total_patients": doctor.get("total_patients", 0),
                "today_patients": len(today_consultations),
                "completed_today": len([c for c in today_consultations if c.get("status") == "completed"]),
                "waiting_patients": queue_stats.get("waiting", 0),
                "current_patient": queue_stats.get("current_patient"),
                "average_wait_time": queue_stats.get("average_wait_time", 0),
                "average_consultation_time": doctor.get("average_consultation_time", 15),
                "completion_rate": round(len(completed) / max(doctor.get("total_patients", 1), 1) * 100, 2)
            }
        }

    # -------------------------
    # Get Department Statistics
    # -------------------------
    @staticmethod
    def get_department_statistics(department: str) -> Dict:
        """Get statistics for all doctors in a department"""
        doctors = DoctorModel.get_doctors_by_department(department)
        
        if not doctors:
            return {
                "success": False,
                "error": f"No doctors found in department {department}"
            }
        
        total_patients = sum(d.get("total_patients", 0) for d in doctors)
        active_doctors = len([d for d in doctors if d.get("is_active")])
        
        from src.services.queue_manager import QueueManager
        department_queue = QueueManager.get_waiting_patients(department=department)
        
        return {
            "success": True,
            "department": department,
            "statistics": {
                "total_doctors": len(doctors),
                "active_doctors": active_doctors,
                "total_patients_served": total_patients,
                "current_waiting": len(department_queue),
                "doctors": doctors
            }
        }


# Backward compatibility
Doctor = DoctorModel
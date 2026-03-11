from typing import Optional, Dict, List
from pydantic import BaseModel
from datetime import datetime, timedelta
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

# Password utilities
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
    except Exception:
        return False


# Receptionist "database"
receptionist_db: Dict[int, Dict] = {}
next_receptionist_id: int = 1

# Sample data
receptionist_db[1] = {
    "id": 1,
    "employee_id": "R001",
    "name": "Mary Wanjiku",
    "phone": "+254700111444",
    "email": "mary.wanjiku@hospital.com",
    "department": "Front Desk",
    "status": "active",
    "created_at": datetime.now() - timedelta(days=365*2),
    "updated_at": None,
    "hashed_password": hash_password("receptionist123"),
    "last_login": datetime.now() - timedelta(days=2)
}

receptionist_db[2] = {
    "id": 2,
    "employee_id": "R002",
    "name": "John Doe",
    "phone": "+254700111555",
    "email": "john.doe@hospital.com",
    "department": "Front Desk",
    "status": "active",
    "created_at": datetime.now() - timedelta(days=180),
    "updated_at": None,
    "hashed_password": hash_password("receptionist456"),
    "last_login": None
}


# Pydantic Models
class ReceptionistCreate(BaseModel):
    employee_id: str
    name: str
    phone: str
    email: Optional[str] = None
    department: Optional[str] = "General"
    password: str


class ReceptionistUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    department: Optional[str] = None
    status: Optional[str] = None


class ReceptionistLogin(BaseModel):
    employee_id: str
    password: str
    role: Optional[str] = "receptionist"  # Default to receptionist, but can be overridden


class ReceptionistModel:
    
    # -----------------------------
    # AUTHENTICATION (NEW)
    # -----------------------------
    @staticmethod
    def authenticate(employee_id: str, password: str, role: Optional[str] = None) -> Optional[Dict]:
        """
        Authenticate a receptionist.
        If role is provided, try that role first.
        If no role provided or role-specific auth fails, try all roles.
        """
        print(f"Receptionist authentication attempt - Employee ID: {employee_id}, Role: {role}")
        
        user = None
        
        # If role is provided, try that specific role first
        if role:
            for u in receptionist_db.values():
                if u["employee_id"] == employee_id and u.get("role", "receptionist") == role:
                    user = u
                    print(f"Found receptionist with matching role: {user['name']}")
                    break
        
        # If no user found with that role or no role provided, try all roles
        if not user:
            print("Trying all receptionists...")
            for u in receptionist_db.values():
                if u["employee_id"] == employee_id:
                    user = u
                    print(f"Found receptionist: {user['name']}")
                    break
        
        if not user:
            print(f"No receptionist found with ID: {employee_id}")
            return None
        
        # Verify password
        if not verify_password(password, user["hashed_password"]):
            print("Password verification failed")
            return None
        
        print(f"Authentication successful for {employee_id}")
        
        # Update last login
        user["last_login"] = datetime.now()
        
        return {
            "success": True,
            "user": {
                "id": user["id"],
                "employee_id": user["employee_id"],
                "name": user["name"],
                "role": "receptionist",  # Always receptionist for this model
                "department": user.get("department"),
                "phone": user.get("phone"),
                "email": user.get("email")
            }
        }

    # -----------------------------
    # CRUD Operations
    # -----------------------------
    
    @staticmethod
    def create_receptionist(data: ReceptionistCreate) -> Dict:
        global next_receptionist_id
        r_id = next_receptionist_id
        
        # Check if employee_id already exists
        for receptionist in receptionist_db.values():
            if receptionist["employee_id"] == data.employee_id:
                return {"success": False, "error": "Employee ID already exists"}
        
        receptionist_db[r_id] = {
            "id": r_id,
            "employee_id": data.employee_id,
            "name": data.name,
            "phone": data.phone,
            "email": data.email,
            "department": data.department,
            "status": "active",
            "created_at": datetime.now(),
            "updated_at": None,
            "hashed_password": hash_password(data.password),
            "last_login": None
        }
        next_receptionist_id += 1
        
        return {
            "success": True,
            "receptionist": ReceptionistModel.get_by_id(r_id)
        }

    @staticmethod
    def update_receptionist(r_id: int, data: ReceptionistUpdate) -> Optional[Dict]:
        receptionist = receptionist_db.get(r_id)
        if not receptionist:
            return None
            
        for key, value in data.dict(exclude_unset=True).items():
            if value is not None:
                receptionist[key] = value
                
        receptionist["updated_at"] = datetime.now()
        return receptionist

    @staticmethod
    def get_all() -> List[Dict]:
        return list(receptionist_db.values())
    
    @staticmethod
    def get_all_receptionists() -> List[Dict]:
        """Get all receptionists (alias for get_all)"""
        return list(receptionist_db.values())
    
    @staticmethod
    def get_active_receptionists() -> List[Dict]:
        """Get only active receptionists"""
        return [r for r in receptionist_db.values() if r.get("status", "active") == "active"]

    @staticmethod
    def get_by_id(r_id: int) -> Optional[Dict]:
        receptionist = receptionist_db.get(r_id)
        if receptionist:
            # Don't return sensitive data
            return {
                "id": receptionist["id"],
                "employee_id": receptionist["employee_id"],
                "name": receptionist["name"],
                "phone": receptionist["phone"],
                "email": receptionist.get("email"),
                "department": receptionist.get("department"),
                "status": receptionist.get("status", "active"),
                "created_at": receptionist["created_at"],
                "last_login": receptionist.get("last_login")
            }
        return None
    
    @staticmethod
    def get_by_employee_id(employee_id: str) -> Optional[Dict]:
        """Get receptionist by employee ID"""
        for receptionist in receptionist_db.values():
            if receptionist["employee_id"] == employee_id:
                return ReceptionistModel.get_by_id(receptionist["id"])
        return None

    @staticmethod
    def delete_receptionist(r_id: int) -> bool:
        if r_id in receptionist_db:
            # Soft delete - mark as inactive instead of removing
            receptionist_db[r_id]["status"] = "inactive"
            receptionist_db[r_id]["updated_at"] = datetime.now()
            return True
        return False
    
    @staticmethod
    def permanently_delete(r_id: int) -> bool:
        """Permanently delete a receptionist (use with caution)"""
        if r_id in receptionist_db:
            del receptionist_db[r_id]
            return True
        return False


# Import timedelta for the sample data
from datetime import timedelta
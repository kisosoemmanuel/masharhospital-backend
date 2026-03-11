from datetime import datetime, timedelta
from typing import Optional, List, Dict
from pydantic import BaseModel
from enum import Enum
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

# -------------------------------------------------
# ENUMS
# -------------------------------------------------

class StaffRole(str, Enum):
    DOCTOR = "doctor"
    NURSE = "nurse"
    ADMIN = "admin"
    RECEPTIONIST = "receptionist"


class StaffStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    ON_LEAVE = "on_leave"


# -------------------------------------------------
# STAFF MODELS
# -------------------------------------------------

class StaffBase(BaseModel):
    staff_id: str
    name: str
    role: StaffRole
    phone: str
    email: Optional[str] = None
    department: Optional[str] = None
    specialization: Optional[str] = None


class StaffCreate(StaffBase):
    password: str
    joining_date: Optional[datetime] = None


class StaffUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    department: Optional[str] = None
    specialization: Optional[str] = None
    status: Optional[StaffStatus] = None


class StaffLogin(BaseModel):
    staff_id: str
    password: str
    role: Optional[str] = None  # Made role optional


class Staff(StaffBase):
    id: int
    status: StaffStatus = StaffStatus.ACTIVE
    joining_date: datetime
    last_login: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    hashed_password: Optional[str] = None  # Added for authentication

    class Config:
        from_attributes = True


# -------------------------------------------------
# BED MODEL
# -------------------------------------------------

class Bed(BaseModel):
    id: int
    bed_number: str
    department: str
    ward: str
    is_occupied: bool = False
    patient_id: Optional[int] = None
    assigned_at: Optional[datetime] = None


# -------------------------------------------------
# INVENTORY MODEL
# -------------------------------------------------

class InventoryItem(BaseModel):
    id: int
    name: str
    category: str
    quantity: int
    unit: str
    reorder_level: int
    last_restocked: datetime
    expiry_date: Optional[datetime] = None


# -------------------------------------------------
# ACTIVITY LOG MODEL
# -------------------------------------------------

class ActivityLog(BaseModel):
    id: int
    user_id: int
    user_name: str
    action: str
    details: str
    timestamp: datetime
    role: str


# -------------------------------------------------
# Password Utilities
# -------------------------------------------------
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


# -------------------------------------------------
# IN-MEMORY DATABASES
# -------------------------------------------------

staff_db: Dict[int, Dict] = {}

beds_db: List[Dict] = []

inventory_db: Dict[int, Dict] = {}

activity_log_db: List[Dict] = []


# -------------------------------------------------
# SAMPLE DATA INITIALIZATION
# -------------------------------------------------

# Add staff with hashed passwords
staff_db[1] = {
    "id": 1,
    "staff_id": "D001",
    "name": "Dr. John Kamau",
    "role": "doctor",
    "phone": "+254700111222",
    "email": "john.kamau@hospital.com",
    "department": "Cardiology",
    "specialization": "Cardiologist",
    "status": "active",
    "joining_date": datetime.now() - timedelta(days=365*3),
    "last_login": datetime.now() - timedelta(days=1),
    "created_at": datetime.now(),
    "updated_at": None,
    "hashed_password": hash_password("doctor123")
}

staff_db[2] = {
    "id": 2,
    "staff_id": "A001",
    "name": "Admin User",
    "role": "admin",
    "phone": "+254700111333",
    "email": "admin@hospital.com",
    "department": "Administration",
    "specialization": None,
    "status": "active",
    "joining_date": datetime.now() - timedelta(days=365*5),
    "last_login": datetime.now() - timedelta(days=1),
    "created_at": datetime.now(),
    "updated_at": None,
    "hashed_password": hash_password("admin123")
}

staff_db[3] = {
    "id": 3,
    "staff_id": "R001",
    "name": "Mary Wanjiku",
    "role": "receptionist",
    "phone": "+254700111444",
    "email": "mary.wanjiku@hospital.com",
    "department": "Front Desk",
    "specialization": None,
    "status": "active",
    "joining_date": datetime.now() - timedelta(days=365*2),
    "last_login": datetime.now() - timedelta(days=2),
    "created_at": datetime.now(),
    "updated_at": None,
    "hashed_password": hash_password("receptionist123")
}

staff_db[4] = {
    "id": 4,
    "staff_id": "N001",
    "name": "Nurse Sarah",
    "role": "nurse",
    "phone": "+254700111555",
    "email": "sarah@hospital.com",
    "department": "General Ward",
    "specialization": "Registered Nurse",
    "status": "active",
    "joining_date": datetime.now() - timedelta(days=365),
    "last_login": None,
    "created_at": datetime.now(),
    "updated_at": None,
    "hashed_password": hash_password("nurse123")
}


inventory_db[1] = {
    "id": 1,
    "name": "Paracetamol",
    "category": "medication",
    "quantity": 1500,
    "unit": "tablets",
    "reorder_level": 500,
    "last_restocked": datetime.now() - timedelta(days=7),
    "expiry_date": datetime.now() + timedelta(days=180)
}


beds_db.extend([
    {
        "id": i,
        "bed_number": f"B{i:03}",
        "department": "General",
        "ward": "Ward A",
        "is_occupied": False,
        "patient_id": None,
        "assigned_at": None
    }
    for i in range(1, 101)
])


# -------------------------------------------------
# ADMIN SERVICE MODEL
# -------------------------------------------------

class AdminModel:

    # -----------------------------
    # AUTHENTICATION (NEW)
    # -----------------------------
    @staticmethod
    def authenticate(staff_id: str, password: str, role: Optional[str] = None) -> Optional[Dict]:
        """
        Authenticate a staff member.
        If role is provided, try that role first.
        If no role provided or role-specific auth fails, try all roles.
        """
        print(f"Admin authentication attempt - Staff ID: {staff_id}, Role: {role}")
        
        user = None
        
        # If role is provided, try that specific role first
        if role:
            for u in staff_db.values():
                if u["staff_id"] == staff_id and u["role"] == role:
                    user = u
                    print(f"Found staff with matching role: {user['name']} - {user['role']}")
                    break
        
        # If no user found with that role or no role provided, try all roles
        if not user:
            print("Trying all roles...")
            for u in staff_db.values():
                if u["staff_id"] == staff_id:
                    user = u
                    print(f"Found staff: {user['name']} with role: {user['role']}")
                    break
        
        if not user:
            print(f"No staff found with ID: {staff_id}")
            return None
        
        # Verify password
        if not verify_password(password, user["hashed_password"]):
            print("Password verification failed")
            return None
        
        print(f"Authentication successful for {staff_id} with role {user['role']}")
        
        # Update last login
        user["last_login"] = datetime.now()
        
        return {
            "success": True,
            "user": {
                "id": user["id"],
                "staff_id": user["staff_id"],
                "name": user["name"],
                "role": user["role"],
                "department": user.get("department"),
                "specialization": user.get("specialization")
            }
        }

    # -----------------------------
    # STAFF MANAGEMENT
    # -----------------------------

    @staticmethod
    def get_all_staff(role: Optional[str] = None, department: Optional[str] = None) -> List[Dict]:
        """Get all staff members with optional filters"""
        staff_list = list(staff_db.values())
        
        if role:
            staff_list = [s for s in staff_list if s["role"] == role]
        
        if department:
            staff_list = [s for s in staff_list if s.get("department") == department]
        
        return staff_list

    @staticmethod
    def get_staff_by_id(staff_id: int) -> Optional[Dict]:
        return staff_db.get(staff_id)
    
    @staticmethod
    def get_staff_by_staff_id(staff_id_str: str) -> Optional[Dict]:
        """Get staff by their employee ID (e.g., D001)"""
        for staff in staff_db.values():
            if staff["staff_id"] == staff_id_str:
                return staff
        return None

    @staticmethod
    def create_staff(data: StaffCreate) -> Dict:
        new_id = max(staff_db.keys()) + 1 if staff_db else 1

        staff = {
            "id": new_id,
            "staff_id": data.staff_id,
            "name": data.name,
            "role": data.role.value if isinstance(data.role, Enum) else data.role,
            "phone": data.phone,
            "email": data.email,
            "department": data.department,
            "specialization": data.specialization,
            "status": "active",
            "joining_date": data.joining_date or datetime.now(),
            "created_at": datetime.now(),
            "updated_at": None,
            "hashed_password": hash_password(data.password),
            "last_login": None
        }

        staff_db[new_id] = staff
        
        # Log activity
        AdminModel.log_activity({
            "user_id": 0,
            "user_name": "System",
            "action": "CREATE_STAFF",
            "details": f"Created new staff: {data.name} ({data.role})",
            "role": "admin"
        })
        
        return staff

    @staticmethod
    def update_staff(staff_id: int, update: StaffUpdate):
        staff = staff_db.get(staff_id)

        if not staff:
            return None

        update_data = update.dict(exclude_unset=True)

        for key, value in update_data.items():
            if key == "role" and isinstance(value, Enum):
                staff[key] = value.value
            else:
                staff[key] = value

        staff["updated_at"] = datetime.now()
        
        # Log activity
        AdminModel.log_activity({
            "user_id": 0,
            "user_name": "System",
            "action": "UPDATE_STAFF",
            "details": f"Updated staff ID: {staff_id}",
            "role": "admin"
        })

        return staff

    @staticmethod
    def delete_staff(staff_id: int):
        if staff_id not in staff_db:
            return False

        staff = staff_db[staff_id]
        
        # Log activity before deletion
        AdminModel.log_activity({
            "user_id": 0,
            "user_name": "System",
            "action": "DELETE_STAFF",
            "details": f"Deleted staff: {staff['name']} ({staff['staff_id']})",
            "role": "admin"
        })

        del staff_db[staff_id]
        return True

    @staticmethod
    def get_staff_statistics() -> Dict:
        """Get statistics about staff members"""
        total = len(staff_db)
        by_role = {}
        by_status = {}
        
        for staff in staff_db.values():
            role = staff["role"]
            status = staff["status"]
            
            by_role[role] = by_role.get(role, 0) + 1
            by_status[status] = by_status.get(status, 0) + 1
        
        return {
            "total": total,
            "by_role": by_role,
            "by_status": by_status
        }

    # -----------------------------
    # BED MANAGEMENT
    # -----------------------------

    @staticmethod
    def get_beds():
        return beds_db
    
    @staticmethod
    def get_bed_status() -> Dict:
        """Get bed occupancy statistics"""
        total = len(beds_db)
        occupied = len([b for b in beds_db if b["is_occupied"]])
        available = total - occupied
        
        by_department = {}
        for bed in beds_db:
            dept = bed["department"]
            if dept not in by_department:
                by_department[dept] = {"total": 0, "occupied": 0, "available": 0}
            
            by_department[dept]["total"] += 1
            if bed["is_occupied"]:
                by_department[dept]["occupied"] += 1
            else:
                by_department[dept]["available"] += 1
        
        return {
            "total": total,
            "occupied": occupied,
            "available": available,
            "by_department": by_department
        }

    @staticmethod
    def assign_bed(bed_id: int, patient_id: int):
        for bed in beds_db:
            if bed["id"] == bed_id:
                if bed["is_occupied"]:
                    return None

                bed["is_occupied"] = True
                bed["patient_id"] = patient_id
                bed["assigned_at"] = datetime.now()
                
                # Log activity
                AdminModel.log_activity({
                    "user_id": 0,
                    "user_name": "System",
                    "action": "ASSIGN_BED",
                    "details": f"Assigned bed {bed_id} to patient {patient_id}",
                    "role": "admin"
                })

                return bed

        return None

    @staticmethod
    def release_bed(bed_id: int):
        for bed in beds_db:
            if bed["id"] == bed_id:
                patient_id = bed["patient_id"]
                bed["is_occupied"] = False
                bed["patient_id"] = None
                bed["assigned_at"] = None
                
                # Log activity
                AdminModel.log_activity({
                    "user_id": 0,
                    "user_name": "System",
                    "action": "RELEASE_BED",
                    "details": f"Released bed {bed_id} from patient {patient_id}",
                    "role": "admin"
                })

                return bed

        return None

    # -----------------------------
    # INVENTORY
    # -----------------------------

    @staticmethod
    def get_inventory():
        return list(inventory_db.values())
    
    @staticmethod
    def get_inventory_status() -> Dict:
        """Get inventory statistics"""
        total_items = len(inventory_db)
        low_stock = []
        
        for item in inventory_db.values():
            if item["quantity"] <= item["reorder_level"]:
                low_stock.append({
                    "id": item["id"],
                    "name": item["name"],
                    "quantity": item["quantity"],
                    "reorder_level": item["reorder_level"]
                })
        
        return {
            "total_items": total_items,
            "low_stock_count": len(low_stock),
            "low_stock_items": low_stock
        }

    @staticmethod
    def update_inventory(item_id: int, quantity_change: int):
        item = inventory_db.get(item_id)

        if not item:
            return None

        old_quantity = item["quantity"]
        item["quantity"] = max(0, item["quantity"] + quantity_change)
        item["last_restocked"] = datetime.now()
        
        # Log activity
        AdminModel.log_activity({
            "user_id": 0,
            "user_name": "System",
            "action": "UPDATE_INVENTORY",
            "details": f"Updated inventory item {item_id}: {old_quantity} -> {item['quantity']}",
            "role": "admin"
        })

        return item

    # -----------------------------
    # ACTIVITY LOG
    # -----------------------------

    @staticmethod
    def log_activity(log_data: Dict):
        """Add an entry to the activity log"""
        global activity_log_db
        new_id = max([log["id"] for log in activity_log_db]) + 1 if activity_log_db else 1
        
        log_entry = {
            "id": new_id,
            **log_data,
            "timestamp": datetime.now()
        }
        
        activity_log_db.append(log_entry)
        
        # Keep only last 100 logs
        if len(activity_log_db) > 100:
            activity_log_db = activity_log_db[-100:]
        
        return log_entry

    @staticmethod
    def get_activity_logs(limit: int = 50):
        """Get recent activity logs"""
        return sorted(activity_log_db, key=lambda x: x["timestamp"], reverse=True)[:limit]
    
    @staticmethod
    def get_recent_activity(limit: int = 10):
        """Get recent activity for dashboard"""
        logs = AdminModel.get_activity_logs(limit)
        return [
            {
                "id": log["id"],
                "user": log["user_name"],
                "action": log["action"],
                "details": log["details"],
                "time": log["timestamp"].isoformat(),
                "role": log["role"]
            }
            for log in logs
        ]

    # -----------------------------
    # ADMIN DASHBOARD
    # -----------------------------

    @staticmethod
    def get_dashboard_stats():
        total_staff = len(staff_db)
        total_beds = len(beds_db)
        occupied_beds = len([b for b in beds_db if b["is_occupied"]])
        available_beds = total_beds - occupied_beds

        low_stock = [
            item for item in inventory_db.values()
            if item["quantity"] <= item["reorder_level"]
        ]
        
        # Staff by role
        staff_by_role = {}
        for staff in staff_db.values():
            role = staff["role"]
            staff_by_role[role] = staff_by_role.get(role, 0) + 1

        return {
            "total_staff": total_staff,
            "staff_by_role": staff_by_role,
            "total_beds": total_beds,
            "occupied_beds": occupied_beds,
            "available_beds": available_beds,
            "bed_occupancy_rate": round((occupied_beds / total_beds * 100) if total_beds > 0 else 0, 2),
            "low_stock_items": len(low_stock),
            "low_stock_details": low_stock[:5],  # Show first 5 low stock items
            "recent_activity": AdminModel.get_recent_activity(5)
        }

    # -----------------------------
    # REPORTS
    # -----------------------------

    @staticmethod
    def get_all_records() -> Dict:
        """Get all records for admin overview"""
        return {
            "staff": list(staff_db.values()),
            "beds": beds_db,
            "inventory": list(inventory_db.values()),
            "activity_logs": activity_log_db[-20:]  # Last 20 logs
        }
    
    @staticmethod
    def generate_monthly_report() -> Dict:
        """Generate a monthly report with statistics"""
        current_month = datetime.now().month
        current_year = datetime.now().year
        
        # This is a simplified report - in a real app, you'd aggregate data from various sources
        return {
            "month": current_month,
            "year": current_year,
            "generated_at": datetime.now().isoformat(),
            "statistics": {
                "staff": AdminModel.get_staff_statistics(),
                "beds": AdminModel.get_bed_status(),
                "inventory": AdminModel.get_inventory_status()
            },
            "recent_activities": AdminModel.get_recent_activity(10)
        }


# Counters for generating new IDs (for backward compatibility)
next_staff_id = max(staff_db.keys()) + 1 if staff_db else 1
next_activity_id = max([log["id"] for log in activity_log_db]) + 1 if activity_log_db else 1
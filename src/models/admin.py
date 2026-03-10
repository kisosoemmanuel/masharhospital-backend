from datetime import datetime, timedelta
from typing import Optional, List, Dict
from pydantic import BaseModel
from enum import Enum


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


class Staff(StaffBase):
    id: int
    status: StaffStatus = StaffStatus.ACTIVE
    joining_date: datetime
    last_login: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

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
# IN-MEMORY DATABASES
# -------------------------------------------------

staff_db: Dict[int, Dict] = {}

beds_db: List[Dict] = []

inventory_db: Dict[int, Dict] = {}

activity_log_db: List[Dict] = []


# -------------------------------------------------
# SAMPLE DATA INITIALIZATION
# -------------------------------------------------

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
    "updated_at": None
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
    # STAFF MANAGEMENT
    # -----------------------------

    @staticmethod
    def get_all_staff() -> List[Dict]:
        return list(staff_db.values())

    @staticmethod
    def get_staff_by_id(staff_id: int) -> Optional[Dict]:
        return staff_db.get(staff_id)

    @staticmethod
    def create_staff(data: StaffCreate) -> Dict:

        new_id = max(staff_db.keys()) + 1 if staff_db else 1

        staff = {
            "id": new_id,
            "staff_id": data.staff_id,
            "name": data.name,
            "role": data.role,
            "phone": data.phone,
            "email": data.email,
            "department": data.department,
            "specialization": data.specialization,
            "status": "active",
            "joining_date": data.joining_date or datetime.now(),
            "created_at": datetime.now(),
            "updated_at": None
        }

        staff_db[new_id] = staff
        return staff

    @staticmethod
    def update_staff(staff_id: int, update: StaffUpdate):

        staff = staff_db.get(staff_id)

        if not staff:
            return None

        update_data = update.dict(exclude_unset=True)

        for key, value in update_data.items():
            staff[key] = value

        staff["updated_at"] = datetime.now()

        return staff

    @staticmethod
    def delete_staff(staff_id: int):

        if staff_id not in staff_db:
            return False

        del staff_db[staff_id]
        return True


    # -----------------------------
    # BED MANAGEMENT
    # -----------------------------

    @staticmethod
    def get_beds():
        return beds_db

    @staticmethod
    def assign_bed(bed_id: int, patient_id: int):

        for bed in beds_db:
            if bed["id"] == bed_id:

                if bed["is_occupied"]:
                    return None

                bed["is_occupied"] = True
                bed["patient_id"] = patient_id
                bed["assigned_at"] = datetime.now()

                return bed

        return None

    @staticmethod
    def release_bed(bed_id: int):

        for bed in beds_db:

            if bed["id"] == bed_id:

                bed["is_occupied"] = False
                bed["patient_id"] = None
                bed["assigned_at"] = None

                return bed

        return None


    # -----------------------------
    # INVENTORY
    # -----------------------------

    @staticmethod
    def get_inventory():
        return list(inventory_db.values())

    @staticmethod
    def update_inventory(item_id: int, quantity: int):

        item = inventory_db.get(item_id)

        if not item:
            return None

        item["quantity"] = quantity
        item["last_restocked"] = datetime.now()

        return item


    # -----------------------------
    # ACTIVITY LOG
    # -----------------------------

    @staticmethod
    def get_activity_logs():
        return activity_log_db


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

        return {
            "total_staff": total_staff,
            "total_beds": total_beds,
            "occupied_beds": occupied_beds,
            "available_beds": available_beds,
            "low_stock_items": len(low_stock),
            "recent_activity": activity_log_db[:5]
        }  

# Counters for generating new IDs (for backward compatibility)
next_staff_id = max(staff_db.keys()) + 1 if staff_db else 1
next_activity_id = max([log["id"] for log in activity_log_db]) + 1 if activity_log_db else 1
from datetime import datetime, timedelta
from typing import Optional, List, Dict
from pydantic import BaseModel
from enum import Enum

class StaffRole(str, Enum):
    DOCTOR = "doctor"
    NURSE = "nurse"
    ADMIN = "admin"
    RECEPTIONIST = "receptionist"

class StaffStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    ON_LEAVE = "on_leave"

class StaffBase(BaseModel):
    staff_id: str
    name: str
    role: StaffRole
    phone: str
    email: Optional[str] = None
    department: Optional[str] = None
    specialization: Optional[str] = None  # For doctors

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

class Bed(BaseModel):
    id: int
    bed_number: str
    department: str
    is_occupied: bool = False
    patient_id: Optional[int] = None
    assigned_at: Optional[datetime] = None
    ward: str

class InventoryItem(BaseModel):
    id: int
    name: str
    category: str  # medication, equipment, supply
    quantity: int
    unit: str
    reorder_level: int
    last_restocked: datetime
    expiry_date: Optional[datetime] = None

class ActivityLog(BaseModel):
    id: int
    user_id: int
    user_name: str
    action: str
    details: str
    timestamp: datetime
    role: str

# In-memory databases
staff_db = {
    1: {
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
        "created_at": datetime.now() - timedelta(days=365*3),
        "updated_at": None
    },
    2: {
        "id": 2,
        "staff_id": "D002",
        "name": "Dr. Mercy Wanjiru",
        "role": "doctor",
        "phone": "+254700333555",
        "email": "mercy.wanjiru@hospital.com",
        "department": "Pediatrics",
        "specialization": "Pediatrician",
        "status": "active",
        "joining_date": datetime.now() - timedelta(days=365*2),
        "last_login": datetime.now() - timedelta(days=2),
        "created_at": datetime.now() - timedelta(days=365*2),
        "updated_at": None
    },
    3: {
        "id": 3,
        "staff_id": "N001",
        "name": "Nurse Achieng",
        "role": "nurse",
        "phone": "+254700444666",
        "email": "achieng@hospital.com",
        "department": "Emergency",
        "specialization": None,
        "status": "active",
        "joining_date": datetime.now() - timedelta(days=365),
        "last_login": datetime.now() - timedelta(hours=5),
        "created_at": datetime.now() - timedelta(days=365),
        "updated_at": None
    },
    4: {
        "id": 4,
        "staff_id": "N002",
        "name": "Nurse Mwikali",
        "role": "nurse",
        "phone": "+254700777888",
        "email": "mwikali@hospital.com",
        "department": "Maternity",
        "specialization": None,
        "status": "active",
        "joining_date": datetime.now() - timedelta(days=180),
        "last_login": datetime.now() - timedelta(days=1),
        "created_at": datetime.now() - timedelta(days=180),
        "updated_at": None
    },
    5: {
        "id": 5,
        "staff_id": "R001",
        "name": "Receptionist Jane",
        "role": "receptionist",
        "phone": "+254700999000",
        "email": "jane@hospital.com",
        "department": "Front Desk",
        "specialization": None,
        "status": "active",
        "joining_date": datetime.now() - timedelta(days=90),
        "last_login": datetime.now() - timedelta(hours=2),
        "created_at": datetime.now() - timedelta(days=90),
        "updated_at": None
    }
}

beds_db = [
    {
        "id": i,
        "bed_number": f"B{str(i).zfill(3)}",
        "department": "General" if i <= 50 else "ICU" if i <= 70 else "Maternity",
        "ward": "Ward A" if i <= 30 else "Ward B" if i <= 60 else "Ward C",
        "is_occupied": i <= 56,  # 56 beds occupied as per screenshot
        "patient_id": i if i <= 56 else None,
        "assigned_at": datetime.now() - timedelta(days=i) if i <= 56 else None
    }
    for i in range(1, 101)  # 100 beds total
]

inventory_db = {
    1: {
        "id": 1,
        "name": "Paracetamol",
        "category": "medication",
        "quantity": 1500,
        "unit": "tablets",
        "reorder_level": 500,
        "last_restocked": datetime.now() - timedelta(days=7),
        "expiry_date": datetime.now() + timedelta(days=180)
    },
    2: {
        "id": 2,
        "name": "Amoxicillin",
        "category": "medication",
        "quantity": 800,
        "unit": "capsules",
        "reorder_level": 300,
        "last_restocked": datetime.now() - timedelta(days=14),
        "expiry_date": datetime.now() + timedelta(days=90)
    },
    3: {
        "id": 3,
        "name": "Surgical Gloves",
        "category": "supply",
        "quantity": 2000,
        "unit": "pairs",
        "reorder_level": 500,
        "last_restocked": datetime.now() - timedelta(days=5),
        "expiry_date": None
    },
    4: {
        "id": 4,
        "name": "Face Masks",
        "category": "supply",
        "quantity": 5000,
        "unit": "pieces",
        "reorder_level": 1000,
        "last_restocked": datetime.now() - timedelta(days=3),
        "expiry_date": None
    }
}

activity_log_db = [
    {
        "id": 1,
        "user_id": 1,
        "user_name": "Dr. John Kamau",
        "role": "doctor",
        "action": "add_prescription",
        "details": "Added prescription for Patient Mary Wanjiru",
        "timestamp": datetime.now() - timedelta(minutes=30)
    },
    {
        "id": 2,
        "user_id": 3,
        "user_name": "Nurse Achieng",
        "role": "nurse",
        "action": "admit_patient",
        "details": "Admitted patient James Otieno to Emergency",
        "timestamp": datetime.now() - timedelta(hours=2)
    },
    {
        "id": 3,
        "user_id": 5,
        "user_name": "Receptionist Jane",
        "role": "receptionist",
        "action": "register_patient",
        "details": "Registered new patient Faith Achieng",
        "timestamp": datetime.now() - timedelta(hours=3)
    },
    {
        "id": 4,
        "user_id": 1,
        "user_name": "Dr. John Kamau",
        "role": "doctor",
        "action": "monthly_report",
        "details": "Generated monthly department report",
        "timestamp": datetime.now() - timedelta(hours=5)
    }
]
next_staff_id = max(staff_db.keys()) + 1
next_activity_id = max([log["id"] for log in activity_log_db]) + 1
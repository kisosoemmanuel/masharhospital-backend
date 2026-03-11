from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, validator
from enum import Enum
import re

# -----------------------------
# Enums
# -----------------------------
class PatientStatus(str, Enum):
    WAITING = "waiting"
    IN_PROGRESS = "in_progress"
    TREATED = "treated"
    CANCELLED = "cancelled"
    NO_SHOW = "no_show"


class PatientPriority(int, Enum):
    NORMAL = 1
    URGENT = 2
    EMERGENCY = 3
    CRITICAL = 4


class NotificationType(str, Enum):
    SUCCESS = "success"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class Gender(str, Enum):
    MALE = "male"
    FEMALE = "female"
    OTHER = "other"


class BloodGroup(str, Enum):
    A_POSITIVE = "A+"
    A_NEGATIVE = "A-"
    B_POSITIVE = "B+"
    B_NEGATIVE = "B-"
    O_POSITIVE = "O+"
    O_NEGATIVE = "O-"
    AB_POSITIVE = "AB+"
    AB_NEGATIVE = "AB-"


# -----------------------------
# Patient Models
# -----------------------------
class PatientBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    age: Optional[int] = Field(None, ge=0, le=150)
    gender: Optional[Gender] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    blood_group: Optional[BloodGroup] = None
    emergency_contact: Optional[str] = None
    emergency_contact_name: Optional[str] = None
    medical_history: Optional[List[str]] = Field(default_factory=list)
    allergies: Optional[List[str]] = Field(default_factory=list)
    
    @validator('phone')
    def validate_phone(cls, v):
        if v and not re.match(r'^\+?[0-9]{10,15}$', v):
            raise ValueError('Invalid phone number format')
        return v
    
    @validator('email')
    def validate_email(cls, v):
        if v and not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', v):
            raise ValueError('Invalid email format')
        return v


class PatientCreate(PatientBase):
    pass


class PatientUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=100)
    age: Optional[int] = Field(None, ge=0, le=150)
    gender: Optional[Gender] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    blood_group: Optional[BloodGroup] = None
    emergency_contact: Optional[str] = None
    emergency_contact_name: Optional[str] = None
    medical_history: Optional[List[str]] = None
    allergies: Optional[List[str]] = None


class Patient(PatientBase):
    id: int
    patient_number: Optional[str] = None  # Format: P-YYYY-MM-XXXX
    created_at: datetime
    updated_at: Optional[datetime] = None
    created_by: Optional[int] = None  # User ID who created this record
    total_visits: Optional[int] = 0
    last_visit: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class PatientResponse(BaseModel):
    success: bool
    data: Optional[Patient] = None
    message: Optional[str] = None
    error: Optional[str] = None


# -----------------------------
# Consultation Models
# -----------------------------
class ConsultationBase(BaseModel):
    patient_id: int
    doctor_id: int
    department: str
    condition: str
    priority: PatientPriority = PatientPriority.NORMAL
    symptoms: Optional[List[str]] = Field(default_factory=list)
    diagnosis: Optional[str] = None
    notes: Optional[str] = None


class ConsultationCreate(ConsultationBase):
    room: Optional[str] = None
    created_by: Optional[int] = None  # Receptionist ID who created this


class ConsultationUpdate(BaseModel):
    doctor_id: Optional[int] = None
    department: Optional[str] = None
    condition: Optional[str] = None
    priority: Optional[PatientPriority] = None
    symptoms: Optional[List[str]] = None
    diagnosis: Optional[str] = None
    notes: Optional[str] = None
    room: Optional[str] = None
    status: Optional[PatientStatus] = None
    satisfaction_rating: Optional[int] = Field(None, ge=1, le=5)


class Consultation(ConsultationBase):
    id: int
    consultation_number: Optional[str] = None  # Format: C-YYYYMMDD-XXXX
    room: Optional[str] = None
    status: PatientStatus = PatientStatus.WAITING
    queue_number: Optional[int] = None
    position: Optional[int] = None  # Position in queue
    estimated_wait_time: Optional[int] = None  # In minutes
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    cancellation_reason: Optional[str] = None
    satisfaction_rating: Optional[int] = None
    feedback: Optional[str] = None
    created_by: Optional[int] = None
    
    class Config:
        from_attributes = True
    
    @property
    def wait_duration(self) -> Optional[int]:
        """Calculate wait duration in minutes"""
        if self.started_at and self.created_at:
            return int((self.started_at - self.created_at).total_seconds() / 60)
        return None
    
    @property
    def consultation_duration(self) -> Optional[int]:
        """Calculate consultation duration in minutes"""
        if self.completed_at and self.started_at:
            return int((self.completed_at - self.started_at).total_seconds() / 60)
        return None


# -----------------------------
# Prescription Models
# -----------------------------
class PrescriptionBase(BaseModel):
    patient_id: int
    doctor_id: int
    consultation_id: Optional[int] = None
    medication: str
    instructions: Optional[str] = None
    dosage: Optional[str] = None
    duration: Optional[str] = None
    quantity: Optional[int] = Field(1, ge=1)
    refills: Optional[int] = Field(0, ge=0)
    notes: Optional[str] = None


class PrescriptionCreate(PrescriptionBase):
    pass


class PrescriptionUpdate(BaseModel):
    medication: Optional[str] = None
    instructions: Optional[str] = None
    dosage: Optional[str] = None
    duration: Optional[str] = None
    quantity: Optional[int] = Field(None, ge=1)
    refills: Optional[int] = Field(None, ge=0)
    notes: Optional[str] = None


class Prescription(PrescriptionBase):
    id: int
    prescription_number: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    filled_at: Optional[datetime] = None
    filled_by: Optional[str] = None
    is_filled: bool = False
    
    class Config:
        from_attributes = True


# -----------------------------
# Quick Registration Model
# -----------------------------
class QuickRegistration(BaseModel):
    patient_name: str = Field(..., min_length=2, max_length=100)
    phone: str
    age: Optional[int] = Field(None, ge=0, le=150)
    gender: Optional[Gender] = None
    condition: str = Field(..., min_length=3)
    priority: int = Field(3, ge=1, le=4)  # 1=Normal, 2=Urgent, 3=Emergency, 4=Critical
    department: str = "General"
    doctor_id: Optional[int] = None
    room: Optional[str] = None
    symptoms: Optional[List[str]] = Field(default_factory=list)
    emergency_contact: Optional[str] = None
    receptionist_name: Optional[str] = None
    
    @validator('phone')
    def validate_phone(cls, v):
        if not re.match(r'^\+?[0-9]{10,15}$', v):
            raise ValueError('Invalid phone number format. Use +254XXXXXXXXX or 07XXXXXXXX')
        return v
    
    class Config:
        schema_extra = {
            "example": {
                "patient_name": "John Doe",
                "phone": "+254700111222",
                "age": 35,
                "gender": "male",
                "condition": "Chest pain",
                "priority": 3,
                "department": "Cardiology",
                "symptoms": ["chest pain", "shortness of breath"]
            }
        }


# -----------------------------
# Notification Models
# -----------------------------
class Notification(BaseModel):
    id: int
    user_id: Optional[int] = None  # Can be None for system notifications
    user_name: Optional[str] = None
    message: str
    type: NotificationType
    timestamp: datetime
    read: bool = False
    read_at: Optional[datetime] = None
    role_target: Optional[str] = 'all'  # 'receptionist', 'doctor', 'admin', 'all'
    action_url: Optional[str] = None
    action_text: Optional[str] = None


class NotificationCreate(BaseModel):
    user_id: Optional[int] = None
    user_name: Optional[str] = None
    message: str
    type: NotificationType = NotificationType.INFO
    role_target: str = 'all'
    action_url: Optional[str] = None
    action_text: Optional[str] = None


# -----------------------------
# Statistics Models
# -----------------------------
class DepartmentStats(BaseModel):
    department: str
    total_patients: int
    waiting: int
    in_progress: int
    completed_today: int
    average_wait_time: int
    doctors_available: int


class DailyStats(BaseModel):
    date: str
    total_patients: int
    new_patients: int
    returning_patients: int
    average_wait_time: int
    satisfaction_score: float


# -----------------------------
# In-Memory Databases
# -----------------------------

# Patients database
patients_db: Dict[int, Dict] = {
    1: {
        "id": 1,
        "patient_number": "P-2024-01-0001",
        "name": "John Doe",
        "age": 45,
        "gender": "male",
        "phone": "+254700111222",
        "email": "john@email.com",
        "address": "Nairobi",
        "blood_group": "O+",
        "emergency_contact": "+254700111223",
        "emergency_contact_name": "Jane Doe",
        "medical_history": ["Hypertension", "Diabetes"],
        "allergies": ["Penicillin"],
        "created_at": datetime.now() - timedelta(days=365),
        "updated_at": datetime.now() - timedelta(days=30),
        "created_by": 1,
        "total_visits": 5,
        "last_visit": datetime.now() - timedelta(days=30)
    },
    2: {
        "id": 2,
        "patient_number": "P-2024-01-0002",
        "name": "Mary Wanjiuru",
        "age": 32,
        "gender": "female",
        "phone": "+254700111333",
        "email": "mary@email.com",
        "address": "Kiambu",
        "blood_group": "A+",
        "emergency_contact": "+254700111334",
        "emergency_contact_name": "Peter Wanjiuru",
        "medical_history": [],
        "allergies": [],
        "created_at": datetime.now() - timedelta(days=180),
        "updated_at": None,
        "created_by": 1,
        "total_visits": 2,
        "last_visit": datetime.now() - timedelta(days=25)
    },
    3: {
        "id": 3,
        "patient_number": "P-2024-01-0003",
        "name": "James Otieno",
        "age": 28,
        "gender": "male",
        "phone": "+254700111444",
        "email": "james@email.com",
        "address": "Kisumu",
        "blood_group": "B+",
        "emergency_contact": "+254700111445",
        "emergency_contact_name": "Sarah Otieno",
        "medical_history": ["Asthma"],
        "allergies": ["Dust"],
        "created_at": datetime.now() - timedelta(days=90),
        "updated_at": None,
        "created_by": 2,
        "total_visits": 3,
        "last_visit": datetime.now() - timedelta(days=20)
    },
    4: {
        "id": 4,
        "patient_number": "P-2024-01-0004",
        "name": "Faith Achieng",
        "age": 25,
        "gender": "female",
        "phone": "+254700111555",
        "email": "faith@email.com",
        "address": "Mombasa",
        "blood_group": "AB+",
        "emergency_contact": "+254700111556",
        "emergency_contact_name": "John Achieng",
        "medical_history": [],
        "allergies": ["Seafood"],
        "created_at": datetime.now() - timedelta(days=60),
        "updated_at": None,
        "created_by": 1,
        "total_visits": 1,
        "last_visit": datetime.now() - timedelta(days=15)
    },
    5: {
        "id": 5,
        "patient_number": "P-2024-01-0005",
        "name": "Peter Mwangi",
        "age": 55,
        "gender": "male",
        "phone": "+254700111666",
        "email": "peter@email.com",
        "address": "Nakuru",
        "blood_group": "O-",
        "emergency_contact": "+254700111667",
        "emergency_contact_name": "Lucy Mwangi",
        "medical_history": ["Diabetes", "Hypertension"],
        "allergies": [],
        "created_at": datetime.now() - timedelta(days=30),
        "updated_at": None,
        "created_by": 2,
        "total_visits": 4,
        "last_visit": datetime.now() - timedelta(days=10)
    }
}

# Consultations database
consultations_db: Dict[int, Dict] = {
    1: {
        "id": 1,
        "consultation_number": "C-20240315-0001",
        "patient_id": 1,
        "doctor_id": 1,
        "department": "Cardiology",
        "room": "4B",
        "condition": "Chest pain",
        "symptoms": ["chest pain", "shortness of breath"],
        "diagnosis": "Angina",
        "notes": "Patient advised to rest",
        "priority": 3,
        "status": "in_progress",
        "queue_number": 1,
        "position": 0,
        "estimated_wait_time": 0,
        "created_at": datetime.now() - timedelta(minutes=30),
        "started_at": datetime.now() - timedelta(minutes=25),
        "completed_at": None,
        "cancelled_at": None,
        "cancellation_reason": None,
        "satisfaction_rating": None,
        "feedback": None,
        "created_by": 1
    },
    2: {
        "id": 2,
        "consultation_number": "C-20240315-0002",
        "patient_id": 2,
        "doctor_id": 1,
        "department": "Cardiology",
        "room": "4B",
        "condition": "Headache",
        "symptoms": ["severe headache", "nausea"],
        "diagnosis": None,
        "notes": None,
        "priority": 1,
        "status": "waiting",
        "queue_number": 2,
        "position": 1,
        "estimated_wait_time": 15,
        "created_at": datetime.now() - timedelta(minutes=20),
        "started_at": None,
        "completed_at": None,
        "cancelled_at": None,
        "cancellation_reason": None,
        "satisfaction_rating": None,
        "feedback": None,
        "created_by": 1
    },
    3: {
        "id": 3,
        "consultation_number": "C-20240315-0003",
        "patient_id": 3,
        "doctor_id": 1,
        "department": "Cardiology",
        "room": "4B",
        "condition": "Injury",
        "symptoms": ["sprained ankle", "swelling"],
        "diagnosis": "Sprained ankle",
        "notes": "X-ray taken",
        "priority": 2,
        "status": "waiting",
        "queue_number": 3,
        "position": 2,
        "estimated_wait_time": 30,
        "created_at": datetime.now() - timedelta(minutes=15),
        "started_at": None,
        "completed_at": None,
        "cancelled_at": None,
        "cancellation_reason": None,
        "satisfaction_rating": None,
        "feedback": None,
        "created_by": 1
    },
    4: {
        "id": 4,
        "consultation_number": "C-20240315-0004",
        "patient_id": 4,
        "doctor_id": 1,
        "department": "Cardiology",
        "room": "4B",
        "condition": "Malaria",
        "symptoms": ["fever", "chills", "headache"],
        "diagnosis": "Malaria",
        "notes": "Prescribed antimalarial",
        "priority": 1,
        "status": "treated",
        "queue_number": 4,
        "position": 3,
        "estimated_wait_time": 45,
        "created_at": datetime.now() - timedelta(hours=3),
        "started_at": datetime.now() - timedelta(hours=3),
        "completed_at": datetime.now() - timedelta(hours=2, minutes=45),
        "cancelled_at": None,
        "cancellation_reason": None,
        "satisfaction_rating": 5,
        "feedback": "Excellent care",
        "created_by": 1
    },
    5: {
        "id": 5,
        "consultation_number": "C-20240315-0005",
        "patient_id": 5,
        "doctor_id": 1,
        "department": "Cardiology",
        "room": "4B",
        "condition": "High Blood Pressure",
        "symptoms": ["dizziness", "headache"],
        "diagnosis": "Hypertension",
        "notes": "BP: 140/90",
        "priority": 2,
        "status": "in_progress",
        "queue_number": 5,
        "position": 0,
        "estimated_wait_time": 0,
        "created_at": datetime.now() - timedelta(minutes=45),
        "started_at": datetime.now() - timedelta(minutes=40),
        "completed_at": None,
        "cancelled_at": None,
        "cancellation_reason": None,
        "satisfaction_rating": None,
        "feedback": None,
        "created_by": 2
    }
}

# Prescriptions database
prescriptions_db: Dict[int, Dict] = {}
next_prescription_id = 1

# Add sample prescriptions
prescriptions_db[1] = {
    "id": 1,
    "prescription_number": "RX-20240315-0001",
    "patient_id": 1,
    "doctor_id": 1,
    "consultation_id": 1,
    "medication": "Aspirin",
    "instructions": "Take with food",
    "dosage": "75mg",
    "duration": "30 days",
    "quantity": 30,
    "refills": 2,
    "notes": "Take once daily",
    "created_at": datetime.now() - timedelta(minutes=20),
    "updated_at": None,
    "filled_at": None,
    "filled_by": None,
    "is_filled": False
}

prescriptions_db[2] = {
    "id": 2,
    "prescription_number": "RX-20240315-0002",
    "patient_id": 4,
    "doctor_id": 1,
    "consultation_id": 4,
    "medication": "Artemether/Lumefantrine",
    "instructions": "Take with food",
    "dosage": "80mg/480mg",
    "duration": "3 days",
    "quantity": 12,
    "refills": 0,
    "notes": "Take twice daily",
    "created_at": datetime.now() - timedelta(hours=2),
    "updated_at": None,
    "filled_at": datetime.now() - timedelta(hours=1, minutes=30),
    "filled_by": "Pharmacist John",
    "is_filled": True
}

# Notifications database
notifications_db: List[Dict] = [
    {
        "id": 1,
        "user_id": 1,
        "user_name": "Dr. John Kamau",
        "message": "Patient Mary Wanjiuru marked as treated",
        "type": "success",
        "timestamp": datetime.now() - timedelta(minutes=2),
        "read": False,
        "read_at": None,
        "role_target": "all",
        "action_url": "/consultations/2",
        "action_text": "View"
    },
    {
        "id": 2,
        "user_id": None,
        "user_name": "System",
        "message": "New emergency case added to queue",
        "type": "warning",
        "timestamp": datetime.now() - timedelta(minutes=10),
        "read": False,
        "read_at": None,
        "role_target": "receptionist",
        "action_url": "/queue",
        "action_text": "View Queue"
    },
    {
        "id": 3,
        "user_id": 5,
        "user_name": "Receptionist Jane",
        "message": "New patient registered at front desk",
        "type": "info",
        "timestamp": datetime.now() - timedelta(minutes=30),
        "read": False,
        "read_at": None,
        "role_target": "all",
        "action_url": "/patients/6",
        "action_text": "View Patient"
    },
    {
        "id": 4,
        "user_id": 2,
        "user_name": "Dr. Jane Smith",
        "message": "Lab results ready for patient James Otieno",
        "type": "info",
        "timestamp": datetime.now() - timedelta(minutes=15),
        "read": True,
        "read_at": datetime.now() - timedelta(minutes=14),
        "role_target": "doctor",
        "action_url": "/lab-results/3",
        "action_text": "View Results"
    }
]

# Set next notification ID
next_notification_id = max([n["id"] for n in notifications_db]) + 1 if notifications_db else 1


# -----------------------------
# Patient Service Class
# -----------------------------
class PatientService:
    """Service class for patient-related operations"""
    
    @staticmethod
    def generate_patient_number() -> str:
        """Generate a unique patient number"""
        now = datetime.now()
        year = now.year
        month = f"{now.month:02d}"
        
        # Count patients created this month
        count = len([
            p for p in patients_db.values()
            if p.get("created_at", datetime.min).year == year and
            p.get("created_at", datetime.min).month == now.month
        ])
        
        return f"P-{year}-{month}-{count+1:04d}"
    
    @staticmethod
    def generate_consultation_number() -> str:
        """Generate a unique consultation number"""
        now = datetime.now()
        date_str = now.strftime("%Y%m%d")
        
        # Count consultations today
        count = len([
            c for c in consultations_db.values()
            if c.get("created_at", datetime.min).date() == now.date()
        ])
        
        return f"C-{date_str}-{count+1:04d}"
    
    @staticmethod
    def generate_prescription_number() -> str:
        """Generate a unique prescription number"""
        now = datetime.now()
        date_str = now.strftime("%Y%m%d")
        
        # Count prescriptions today
        count = len([
            p for p in prescriptions_db.values()
            if p.get("created_at", datetime.min).date() == now.date()
        ])
        
        return f"RX-{date_str}-{count+1:04d}"
    
    @staticmethod
    def get_patient_by_id(patient_id: int) -> Optional[Dict]:
        """Get patient by ID with enhanced information"""
        patient = patients_db.get(patient_id)
        if not patient:
            return None
        
        # Get patient's visit history
        visits = [
            c for c in consultations_db.values()
            if c.get("patient_id") == patient_id
        ]
        
        # Get last visit
        last_visit = None
        if visits:
            last_visit = max(visits, key=lambda x: x.get("created_at", datetime.min))
        
        # Get current queue status if any
        current_consultation = None
        for c in consultations_db.values():
            if c.get("patient_id") == patient_id and c.get("status") in ["waiting", "in_progress"]:
                current_consultation = {
                    "id": c["id"],
                    "consultation_number": c.get("consultation_number"),
                    "department": c.get("department"),
                    "doctor_id": c.get("doctor_id"),
                    "status": c.get("status"),
                    "queue_number": c.get("queue_number"),
                    "position": c.get("position"),
                    "estimated_wait_time": c.get("estimated_wait_time")
                }
                break
        
        return {
            **patient,
            "total_visits": len(visits),
            "last_visit": last_visit.get("created_at") if last_visit else None,
            "current_consultation": current_consultation,
            "has_prescriptions": len([p for p in prescriptions_db.values() if p.get("patient_id") == patient_id]) > 0
        }
    
    @staticmethod
    def get_patients(search: Optional[str] = None, status: Optional[str] = None) -> List[Dict]:
        """Get all patients with optional filters"""
        patients = list(patients_db.values())
        
        if search:
            search = search.lower()
            patients = [
                p for p in patients
                if search in p.get("name", "").lower() or
                search in p.get("phone", "") or
                search in p.get("email", "").lower()
            ]
        
        if status:
            # Filter by patient status based on current consultations
            filtered = []
            for p in patients:
                has_active = any(
                    c for c in consultations_db.values()
                    if c.get("patient_id") == p["id"] and
                    c.get("status") == status
                )
                if (status == "active" and has_active) or \
                   (status == "inactive" and not has_active):
                    filtered.append(p)
            patients = filtered
        
        return patients
    
    @staticmethod
    def create_patient(patient_data: PatientCreate) -> Dict:
        """Create a new patient"""
        # Validate required fields
        if not patient_data.name:
            return {
                "success": False,
                "error": "Patient name is required"
            }
        
        # Check if patient with same phone exists
        if patient_data.phone:
            for existing in patients_db.values():
                if existing.get("phone") == patient_data.phone:
                    return {
                        "success": False,
                        "error": f"Patient with phone {patient_data.phone} already exists",
                        "existing_patient": existing
                    }
        
        new_id = max(patients_db.keys()) + 1 if patients_db else 1
        
        patient = {
            "id": new_id,
            "patient_number": PatientService.generate_patient_number(),
            "name": patient_data.name,
            "age": patient_data.age,
            "gender": patient_data.gender.value if patient_data.gender else None,
            "phone": patient_data.phone,
            "email": patient_data.email,
            "address": patient_data.address,
            "blood_group": patient_data.blood_group.value if patient_data.blood_group else None,
            "emergency_contact": patient_data.emergency_contact,
            "emergency_contact_name": patient_data.emergency_contact_name,
            "medical_history": patient_data.medical_history or [],
            "allergies": patient_data.allergies or [],
            "created_at": datetime.now(),
            "updated_at": None,
            "created_by": None,
            "total_visits": 0,
            "last_visit": None
        }
        
        patients_db[new_id] = patient
        
        return {
            "success": True,
            "patient": PatientService.get_patient_by_id(new_id),
            "message": f"Patient {patient_data.name} created successfully"
        }
    
    @staticmethod
    def update_patient(patient_id: int, update_data: PatientUpdate) -> Dict:
        """Update patient information"""
        patient = patients_db.get(patient_id)
        if not patient:
            return {
                "success": False,
                "error": f"Patient with ID {patient_id} not found"
            }
        
        # Update fields
        update_dict = update_data.dict(exclude_unset=True)
        for key, value in update_dict.items():
            if value is not None:
                if key == "gender" and isinstance(value, Gender):
                    patient[key] = value.value
                elif key == "blood_group" and isinstance(value, BloodGroup):
                    patient[key] = value.value
                else:
                    patient[key] = value
        
        patient["updated_at"] = datetime.now()
        
        return {
            "success": True,
            "patient": PatientService.get_patient_by_id(patient_id),
            "message": "Patient updated successfully"
        }
    
    @staticmethod
    def delete_patient(patient_id: int) -> bool:
        """Delete a patient"""
        if patient_id not in patients_db:
            return False
        
        # Check if patient has active consultations
        active = any(
            c for c in consultations_db.values()
            if c.get("patient_id") == patient_id and
            c.get("status") in ["waiting", "in_progress"]
        )
        
        if active:
            return False  # Cannot delete patient with active consultations
        
        del patients_db[patient_id]
        return True
    
    @staticmethod
    def get_prescriptions(search: Optional[str] = None, patient_id: Optional[int] = None) -> List[Dict]:
        """Get prescriptions with optional filters"""
        prescriptions = list(prescriptions_db.values())
        
        if patient_id:
            prescriptions = [p for p in prescriptions if p.get("patient_id") == patient_id]
        
        if search:
            search = search.lower()
            prescriptions = [
                p for p in prescriptions
                if search in p.get("medication", "").lower()
            ]
        
        # Enhance with patient and doctor names
        enhanced = []
        for p in prescriptions:
            patient = patients_db.get(p.get("patient_id"))
            from src.models.doctor import DoctorModel
            doctor = DoctorModel.get_doctor_by_id(p.get("doctor_id"))
            
            enhanced.append({
                **p,
                "patient_name": patient.get("name") if patient else "Unknown",
                "doctor_name": doctor.get("name") if doctor else "Unknown",
                "status": "Filled" if p.get("is_filled") else "Pending"
            })
        
        return enhanced
    
    @staticmethod
    def create_prescription(prescription_data: PrescriptionCreate) -> Dict:
        """Create a new prescription"""
        global next_prescription_id
        
        # Validate patient exists
        if prescription_data.patient_id not in patients_db:
            return {
                "success": False,
                "error": f"Patient with ID {prescription_data.patient_id} not found"
            }
        
        # Validate doctor exists
        from src.models.doctor import DoctorModel
        doctor = DoctorModel.get_doctor_by_id(prescription_data.doctor_id)
        if not doctor:
            return {
                "success": False,
                "error": f"Doctor with ID {prescription_data.doctor_id} not found"
            }
        
        new_id = next_prescription_id
        next_prescription_id += 1
        
        prescription = {
            "id": new_id,
            "prescription_number": PatientService.generate_prescription_number(),
            "patient_id": prescription_data.patient_id,
            "doctor_id": prescription_data.doctor_id,
            "consultation_id": prescription_data.consultation_id,
            "medication": prescription_data.medication,
            "instructions": prescription_data.instructions,
            "dosage": prescription_data.dosage,
            "duration": prescription_data.duration,
            "quantity": prescription_data.quantity,
            "refills": prescription_data.refills,
            "notes": prescription_data.notes,
            "created_at": datetime.now(),
            "updated_at": None,
            "filled_at": None,
            "filled_by": None,
            "is_filled": False
        }
        
        prescriptions_db[new_id] = prescription
        
        # Create notification
        patient = patients_db[prescription_data.patient_id]
        from src.services.receptionist_service import ReceptionistService
        ReceptionistService.create_notification(
            user_id=prescription_data.doctor_id,
            user_name=doctor.get("name"),
            message=f"Prescription created for {patient.get('name')}",
            type=NotificationType.SUCCESS,
            role_target="pharmacy"
        )
        
        return {
            "success": True,
            "prescription": prescription,
            "message": "Prescription created successfully"
        }
    
    @staticmethod
    def get_department_stats(department: str) -> Dict:
        """Get statistics for a specific department"""
        dept_consultations = [
            c for c in consultations_db.values()
            if c.get("department") == department
        ]
        
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        today_consultations = [
            c for c in dept_consultations
            if c.get("created_at", datetime.min) >= today_start
        ]
        
        waiting = len([c for c in dept_consultations if c.get("status") == "waiting"])
        in_progress = len([c for c in dept_consultations if c.get("status") == "in_progress"])
        completed_today = len([c for c in today_consultations if c.get("status") == "treated"])
        
        # Calculate average wait time
        wait_times = []
        for c in dept_consultations:
            if c.get("started_at") and c.get("created_at"):
                wait_time = (c["started_at"] - c["created_at"]).seconds // 60
                if wait_time > 0:
                    wait_times.append(wait_time)
        
        avg_wait_time = sum(wait_times) // len(wait_times) if wait_times else 0
        
        # Get doctors in department
        from src.models.doctor import DoctorModel
        doctors = DoctorModel.get_doctors_by_department(department)
        
        return {
            "success": True,
            "department": department,
            "statistics": {
                "total_patients_today": len(today_consultations),
                "waiting": waiting,
                "in_progress": in_progress,
                "completed_today": completed_today,
                "average_wait_time": avg_wait_time,
                "doctors_available": len(doctors),
                "doctors": doctors
            }
        }
    
    @staticmethod
    def get_daily_stats(days: int = 7) -> List[Dict]:
        """Get daily statistics for the last N days"""
        stats = []
        today = datetime.now().date()
        
        for i in range(days):
            date = today - timedelta(days=i)
            next_date = date + timedelta(days=1)
            
            # Get consultations for this day
            day_consultations = [
                c for c in consultations_db.values()
                if date <= c.get("created_at", datetime.min).date() < next_date
            ]
            
            # Get patients registered this day
            new_patients = [
                p for p in patients_db.values()
                if date <= p.get("created_at", datetime.min).date() < next_date
            ]
            
            # Get returning patients (those with previous visits)
            returning = []
            for p in day_consultations:
                patient_visits = [
                    c for c in consultations_db.values()
                    if c.get("patient_id") == p.get("patient_id") and
                    c.get("created_at", datetime.min).date() < date
                ]
                if patient_visits:
                    returning.append(p)
            
            # Calculate average wait time
            wait_times = []
            for c in day_consultations:
                if c.get("started_at") and c.get("created_at"):
                    wait_time = (c["started_at"] - c["created_at"]).seconds // 60
                    if wait_time > 0:
                        wait_times.append(wait_time)
            
            avg_wait_time = sum(wait_times) // len(wait_times) if wait_times else 0
            
            # Calculate satisfaction score
            ratings = [
                c.get("satisfaction_rating") for c in day_consultations
                if c.get("satisfaction_rating")
            ]
            satisfaction_score = sum(ratings) / len(ratings) if ratings else 0
            
            stats.append({
                "date": date.isoformat(),
                "total_patients": len(day_consultations),
                "new_patients": len(new_patients),
                "returning_patients": len(returning),
                "average_wait_time": avg_wait_time,
                "satisfaction_score": round(satisfaction_score, 2)
            })
        
        return stats
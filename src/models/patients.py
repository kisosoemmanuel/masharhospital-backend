from datetime import datetime, timedelta
from typing import Optional, List, Dict
from pydantic import BaseModel, Field
from enum import Enum

class PatientStatus(str, Enum):
    WAITING = "waiting"
    IN_PROGRESS = "in_progress"
    TREATED = "treated"

class PatientPriority(int, Enum):
    NORMAL = 1
    URGENT = 2
    EMERGENCY = 3

class PatientBase(BaseModel):
    name: str
    age: Optional[int] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None

class PatientCreate(PatientBase):
    pass

class PatientUpdate(BaseModel):
    name: Optional[str] = None
    age: Optional[int] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None

class Patient(PatientBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

class ConsultationBase(BaseModel):
    patient_id: int
    doctor_id: int
    department: str
    condition: str
    priority: PatientPriority = PatientPriority.NORMAL

class ConsultationCreate(ConsultationBase):
    room: Optional[str] = None

class Consultation(ConsultationBase):
    id: int
    room: Optional[str] = None
    status: PatientStatus = PatientStatus.WAITING
    queue_number: Optional[int] = None
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    satisfaction_rating: Optional[int] = None
    
    class Config:
        from_attributes = True

class PrescriptionBase(BaseModel):
    patient_id: int
    doctor_id: int
    consultation_id: Optional[int] = None
    medication: str
    instructions: Optional[str] = None
    dosage: Optional[str] = None
    duration: Optional[str] = None

class Prescription(PrescriptionBase):
    id: int
    created_at: datetime
    
    class Config:
        from_attributes = True

# In-memory databases (replace with real database later)
patients_db = {
    1: {
        "id": 1,
        "name": "John Doe",
        "age": 45,
        "phone": "+254700111222",
        "email": "john@email.com",
        "address": "Nairobi",
        "created_at": datetime.now() - timedelta(days=30),
        "updated_at": None
    },
    2: {
        "id": 2,
        "name": "Mary Wanjiuru",
        "age": 32,
        "phone": "+254700111333",
        "email": "mary@email.com",
        "address": "Kiambu",
        "created_at": datetime.now() - timedelta(days=25),
        "updated_at": None
    },
    3: {
        "id": 3,
        "name": "James Otieno",
        "age": 28,
        "phone": "+254700111444",
        "email": "james@email.com",
        "address": "Kisumu",
        "created_at": datetime.now() - timedelta(days=20),
        "updated_at": None
    },
    4: {
        "id": 4,
        "name": "Faith Achieng",
        "age": 25,
        "phone": "+254700111555",
        "email": "faith@email.com",
        "address": "Mombasa",
        "created_at": datetime.now() - timedelta(days=15),
        "updated_at": None
    },
    5: {
        "id": 5,
        "name": "Peter Mwangi",
        "age": 55,
        "phone": "+254700111666",
        "email": "peter@email.com",
        "address": "Nakuru",
        "created_at": datetime.now() - timedelta(days=10),
        "updated_at": None
    }
}

consultations_db = {
    1: {
        "id": 1,
        "patient_id": 1,
        "doctor_id": 1,
        "department": "Cardiology",
        "room": "4B",
        "condition": "High Fever",
        "priority": 3,
        "status": "in_progress",
        "queue_number": 1,
        "created_at": datetime.now() - timedelta(minutes=30),
        "started_at": datetime.now() - timedelta(minutes=25),
        "completed_at": None,
        "satisfaction_rating": None
    },
    2: {
        "id": 2,
        "patient_id": 2,
        "doctor_id": 1,
        "department": "Cardiology",
        "room": "4B",
        "condition": "Headache",
        "priority": 1,
        "status": "waiting",
        "queue_number": 2,
        "created_at": datetime.now() - timedelta(minutes=20),
        "started_at": None,
        "completed_at": None,
        "satisfaction_rating": None
    },
    3: {
        "id": 3,
        "patient_id": 3,
        "doctor_id": 1,
        "department": "Cardiology",
        "room": "4B",
        "condition": "Injury",
        "priority": 2,
        "status": "waiting",
        "queue_number": 3,
        "created_at": datetime.now() - timedelta(minutes=15),
        "started_at": None,
        "completed_at": None,
        "satisfaction_rating": None
    },
    4: {
        "id": 4,
        "patient_id": 4,
        "doctor_id": 1,
        "department": "Cardiology",
        "room": "4B",
        "condition": "Malaria",
        "priority": 1,
        "status": "treated",
        "queue_number": 4,
        "created_at": datetime.now() - timedelta(hours=3),
        "started_at": datetime.now() - timedelta(hours=3),
        "completed_at": datetime.now() - timedelta(hours=2, minutes=45),
        "satisfaction_rating": 5
    },
    5: {
        "id": 5,
        "patient_id": 5,
        "doctor_id": 1,
        "department": "Cardiology",
        "room": "4B",
        "condition": "High Blood Pressure",
        "priority": 2,
        "status": "in_progress",
        "queue_number": 5,
        "created_at": datetime.now() - timedelta(minutes=45),
        "started_at": datetime.now() - timedelta(minutes=40),
        "completed_at": None,
        "satisfaction_rating": None
    }
}

prescriptions_db = {}
next_prescription_id = 1
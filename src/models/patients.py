from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean, JSON
from sqlalchemy.orm import Session, relationship
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, validator
from enum import Enum
import re

from src.database import Base
from pydantic import BaseModel, ConfigDict

# -----------------------------
# Enums (Kept for Validation)
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

class Gender(str, Enum):
    MALE = "male"
    FEMALE = "female"
    OTHER = "other"

# -----------------------------
# SQLAlchemy Models (Database)
# -----------------------------

class Patient(Base):
    __tablename__ = "patients"

    id = Column(Integer, primary_key=True, index=True)
    patient_number = Column(String, unique=True, index=True)
    name = Column(String, nullable=False)
    age = Column(Integer)
    gender = Column(String)
    phone = Column(String, index=True)
    email = Column(String)
    address = Column(String)
    blood_group = Column(String)
    emergency_contact = Column(String)
    # Store lists as JSON strings in SQLite
    medical_history = Column(JSON, default=[])
    allergies = Column(JSON, default=[])
    
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, onupdate=datetime.now)
    
    # Relationships
    consultations = relationship("Consultation", back_populates="patient")
    prescriptions = relationship("Prescription", back_populates="patient")

class Consultation(Base):
    __tablename__ = "consultations"

    id = Column(Integer, primary_key=True, index=True)
    consultation_number = Column(String, unique=True)
    patient_id = Column(Integer, ForeignKey("patients.id"))
    doctor_id = Column(Integer) # Assuming a staff/doctor table exists
    department = Column(String)
    condition = Column(String)
    priority = Column(Integer, default=1)
    status = Column(String, default="waiting")
    room = Column(String)
    
    queue_number = Column(Integer)
    created_at = Column(DateTime, default=datetime.now)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    
    # Relationships
    patient = relationship("Patient", back_populates="consultations")

class Prescription(Base):
    __tablename__ = "prescriptions"

    id = Column(Integer, primary_key=True, index=True)
    prescription_number = Column(String, unique=True)
    patient_id = Column(Integer, ForeignKey("patients.id"))
    doctor_id = Column(Integer)
    medication = Column(String)
    dosage = Column(String)
    instructions = Column(String)
    is_filled = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.now)

    # Relationships
    patient = relationship("Patient", back_populates="prescriptions")


class PatientUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    gender: Optional[str] = None
    address: Optional[str] = None
    next_of_kin: Optional[str] = None
    next_of_kin_phone: Optional[str] = None
    
    model_config = ConfigDict(from_attributes=True) 


# -----------------------------
# Pydantic Models (Schemas)
# -----------------------------

class PatientBase(BaseModel):
    name: str = Field(..., min_length=2)
    age: Optional[int] = Field(None, ge=0)
    gender: Optional[Gender] = None
    phone: str
    email: Optional[str] = None
    medical_history: List[str] = []
    allergies: List[str] = []

    @validator('phone')
    def validate_phone(cls, v):
        if not re.match(r'^\+?[0-9]{10,15}$', v):
            raise ValueError('Invalid phone format')
        return v

class PatientCreate(PatientBase):
    pass

class QuickRegistration(BaseModel):
    patient_name: str
    phone: str
    condition: str
    priority: int = 1
    department: str = "General"

# -----------------------------
# Service Helper (Data Access)
# -----------------------------

class PatientModel:
    """Utility class for Patient database operations"""
    
    @staticmethod
    def generate_patient_number(db: Session) -> str:
        """Generates P-YYYY-XXXX format"""
        year = datetime.now().year
        count = db.query(Patient).count()
        return f"P-{year}-{count + 1:04d}"

    @staticmethod
    def get_by_id(db: Session, p_id: int) -> Optional[Patient]:
        return db.query(Patient).filter(Patient.id == p_id).first()

    @staticmethod
    def get_all(db: Session) -> List[Patient]:
        return db.query(Patient).all()
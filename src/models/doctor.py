from sqlalchemy import Column, Integer, String, DateTime, Boolean
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from pydantic import BaseModel
from jose import jwt
from passlib.context import CryptContext
import os
from src.database import Base

# -----------------------------
# Configuration & Security
# -----------------------------
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-here")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
# This handles the secure hashing of passwords
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# -----------------------------
# SQLAlchemy Database Model
# -----------------------------
class DoctorTable(Base):
    __tablename__ = "doctors"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(String, unique=True, index=True)
    username = Column(String, unique=True, index=True)
    hashed_password = Column(String, nullable=False)
    name = Column(String, nullable=False)
    role = Column(String, default="doctor")
    department = Column(String)
    specialization = Column(String)
    email = Column(String)
    phone = Column(String)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login = Column(DateTime, nullable=True)
    total_patients = Column(Integer, default=0)
    average_consultation_time = Column(Integer, default=15)

# -----------------------------
# Pydantic Schemas
# -----------------------------
class DoctorLogin(BaseModel):
    username: str
    password: str

class DoctorCreate(BaseModel):
    name: str
    username: str
    password: str
    department: str = "General"
    email: Optional[str] = None
    specialization: Optional[str] = "General"
    phone: Optional[str] = None

class DoctorUpdate(BaseModel):
    name: Optional[str] = None
    department: Optional[str] = None
    specialization: Optional[str] = None
    is_active: Optional[bool] = None

# -----------------------------
# Doctor Model Logic
# -----------------------------
class DoctorModel:

    @staticmethod
    def hash_password(password: str) -> str:
        return pwd_context.hash(password)

    @staticmethod
    def verify_password(password: str, hashed: str) -> bool:
        # Prevents crashing if the password in DB isn't actually a hash
        try:
            return pwd_context.verify(password, hashed)
        except Exception:
            return False

    @staticmethod
    def authenticate(db: Session, username: str, password: str) -> Optional[DoctorTable]:
        """
        Modified to return the SQLAlchemy object itself.
        This matches the logic in your main.py.
        """
        doctor = db.query(DoctorTable).filter(
            (DoctorTable.username == username) | (DoctorTable.employee_id == username)
        ).first()

        if not doctor:
            return None
        
        if not DoctorModel.verify_password(password, doctor.hashed_password):
            return None

        # Update last login
        doctor.last_login = datetime.utcnow()
        db.commit()
        return doctor

    @staticmethod
    def create_doctor(db: Session, data: DoctorCreate) -> Dict:
        """Register a new doctor in the database."""
        existing = db.query(DoctorTable).filter(DoctorTable.username == data.username).first()
        if existing:
            return {"success": False, "error": "Username already exists"}

        count = db.query(DoctorTable).count()
        emp_id = f"D-{count + 1:03d}"

        new_doctor = DoctorTable(
            username=data.username,
            employee_id=emp_id,
            hashed_password=DoctorModel.hash_password(data.password),
            name=data.name,
            department=data.department,
            specialization=data.specialization,
            email=data.email,
            phone=data.phone
        )

        db.add(new_doctor)
        db.commit()
        db.refresh(new_doctor)
        return {"success": True, "doctor": new_doctor}

    @staticmethod
    def get_all(db: Session) -> List[DoctorTable]:
        return db.query(DoctorTable).filter(DoctorTable.is_active == True).all()
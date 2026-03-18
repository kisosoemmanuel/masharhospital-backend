from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.orm import Session
from datetime import datetime
from typing import Optional, List, Dict
from pydantic import BaseModel
from passlib.context import CryptContext
from src.database import Base

# -----------------------------
# Password Hashing
# -----------------------------
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

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
# SQLAlchemy Table Model
# -----------------------------
class Receptionist(Base):
    __tablename__ = "receptionists"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(String, unique=True, index=True)
    name = Column(String)
    phone = Column(String)
    email = Column(String, nullable=True)
    department = Column(String, default="Front Desk")
    status = Column(String, default="active")
    hashed_password = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, onupdate=datetime.utcnow)
    last_login = Column(DateTime, nullable=True)
    
    # Adding this property to match the logic used in main.py for staff roles
    @property
    def role(self):
        return "receptionist"

# -----------------------------
# Pydantic Schemas
# -----------------------------
class ReceptionistCreate(BaseModel):
    employee_id: str
    name: str
    phone: str
    email: Optional[str] = None
    department: Optional[str] = "Front Desk"
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

# -----------------------------
# Receptionist Model Logic
# -----------------------------
class ReceptionistModel:
    
    @staticmethod
    def authenticate(db: Session, employee_id: str, password: str) -> Optional[Receptionist]:
        """
        Authenticate a receptionist. 
        Returns the Receptionist object if successful to match main.py logic.
        """
        user = db.query(Receptionist).filter(Receptionist.employee_id == employee_id).first()
        
        if not user or not verify_password(password, user.hashed_password):
            return None
        
        # Update last login timestamp
        user.last_login = datetime.utcnow()
        db.commit()
        db.refresh(user)
        
        return user

    @staticmethod
    def create_receptionist(db: Session, data: ReceptionistCreate) -> Dict:
        """Create a new receptionist record."""
        existing = db.query(Receptionist).filter(Receptionist.employee_id == data.employee_id).first()
        if existing:
            return {"success": False, "error": "Employee ID already exists"}
        
        new_rec = Receptionist(
            employee_id=data.employee_id,
            name=data.name,
            phone=data.phone,
            email=data.email,
            department=data.department,
            hashed_password=hash_password(data.password)
        )
        
        db.add(new_rec)
        db.commit()
        db.refresh(new_rec)
        
        return {"success": True, "receptionist": new_rec}

    @staticmethod
    def update_receptionist(db: Session, r_id: int, data: ReceptionistUpdate) -> Optional[Receptionist]:
        """Update existing receptionist data."""
        rec = db.query(Receptionist).filter(Receptionist.id == r_id).first()
        if not rec:
            return None
            
        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(rec, key, value)
                
        db.commit()
        db.refresh(rec)
        return rec

    @staticmethod
    def get_all(db: Session) -> List[Receptionist]:
        return db.query(Receptionist).all()

    @staticmethod
    def get_by_id(db: Session, r_id: int) -> Optional[Receptionist]:
        return db.query(Receptionist).filter(Receptionist.id == r_id).first()

    @staticmethod
    def delete_receptionist(db: Session, r_id: int) -> bool:
        """Soft delete by setting status to inactive."""
        rec = db.query(Receptionist).filter(Receptionist.id == r_id).first()
        if rec:
            rec.status = "inactive"
            db.commit()
            return True
        return False
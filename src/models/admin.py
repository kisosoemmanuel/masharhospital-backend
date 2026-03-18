# src/models/admin.py

from datetime import datetime
from typing import Optional, List, Dict
from pydantic import BaseModel, ConfigDict
from enum import Enum
from passlib.context import CryptContext
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text, func, desc
from sqlalchemy.orm import Session
from sqlalchemy.types import Enum as SAEnum
from fastapi import Depends
from src.database import Base, get_db

# -----------------------------
# Password Hashing
# -----------------------------
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=12)

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
# SQLAlchemy Models
# -------------------------------------------------
class Staff(Base):
    __tablename__ = "staff"
    
    id = Column(Integer, primary_key=True, index=True)
    staff_id = Column(String(10), unique=True, index=True, nullable=False)
    name = Column(String(100), nullable=False)
    role = Column(SAEnum(StaffRole, values_callable=lambda cls: [e.value for e in StaffRole]), nullable=False, index=True)
    phone = Column(String(20), nullable=False, index=True)
    email = Column(String(100), unique=True, index=True)
    department = Column(String(50))
    specialization = Column(String(100))
    status = Column(SAEnum(StaffStatus, values_callable=lambda cls: [e.value for e in StaffStatus]), default=StaffStatus.ACTIVE, index=True)
    hashed_password = Column(String(255), nullable=False)
    joining_date = Column(DateTime, default=func.now())
    last_login = Column(DateTime)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

class Bed(Base):
    __tablename__ = "beds"
    id = Column(Integer, primary_key=True, index=True)
    bed_number = Column(String(10), unique=True, nullable=False)
    department = Column(String(50), nullable=False)
    ward = Column(String(50), nullable=False)
    is_occupied = Column(Boolean, default=False)
    patient_id = Column(Integer, nullable=True)
    assigned_at = Column(DateTime, nullable=True)

class InventoryItem(Base):
    __tablename__ = "inventory_items"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, index=True)
    category = Column(String(50), nullable=False)
    quantity = Column(Integer, default=0)
    unit = Column(String(20), nullable=False)
    reorder_level = Column(Integer, default=0)
    last_restocked = Column(DateTime, default=func.now())
    expiry_date = Column(DateTime, nullable=True)

class ActivityLog(Base):
    __tablename__ = "activity_logs"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("staff.id"), nullable=True)
    user_name = Column(String(100), nullable=False)
    action = Column(String(50), nullable=False)
    details = Column(Text)
    timestamp = Column(DateTime, default=func.now())
    role = Column(String(20), nullable=False)

# -------------------------------------------------
# Pydantic Schemas
# -------------------------------------------------
class StaffLogin(BaseModel):
    staff_id: str
    password: str
    role: Optional[str] = None 

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

class StaffSchema(StaffBase):
    id: int
    status: StaffStatus = StaffStatus.ACTIVE
    joining_date: datetime
    last_login: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)

# -------------------------------------------------
# AdminModel (Logic)
# -------------------------------------------------
class AdminModel:
    @staticmethod
    def authenticate(db: Session, staff_id: str, password: str) -> Optional[Staff]:
        staff = db.query(Staff).filter(Staff.staff_id == staff_id).first()
        if not staff or not verify_password(password, staff.hashed_password):
            return None
        try:
            staff.last_login = datetime.now()
            db.commit()
            db.refresh(staff)
        except Exception as e:
            db.rollback()
            print(f"Warning: Could not update last_login: {e}")
        return staff

    @staticmethod
    def get_by_staff_id(db: Session, staff_id: str) -> Optional[Staff]:
        """
        UPDATED: Checks staff_id string (DOC001) first, then integer primary key.
        This fixes the 404 errors when the frontend sends simple IDs.
        """
        # Try finding by staff_id field
        staff = db.query(Staff).filter(Staff.staff_id == str(staff_id)).first()
        
        # Fallback to primary key if it's a numeric string
        if not staff and str(staff_id).isdigit():
            staff = db.query(Staff).filter(Staff.id == int(staff_id)).first()
            
        return staff

    @staticmethod
    def get_all_staff(role: Optional[str] = None, department: Optional[str] = None, db: Session = Depends(get_db)) -> List[Staff]:
        query = db.query(Staff)
        if role: query = query.filter(Staff.role == role)
        if department: query = query.filter(Staff.department == department)
        return query.all()

    @staticmethod
    def create_staff(data: StaffCreate, db: Session) -> Staff:
        if db.query(Staff).filter(Staff.staff_id == data.staff_id).first():
            raise ValueError(f"Staff ID {data.staff_id} already exists")
        
        staff = Staff(
            staff_id=data.staff_id, name=data.name, role=data.role,
            phone=data.phone, email=data.email, department=data.department,
            specialization=data.specialization,
            hashed_password=hash_password(data.password),
            joining_date=data.joining_date or datetime.now()
        )
        db.add(staff); db.commit(); db.refresh(staff)
        AdminModel.log_activity(staff.id, staff.name, "CREATE_STAFF", f"Account created for {staff.name}", "admin", db)
        return staff

    @staticmethod
    def update_staff(staff_id: int, update: StaffUpdate, db: Session) -> Optional[Staff]:
        staff = db.query(Staff).filter(Staff.id == staff_id).first()
        if not staff: return None
        for key, value in update.model_dump(exclude_unset=True).items():
            setattr(staff, key, value)
        db.commit(); db.refresh(staff)
        return staff

    @staticmethod
    def delete_staff(staff_id: int, db: Session) -> bool:
        staff = db.query(Staff).filter(Staff.id == staff_id).first()
        if not staff: return False
        staff.status = StaffStatus.INACTIVE
        db.commit()
        return True

    @staticmethod
    def get_staff_statistics(db: Session) -> Dict:
        return {
            "total": db.query(Staff).count(),
            "active": db.query(Staff).filter(Staff.status == StaffStatus.ACTIVE).count(),
            "by_role": {role.value: db.query(Staff).filter(Staff.role == role).count() for role in StaffRole}
        }

    # Bed & Inventory Management
    @staticmethod
    def get_bed_status(db: Session) -> Dict:
        total = db.query(Bed).count()
        occupied = db.query(Bed).filter(Bed.is_occupied == True).count()
        return {
            "total_beds": total, "occupied_beds": occupied,
            "available_beds": total - occupied,
            "occupancy_rate": round((occupied / total * 100), 1) if total > 0 else 0
        }

    @staticmethod
    def get_inventory_status(db: Session) -> Dict:
        total = db.query(InventoryItem).count()
        low_stock = db.query(InventoryItem).filter(InventoryItem.quantity <= InventoryItem.reorder_level).all()
        return {
            "total_items": total, "low_stock_count": len(low_stock),
            "low_stock_items": [{"id": i.id, "name": i.name, "qty": i.quantity} for i in low_stock]
        }

    @staticmethod
    def log_activity(user_id: Optional[int], user_name: str, action: str, details: str, role: str, db: Session):
        log = ActivityLog(user_id=user_id, user_name=user_name, action=action, details=details, role=role)
        db.add(log); db.commit()

    @staticmethod
    def get_activity_logs(limit: int = 50, db: Session = Depends(get_db)) -> List[ActivityLog]:
        return db.query(ActivityLog).order_by(desc(ActivityLog.timestamp)).limit(limit).all()

# -------------------------------------------------
# Data Seeding
# -------------------------------------------------
def seed_admin_data(db: Session):
    if not db.query(Staff).filter(Staff.staff_id == "A001").first():
        admin = Staff(
            staff_id="A001", name="System Admin", role=StaffRole.ADMIN,
            phone="+254700000000", email="admin@mashar.com",
            hashed_password=hash_password("admin123")
        )
        db.add(admin); db.commit()
    
    if db.query(Bed).count() == 0:
        for i in range(1, 6):
            db.add(Bed(bed_number=f"B{i:02}", department="General", ward="Ward 1"))
        db.commit()
    print("✅ Database seeded successfully.")

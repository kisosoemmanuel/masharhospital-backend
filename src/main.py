from fastapi import FastAPI, Depends, HTTPException, status, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer
from contextlib import asynccontextmanager
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
import os
import json
import traceback
from dotenv import load_dotenv
from jose import JWTError, jwt
from pydantic import BaseModel, ValidationError

# Database Imports
from sqlalchemy.orm import Session
from sqlalchemy import desc
from src.database import SessionLocal, engine, Base

# Models & Services
from src.models.doctor import DoctorModel, DoctorLogin, DoctorCreate
from src.models.patients import (
    Patient, PatientCreate, PatientUpdate, QuickRegistration,
    Prescription, Consultation, PatientModel
)
from src.models.admin import StaffCreate, StaffUpdate, AdminModel, StaffLogin, Staff, StaffRole
from src.models.receptionist import ReceptionistCreate, ReceptionistUpdate, ReceptionistModel, ReceptionistLogin
from src.services.queue_manager import QueueManager
from src.services.patient_service import PatientService
from src.services.admin_service import AdminService
from src.services.receptionist_service import ReceptionistService

# For export
from fastapi.responses import Response, JSONResponse
from io import BytesIO
import openpyxl
from openpyxl.styles import Font, Alignment, PatternFill
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.graphics.shapes import Drawing
from reportlab.graphics.charts.barcharts import VerticalBarChart
from collections import Counter

load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY", "change-this-secret-in-production")
ALGORITHM = "HS256"

# ✅ FIX 1: Increased token expiry from 30 min to 8 hours so doctors don't get
# logged out mid-shift. Change back to 30 if you want stricter security.
ACCESS_TOKEN_EXPIRE_MINUTES = 480  # 8 hours

# --------------------------------------------------
# DATABASE & LIFESPAN
# --------------------------------------------------

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events with Database context"""
    from src.database import init_db
    print("🚀 Starting Mashar Hospital API...")
    try:
        init_db()
        print("✅ Database ready. API live!")
    except Exception as e:
        print(f"❌ Database initialization failed: {e}")
        traceback.print_exc()
    yield
    print("🛑 Shutting down Mashar Hospital API...")

tags_metadata = [
    {"name": "auth", "description": "Login and authentication"},
    {"name": "patients", "description": "Patient management"},
    {"name": "queue", "description": "Queue operations"},
    {"name": "doctors", "description": "Doctor profile and management"},
    {"name": "admin", "description": "Admin functions"},
    {"name": "receptionist", "description": "Receptionist functions"},
    {"name": "health", "description": "Health checks"}
]

app = FastAPI(
    title="Mashar Hospital Management API v2.1",
    description="Full-featured hospital backend with RBAC, queues, staff, beds & inventory",
    version="2.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_tags=tags_metadata
)

# --------------------------------------------------
# MIDDLEWARE & SECURITY
# --------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/login", auto_error=False)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire, "iat": datetime.utcnow()})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

# ✅ FIX 2: Normalize role to lowercase so "Doctor", "DOCTOR", "doctor" all match
def normalize_role(role_value: Any) -> str:
    """Convert any role representation to a clean lowercase string."""
    if role_value is None:
        return ""
    raw = role_value.value if hasattr(role_value, 'value') else str(role_value)
    # Handle cases like "StaffRole.doctor" -> "doctor"
    if "." in raw:
        raw = raw.split(".")[-1]
    return raw.strip().lower()

async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    if not token:
        raise HTTPException(status_code=401, detail="Authentication required")
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        role = payload.get("role")
        if not username or not role:
            raise HTTPException(status_code=401, detail="Invalid token claims")
        # Normalize role from token too
        normalized_role = normalize_role(role)
        print(f"🔐 Token decoded: user={username}, role={normalized_role}")
        return {"username": username, "role": normalized_role}
    except JWTError as e:
        print(f"JWT Error: {e}")
        raise HTTPException(status_code=401, detail="Invalid token")

def require_role(required_roles: List[str]):
    # ✅ FIX 3: Normalize required_roles to lowercase for consistent comparison
    normalized_required = [r.lower() for r in required_roles]
    async def role_checker(current_user=Depends(get_current_user)):
        if current_user["role"] not in normalized_required:
            print(f"⛔ Role mismatch: user has '{current_user['role']}', needs one of {normalized_required}")
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return current_user
    return role_checker

# --------------------------------------------------
# LOGIN MODELS
# --------------------------------------------------
class UniversalLoginRequest(BaseModel):
    username: Optional[str] = None
    staff_id: Optional[str] = None
    employee_id: Optional[str] = None
    password: str
    role: Optional[str] = None

# --------------------------------------------------
# AUTHENTICATION ROUTES
# --------------------------------------------------
@app.post("/api/login", tags=["auth"])
@app.post("/api/admin/login", tags=["auth"])
@app.post("/api/doctors/login", tags=["auth"])
@app.post("/api/receptionist/login", tags=["auth"])
async def universal_login(
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Universal login endpoint that handles all role types.
    Accepts flat JSON with username, staff_id, or employee_id plus password.
    """
    try:
        body = await request.json()
        print(f"DEBUG: Login attempt payload: {body}")

        try:
            login_data = UniversalLoginRequest(**body)
        except ValidationError:
            flat_body = {}
            for key, value in body.items():
                if isinstance(value, dict):
                    flat_body.update(value)
                else:
                    flat_body[key] = value
            login_data = UniversalLoginRequest(**flat_body)

        identifier = login_data.username or login_data.staff_id or login_data.employee_id
        if not identifier or not login_data.password:
            return JSONResponse(
                status_code=400,
                content={"success": False, "detail": "Username and password required"}
            )

        user = AdminModel.authenticate(db, staff_id=str(identifier), password=str(login_data.password))

        if not user:
            return JSONResponse(
                status_code=401,
                content={"success": False, "detail": "Invalid credentials"}
            )

        # ✅ FIX 4: Always store role as normalized lowercase in the token
        role_val = normalize_role(user.role)
        token = create_access_token({"sub": str(user.staff_id), "role": role_val})

        print(f"✅ Login success: {user.staff_id}, role stored in token: '{role_val}'")

        return {
            "success": True,
            "access_token": token,
            "token_type": "bearer",
            "role": role_val,
            "username": user.name,
            "staff_id": user.staff_id,
            "user": {
                "id": user.id,
                "name": user.name,
                "staff_id": user.staff_id,
                "role": role_val,
            }
        }

    except Exception as e:
        print("ERROR in login:", traceback.format_exc())
        return JSONResponse(
            status_code=400,
            content={"success": False, "detail": "Invalid request format"}
        )

# --------------------------------------------------
# DOCTOR DASHBOARD SUPPORT ROUTES
# --------------------------------------------------
@app.get("/api/doctors/patients/{patient_id}/consultations", tags=["doctors"])
async def get_patient_consultations_for_doctor(
    patient_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_role(["doctor", "admin"]))
):
    """Return all consultations for a patient (doctor or admin accessible)."""
    consultations = db.query(Consultation).filter(Consultation.patient_id == patient_id).all()
    return {
        "success": True,
        "data": [
            {
                "id": c.id,
                "condition": c.condition,
                "status": c.status,
                "created_at": c.created_at.isoformat() if c.created_at else None,
                "department": c.department,
                "priority": c.priority,
                "doctor_id": c.doctor_id,
            }
            for c in consultations
        ]
    }

@app.get("/api/doctors/current", tags=["doctors"])
async def get_current_doctor(db: Session = Depends(get_db)):
    doctor = db.query(Staff).filter(Staff.role == StaffRole.DOCTOR).first()
    if not doctor:
        return {"success": False, "message": "No active doctor found", "data": None}
    return {"success": True, "data": doctor}

@app.get("/api/doctors/{doctor_id}", tags=["doctors"])
async def get_doctor_profile(doctor_id: str, db: Session = Depends(get_db)):
    doctor = AdminModel.get_by_staff_id(db, doctor_id)
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor not found")
    return {"success": True, "data": doctor}

@app.get("/api/queue/current", tags=["queue"])
async def get_current_consultation(doctor_id: str, db: Session = Depends(get_db)):
    result = QueueManager.get_current_patient(db, doctor_id)
    return {"success": True, "data": result}

@app.get("/api/queue/waiting", tags=["queue"])
async def get_waiting_patients_list(doctor_id: str, db: Session = Depends(get_db)):
    patients = QueueManager.get_waiting_by_doctor(db, doctor_id)
    return {"success": True, "data": patients}

@app.put("/api/consultations/{consultation_id}/status", tags=["queue"])
async def update_consultation_status(
    consultation_id: int,
    status: str,
    db: Session = Depends(get_db),
    current_user=Depends(require_role(["doctor", "admin"]))
):
    consultation = db.query(Consultation).filter(Consultation.id == consultation_id).first()
    if not consultation:
        raise HTTPException(status_code=404, detail="Consultation not found")
    consultation.status = status
    if status == "treated":
        consultation.completed_at = datetime.utcnow()
    db.commit()
    return {"success": True, "message": f"Consultation status updated to {status}"}

# ✅ FIX 5: Added a /api/debug/role endpoint so you can test what role your token has
@app.get("/api/debug/role", tags=["debug"])
async def debug_role(current_user=Depends(get_current_user)):
    """Call this from the browser console to check your token's role."""
    return {
        "username": current_user["username"],
        "role": current_user["role"],
        "message": f"Your token identifies you as role='{current_user['role']}'"
    }

@app.get("/api/debug/token", tags=["debug"])
async def debug_token(current_user=Depends(require_role(["doctor", "admin"]))):
    return {"user": current_user}

# --------------------------------------------------
# PRESCRIPTION ROUTES
# --------------------------------------------------
@app.get("/api/prescriptions", tags=["patients"])
async def list_prescriptions(patient_id: Optional[int] = None, db: Session = Depends(get_db)):
    query = db.query(Prescription)
    if patient_id:
        query = query.filter(Prescription.patient_id == patient_id)
    results = query.order_by(desc(Prescription.created_at)).all()
    return {"success": True, "data": results}

@app.post("/api/prescriptions", tags=["patients"])
async def create_prescription(data: Dict[str, Any], db: Session = Depends(get_db)):
    try:
        new_presc = Prescription(
            patient_id=data.get("patient_id"),
            doctor_id=data.get("doctor_id"),
            medication=data.get("medication"), 
            dosage=data.get("dosage"),
            diagnosis=data.get("diagnosis"), 
            instructions=data.get("instructions"),
            prescription_number=f"PRE-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        )
        db.add(new_presc)
        db.commit()
        db.refresh(new_presc)
        return {"success": True, "data": new_presc}
    except Exception as e:
        db.rollback()
        # This will now show you if there's any remaining database mismatch
        raise HTTPException(status_code=400, detail=str(e))

# --------------------------------------------------
# QUEUE ROUTES
# --------------------------------------------------
@app.get("/api/queue/status", tags=["queue"])
async def get_queue_status(db: Session = Depends(get_db)):
    stats = QueueManager.get_queue_stats(db)
    return {"success": True, "data": stats}

@app.post("/api/queue/register", tags=["queue"])
async def register_patient_queue(
    patient_id: int,
    department: str = "General",
    condition: str = None,
    priority: int = 1,
    doctor_id: str = "DOC001",
    db: Session = Depends(get_db)
):
    result = QueueManager.add_to_queue(db, patient_id, department, doctor_id, priority, condition)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result.get("error"))
    return {"success": True, **result}

@app.post("/api/queue/next/{doctor_id}", tags=["queue"])
async def call_next_patient(doctor_id: str, db: Session = Depends(get_db)):
    result = QueueManager.call_next_patient(db, doctor_id)
    if not result.get("success"):
        raise HTTPException(status_code=404, detail=result.get("error", "No patients in queue"))
    return result

# --------------------------------------------------
# PATIENT ROUTES
# --------------------------------------------------
@app.get("/api/patients", tags=["patients"])
async def list_patients(search: Optional[str] = None, db: Session = Depends(get_db)):
    patients = PatientService.get_patients(db, search=search)
    return {"success": True, "data": patients, "count": len(patients)}

@app.post("/api/patients", tags=["patients"])
async def create_patient(patient: PatientCreate, db: Session = Depends(get_db)):
    new_patient = PatientService.create_patient(db, patient)
    return {"success": True, "data": new_patient}

@app.get("/api/patients/{patient_id}", tags=["patients"])
async def get_patient(patient_id: int, db: Session = Depends(get_db)):
    patient = PatientService.get_patient_by_id(db, patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    return {"success": True, "data": patient}

@app.get("/api/patients/search/{query}", tags=["patients"])
async def search_patients(query: str, db: Session = Depends(get_db)):
    patients = PatientService.get_patients(db, search=query)
    return {"success": True, "data": patients, "count": len(patients)}

# --------------------------------------------------
# ADMIN ROUTES
# --------------------------------------------------
@app.get("/api/admin/dashboard", tags=["admin"])
async def admin_dashboard(
    current_user=Depends(require_role(["admin"])),
    db: Session = Depends(get_db)
):
    stats = AdminService.get_dashboard_stats(db)
    return {"success": True, "data": stats}

@app.get("/api/admin/staff", tags=["admin"])
async def get_all_staff_list(
    role: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user=Depends(require_role(["admin"]))
):
    staff_members = AdminModel.get_all_staff(role=role, db=db)
    return {"success": True, "data": staff_members or []}

@app.post("/api/admin/staff", tags=["admin"])
async def add_new_staff(
    staff_data: StaffCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_role(["admin"]))
):
    try:
        new_staff = AdminModel.create_staff(staff_data, db)
        return {"success": True, "data": new_staff}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.delete("/api/admin/staff/{staff_id}", tags=["admin"])
async def remove_staff(
    staff_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_role(["admin"]))
):
    success = AdminModel.delete_staff(staff_id, db)
    if not success:
        raise HTTPException(status_code=404, detail="Staff member not found")
    return {"success": True, "message": "Staff deactivated"}

@app.get("/api/admin/consultations", tags=["admin"])
async def get_filtered_consultations(
    department: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user=Depends(require_role(["admin"]))
):
    query = db.query(Consultation).join(Patient, Consultation.patient_id == Patient.id)
    if department:
        query = query.filter(Consultation.department == department)
    if status:
        query = query.filter(Consultation.status == status)
    if from_date:
        from_dt = datetime.fromisoformat(from_date)
        query = query.filter(Consultation.created_at >= from_dt)
    if to_date:
        to_dt = datetime.fromisoformat(to_date) + timedelta(days=1)
        query = query.filter(Consultation.created_at < to_dt)

    consultations = query.all()
    records = []
    for c in consultations:
        patient = db.query(Patient).filter(Patient.id == c.patient_id).first()
        doctor = db.query(Staff).filter(Staff.staff_id == c.doctor_id).first() if c.doctor_id else None
        records.append({
            "id": c.id,
            "patient_name": patient.name if patient else "Unknown",
            "doctor_name": doctor.name if doctor else "Unknown",
            "department": c.department,
            "created_at": c.created_at.isoformat() if c.created_at else None,
            "status": c.status,
            "condition": c.condition,
            "priority": c.priority,
        })

    total_patients = db.query(Patient).count()
    total_consultations = len(consultations)
    wait_times = []
    for c in consultations:
        if c.started_at and c.created_at:
            wait = (c.started_at - c.created_at).seconds // 60
            if wait > 0:
                wait_times.append(wait)
    avg_wait_time = sum(wait_times) // len(wait_times) if wait_times else 0
    treated_today = db.query(Consultation).filter(
        Consultation.status == "treated",
        Consultation.completed_at >= datetime.now().replace(hour=0, minute=0, second=0)
    ).count()

    return {
        "records": records,
        "stats": {
            "totalPatients": total_patients,
            "totalConsultations": total_consultations,
            "avgWaitTime": avg_wait_time,
            "treatedToday": treated_today,
        }
    }

@app.options("/api/admin/reports/export", tags=["admin"])
async def export_report_options():
    return Response(status_code=200, headers={
        "Access-Control-Allow-Origin": "http://localhost:3000",
        "Access-Control-Allow-Methods": "GET, OPTIONS",
        "Access-Control-Allow-Headers": "Authorization, Content-Type",
        "Access-Control-Allow-Credentials": "true",
        "Access-Control-Max-Age": "86400",
    })

@app.get("/api/admin/reports/export", tags=["admin"])
async def export_report(
    format: str = "pdf",
    department: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    status: Optional[str] = None,
    include_charts: bool = False,
    db: Session = Depends(get_db),
    current_user=Depends(require_role(["admin"]))
):
    try:
        file_content, media_type, filename = await AdminService.generate_report(
            format, department, from_date, to_date, status, include_charts, db
        )
        return Response(
            content=file_content,
            media_type=media_type,
            headers={
                "Content-Disposition": f"attachment; filename={filename}",
                "Access-Control-Allow-Origin": "http://localhost:3000",
                "Access-Control-Allow-Credentials": "true",
                "Access-Control-Expose-Headers": "Content-Disposition",
            }
        )
    except Exception as e:
        print("ERROR in export_report:", traceback.format_exc())
        return JSONResponse(status_code=500, content={"success": False, "detail": str(e)},
            headers={"Access-Control-Allow-Origin": "http://localhost:3000", "Access-Control-Allow-Credentials": "true"})

@app.options("/api/admin/personnel/export", tags=["admin"])
async def personnel_export_options():
    return Response(status_code=200, headers={
        "Access-Control-Allow-Origin": "http://localhost:3000",
        "Access-Control-Allow-Methods": "GET, OPTIONS",
        "Access-Control-Allow-Headers": "Authorization, Content-Type",
        "Access-Control-Allow-Credentials": "true",
        "Access-Control-Max-Age": "86400",
    })

@app.get("/api/admin/personnel/export", tags=["admin"])
async def export_personnel_report(
    format: str = "pdf",
    include_charts: bool = False,
    db: Session = Depends(get_db),
    current_user=Depends(require_role(["admin"]))
):
    try:
        file_content, media_type, filename = await AdminService.generate_personnel_report(format, db, include_charts)
        return Response(
            content=file_content,
            media_type=media_type,
            headers={
                "Content-Disposition": f"attachment; filename={filename}",
                "Access-Control-Allow-Origin": "http://localhost:3000",
                "Access-Control-Allow-Credentials": "true",
                "Access-Control-Expose-Headers": "Content-Disposition",
            }
        )
    except Exception as e:
        print("ERROR in personnel export:", traceback.format_exc())
        return JSONResponse(status_code=500, content={"success": False, "detail": str(e)},
            headers={"Access-Control-Allow-Origin": "http://localhost:3000", "Access-Control-Allow-Credentials": "true"})

# --------------------------------------------------
# RECEPTIONIST ROUTES
# --------------------------------------------------
@app.get("/api/receptionist/dashboard", tags=["receptionist"])
async def get_receptionist_dashboard(db: Session = Depends(get_db)):
    result = ReceptionistService.get_dashboard_stats(db)
    return {"success": True, "data": result}

@app.get("/api/receptionist/queue", tags=["receptionist"])
async def get_receptionist_queue(db: Session = Depends(get_db)):
    queue_data = (
        db.query(Consultation, Patient)
        .join(Patient, Consultation.patient_id == Patient.id)
        .filter(Consultation.status == "waiting")
        .all()
    )
    return {
        "success": True,
        "data": [
            {
                "id": c.id,
                "name": p.name,
                "condition": c.condition,
                "priority": c.priority,
                "status": c.status,
                "arrival_time": c.created_at.strftime("%H:%M") if c.created_at else "--:--"
            } for c, p in queue_data
        ]
    }

@app.post("/api/receptionist/patients/quick", tags=["receptionist"])
async def quick_register_patient(data: QuickRegistration, db: Session = Depends(get_db)):
    try:
        p_no = PatientModel.generate_patient_number(db)
        new_patient = Patient(name=data.patient_name, phone=data.phone, patient_number=p_no)
        db.add(new_patient)
        db.flush()
        new_consultation = Consultation(
            patient_id=new_patient.id,
            condition=data.condition,
            priority=data.priority,
            department=data.department,
            status="waiting",
            consultation_number=f"C-{datetime.now().strftime('%y%m%d%H%M%S')}"
        )
        db.add(new_consultation)
        db.commit()
        return {"success": True}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

# --------------------------------------------------
# NOTIFICATIONS ROUTE
# --------------------------------------------------
@app.get("/api/notifications", tags=["notifications"])
async def get_notifications(db: Session = Depends(get_db)):
    return {
        "success": True,
        "data": [
            {
                "id": 1,
                "title": "System Online",
                "message": "Welcome to Mashar Hospital Management System",
                "type": "info",
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M")
            }
        ]
    }

# --------------------------------------------------
# HEALTH & SYSTEM
# --------------------------------------------------
@app.get("/", tags=["health"])
async def root():
    return {"message": "Mashar Hospital API v2.1", "docs": "/docs", "health": "/api/health"}

@app.get("/api/health", tags=["health"])
async def health_check(db: Session = Depends(get_db)):
    stats = QueueManager.get_queue_stats(db)
    return {"success": True, "status": "healthy", "version": "2.1.0", "queue": stats}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.main:app", host="0.0.0.0", port=8000, reload=True) 


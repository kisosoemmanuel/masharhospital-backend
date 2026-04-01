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
from pydantic import BaseModel, ValidationError, Field
import httpx

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
from src.models.admin import StaffCreate, StaffUpdate, AdminModel, StaffLogin, Staff, StaffRole, ActivityLog
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
    {"name": "notifications", "description": "Real-time notifications"},
    {"name": "health", "description": "Health checks"},
]

app = FastAPI(
    title="Mashar Hospital Management API v2.1",
    description="Full-featured hospital backend with RBAC, queues, staff, beds & inventory",
    version="2.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_tags=tags_metadata,
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

def normalize_role(role_value: Any) -> str:
    if role_value is None:
        return ""
    raw = role_value.value if hasattr(role_value, "value") else str(role_value)
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
        normalized_role = normalize_role(role)
        print(f"🔐 Token decoded: user={username}, role={normalized_role}")
        return {"username": username, "role": normalized_role}
    except JWTError as e:
        print(f"JWT Error: {e}")
        raise HTTPException(status_code=401, detail="Invalid token")

def require_role(required_roles: List[str]):
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
async def universal_login(request: Request, db: Session = Depends(get_db)):
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
                content={"success": False, "detail": "Username and password required"},
            )

        user = AdminModel.authenticate(db, staff_id=str(identifier), password=str(login_data.password))
        if not user:
            return JSONResponse(
                status_code=401,
                content={"success": False, "detail": "Invalid credentials"},
            )

        role_val = normalize_role(user.role)
        token = create_access_token({"sub": str(user.staff_id), "role": role_val})
        print(f"✅ Login success: {user.staff_id}, role stored in token: '{role_val}'")

        # Log the login event
        AdminModel.log_activity(
            user_id=user.id,
            user_name=user.name,
            action="LOGIN",
            details=f"{user.name} ({role_val}) logged in",
            role=role_val,
            db=db,
        )

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
            },
        }

    except Exception as e:
        print("ERROR in login:", traceback.format_exc())
        return JSONResponse(
            status_code=400,
            content={"success": False, "detail": "Invalid request format"},
        )

# --------------------------------------------------
# DOCTOR DASHBOARD SUPPORT ROUTES
# --------------------------------------------------
@app.get("/api/doctors/patients/{patient_id}/consultations", tags=["doctors"])
async def get_patient_consultations_for_doctor(
    patient_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_role(["doctor", "admin"])),
):
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
        ],
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

# ======================= UPDATED QUEUE ENDPOINTS =======================
@app.get("/api/queue/current", tags=["queue"])
async def get_current_consultation(doctor_id: str, db: Session = Depends(get_db)):
    result = QueueManager.get_current_patient(db, doctor_id)
    if result:
        # Handle both dict and object responses
        if isinstance(result, dict):
            patient_id = result.get("patient_id")
            data = {
                "id": result.get("id"),
                "consultation_number": result.get("consultation_number"),
                "patient_id": patient_id,
                "condition": result.get("condition"),
                "priority": result.get("priority"),
                "status": result.get("status"),
                "created_at": result.get("created_at"),
                "started_at": result.get("started_at"),
                "completed_at": result.get("completed_at"),
                "department": result.get("department"),
                "doctor_id": result.get("doctor_id"),
            }
        else:
            patient_id = result.patient_id
            data = {
                "id": result.id,
                "consultation_number": result.consultation_number,
                "patient_id": patient_id,
                "condition": result.condition,
                "priority": result.priority,
                "status": result.status,
                "created_at": result.created_at,
                "started_at": result.started_at,
                "completed_at": result.completed_at,
                "department": result.department,
                "doctor_id": result.doctor_id,
            }
        patient = db.query(Patient).filter(Patient.id == patient_id).first()
        data["patient_name"] = patient.name if patient else None
        return {"success": True, "data": data}
    return {"success": True, "data": None}

@app.get("/api/queue/waiting", tags=["queue"])
async def get_waiting_patients_list(doctor_id: str, db: Session = Depends(get_db)):
    consultations = QueueManager.get_waiting_by_doctor(db, doctor_id)
    enriched = []
    for cons in consultations:
        if isinstance(cons, dict):
            patient_id = cons.get("patient_id")
            data = {
                "id": cons.get("id"),
                "consultation_number": cons.get("consultation_number"),
                "patient_id": patient_id,
                "condition": cons.get("condition"),
                "priority": cons.get("priority"),
                "status": cons.get("status"),
                "created_at": cons.get("created_at"),
                "department": cons.get("department"),
                "doctor_id": cons.get("doctor_id"),
            }
        else:
            patient_id = cons.patient_id
            data = {
                "id": cons.id,
                "consultation_number": cons.consultation_number,
                "patient_id": patient_id,
                "condition": cons.condition,
                "priority": cons.priority,
                "status": cons.status,
                "created_at": cons.created_at,
                "department": cons.department,
                "doctor_id": cons.doctor_id,
            }
        patient = db.query(Patient).filter(Patient.id == patient_id).first()
        data["patient_name"] = patient.name if patient else None
        enriched.append(data)
    return {"success": True, "data": enriched}

# =============================== QUEUE DISPLAY ENDPOINT ===============================
@app.get("/api/queue/display", tags=["queue"])
async def get_queue_display(db: Session = Depends(get_db)):
    """
    Returns combined data for the public queue display:
    - current patient being served (first in_progress consultation)
    - list of waiting patients (status = 'waiting')
    - summary statistics
    """
    from datetime import datetime, timedelta

    # 1. Current patient (first consultation with status 'in_progress')
    current_consultation = (
        db.query(Consultation)
        .filter(Consultation.status == "in_progress")
        .order_by(Consultation.started_at.desc().nullslast())
        .first()
    )
    current_patient = None
    if current_consultation:
        patient = db.query(Patient).filter(Patient.id == current_consultation.patient_id).first()
        if patient:
            token = getattr(patient, "patient_number", None) or f"P{patient.id}"
            room = getattr(current_consultation, "room", None) or "Consultation"
            current_patient = {
                "id": patient.id,
                "name": patient.name,
                "token": token,
                "room": room,
                "arrivedAt": current_consultation.created_at.isoformat() if current_consultation.created_at else None,
            }

    # 2. Waiting patients (status = 'waiting')
    waiting_consultations = (
        db.query(Consultation, Patient)
        .join(Patient, Consultation.patient_id == Patient.id)
        .filter(Consultation.status == "waiting")
        .order_by(Consultation.priority.desc(), Consultation.created_at)
        .all()
    )
    now = datetime.utcnow()
    waiting_patients = []
    total_wait_minutes = 0
    emergency_count = 0

    for cons, pat in waiting_consultations:
        priority_type = "emergency" if (cons.priority and cons.priority > 1) else "normal"
        if priority_type == "emergency":
            emergency_count += 1

        estimated_wait = 15  # placeholder, can be improved
        waiting_patients.append({
            "id": cons.id,
            "name": pat.name,
            "priority": priority_type,
            "condition": cons.condition or "General",
            "arrivedAt": cons.created_at.isoformat() if cons.created_at else None,
            "estimatedWait": estimated_wait,
        })

        if cons.created_at:
            minutes_waiting = (now - cons.created_at).total_seconds() // 60
            total_wait_minutes += minutes_waiting

    total_waiting = len(waiting_patients)
    avg_wait_time = int(total_wait_minutes // total_waiting) if total_waiting > 0 else 0

    # 3. Statistics
    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    completed_today = (
        db.query(Consultation)
        .filter(
            Consultation.status == "treated",
            Consultation.completed_at >= today_start
        )
        .count()
    )

    stats = {
        "totalWaiting": total_waiting,
        "avgWaitTime": avg_wait_time,
        "emergencyCount": emergency_count,
        "completedToday": completed_today,
    }

    return {
        "currentPatient": current_patient,
        "waitingPatients": waiting_patients,
        "stats": stats,
    }
# ============================================================================

# ✅ UPDATED: logs "call next patient" to ActivityLog for notifications
@app.put("/api/consultations/{consultation_id}/status", tags=["queue"])
async def update_consultation_status(
    consultation_id: int,
    status: str,
    db: Session = Depends(get_db),
    current_user=Depends(require_role(["doctor", "admin"])),
):
    consultation = db.query(Consultation).filter(Consultation.id == consultation_id).first()
    if not consultation:
        raise HTTPException(status_code=404, detail="Consultation not found")

    consultation.status = status
    if status == "treated":
        consultation.completed_at = datetime.utcnow()
    db.commit()

    # Resolve patient name for a readable notification
    patient = db.query(Patient).filter(Patient.id == consultation.patient_id).first()
    patient_name = patient.name if patient else f"Patient #{consultation.patient_id}"

    action_label = {
        "treated": "PATIENT_TREATED",
        "waiting": "PATIENT_WAITING",
        "in_progress": "CONSULTATION_STARTED",
    }.get(status, "STATUS_UPDATE")

    friendly = {
        "treated": f"marked {patient_name} as treated ✅",
        "waiting": f"moved {patient_name} back to waiting",
        "in_progress": f"started consultation with {patient_name}",
    }.get(status, f"updated {patient_name} status to '{status}'")

    doctor_id = current_user["username"]
    doctor = AdminModel.get_by_staff_id(db, doctor_id)
    doctor_name = doctor.name if doctor else doctor_id

    AdminModel.log_activity(
        user_id=doctor.id if doctor else None,
        user_name=doctor_name,
        action=action_label,
        details=f"Dr. {doctor_name} {friendly}",
        role=current_user["role"],
        db=db,
    )

    return {"success": True, "message": f"Consultation status updated to {status}"}

@app.get("/api/debug/role", tags=["health"])
async def debug_role(current_user=Depends(get_current_user)):
    return {
        "username": current_user["username"],
        "role": current_user["role"],
        "message": f"Your token identifies you as role='{current_user['role']}'",
    }

@app.get("/api/debug/token", tags=["health"])
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
            prescription_number=f"PRE-{datetime.now().strftime('%Y%m%d%H%M%S')}",
        )
        db.add(new_presc)
        db.commit()
        db.refresh(new_presc)
        return {"success": True, "data": new_presc}
    except Exception as e:
        db.rollback()
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
    db: Session = Depends(get_db),
):
    result = QueueManager.add_to_queue(db, patient_id, department, doctor_id, priority, condition)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result.get("error"))
    return {"success": True, **result}

# ✅ UPDATED: logs "call next patient" to ActivityLog for notifications
@app.post("/api/queue/next/{doctor_id}", tags=["queue"])
async def call_next_patient(
    doctor_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(require_role(["doctor", "admin"])),
):
    result = QueueManager.call_next_patient(db, doctor_id)
    if not result.get("success"):
        raise HTTPException(status_code=404, detail=result.get("error", "No patients in queue"))

    patient_name = (
        result.get("patient_name")
        or result.get("name")
        or result.get("data", {}).get("name")
        or "next patient"
    )
    doctor = AdminModel.get_by_staff_id(db, doctor_id)
    doctor_name = doctor.name if doctor else doctor_id

    AdminModel.log_activity(
        user_id=doctor.id if doctor else None,
        user_name=doctor_name,
        action="CALL_NEXT_PATIENT",
        details=f"Dr. {doctor_name} called {patient_name} 📢",
        role="doctor",
        db=db,
    )

    return result

# --------------------------------------------------
# PATIENT ROUTES
# --------------------------------------------------
@app.get("/api/patients", tags=["patients"])
async def list_patients(search: Optional[str] = None, db: Session = Depends(get_db)):
    # Get base patient list (using PatientService.get_patients)
    patients = PatientService.get_patients(db, search=search)

    # Enrich each patient with gender and latest consultation condition
    enriched = []
    for p in patients:
        # Get the most recent consultation for this patient
        latest_consultation = (
            db.query(Consultation)
            .filter(Consultation.patient_id == p.id)
            .order_by(desc(Consultation.created_at))
            .first()
        )
        enriched.append({
            "id": p.id,
            "name": p.name,
            "phone": p.phone,
            "gender": p.gender,
            "created_at": p.created_at,
            "condition": latest_consultation.condition if latest_consultation else None,
        })

    return {"success": True, "data": enriched, "count": len(patients)}

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
    db: Session = Depends(get_db),
):
    stats = AdminService.get_dashboard_stats(db)
    return {"success": True, "data": stats}

@app.get("/api/admin/activity-logs", tags=["admin"])
async def get_activity_logs(
    limit: int = 10,
    db: Session = Depends(get_db),
    current_user=Depends(require_role(["admin"])),
):
    logs = (
        db.query(ActivityLog)
        .order_by(desc(ActivityLog.timestamp))
        .limit(limit)
        .all()
    )
    return {
        "success": True,
        "data": [
            {
                "id": log.id,
                "user_name": log.user_name,
                "action": log.action,
                "details": log.details,
                "role": log.role,
                "timestamp": log.timestamp.isoformat() if log.timestamp else None,
            }
            for log in logs
        ],
    }

@app.get("/api/admin/staff", tags=["admin"])
async def get_all_staff_list(
    role: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user=Depends(require_role(["admin"])),
):
    staff_members = AdminModel.get_all_staff(role=role, db=db)
    return {"success": True, "data": staff_members or []}

@app.post("/api/admin/staff", tags=["admin"])
async def add_new_staff(
    staff_data: StaffCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_role(["admin"])),
):
    try:
        new_staff = AdminModel.create_staff(staff_data, db)
        return {
            "success": True,
            "data": new_staff,
            "message": f"Staff {staff_data.name} created successfully",
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.put("/api/admin/staff/{staff_id}", tags=["admin"])
async def update_staff(
    staff_id: int,
    staff_update: StaffUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(require_role(["admin"])),
):
    try:
        updated_staff = AdminModel.update_staff(staff_id, staff_update, db)
        if not updated_staff:
            raise HTTPException(status_code=404, detail="Staff member not found")
        return {"success": True, "data": updated_staff, "message": "Staff updated successfully"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.delete("/api/admin/staff/{staff_id}", tags=["admin"])
async def remove_staff(
    staff_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_role(["admin"])),
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
    current_user=Depends(require_role(["admin"])),
):
    query = db.query(Consultation).join(Patient, Consultation.patient_id == Patient.id)
    if department:
        query = query.filter(Consultation.department == department)
    if status:
        query = query.filter(Consultation.status == status)
    if from_date:
        query = query.filter(Consultation.created_at >= datetime.fromisoformat(from_date))
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

    wait_times = []
    for c in consultations:
        if c.started_at and c.created_at:
            wait = (c.started_at - c.created_at).seconds // 60
            if wait > 0:
                wait_times.append(wait)

    treated_today = db.query(Consultation).filter(
        Consultation.status == "treated",
        Consultation.completed_at >= datetime.now().replace(hour=0, minute=0, second=0),
    ).count()

    return {
        "records": records,
        "stats": {
            "totalPatients": db.query(Patient).count(),
            "totalConsultations": len(consultations),
            "avgWaitTime": sum(wait_times) // len(wait_times) if wait_times else 0,
            "treatedToday": treated_today,
        },
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
    current_user=Depends(require_role(["admin"])),
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
            },
        )
    except Exception as e:
        print("ERROR in export_report:", traceback.format_exc())
        return JSONResponse(
            status_code=500,
            content={"success": False, "detail": str(e)},
            headers={
                "Access-Control-Allow-Origin": "http://localhost:3000",
                "Access-Control-Allow-Credentials": "true",
            },
        )

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
    current_user=Depends(require_role(["admin"])),
):
    try:
        file_content, media_type, filename = await AdminService.generate_personnel_report(
            format, db, include_charts
        )
        return Response(
            content=file_content,
            media_type=media_type,
            headers={
                "Content-Disposition": f"attachment; filename={filename}",
                "Access-Control-Allow-Origin": "http://localhost:3000",
                "Access-Control-Allow-Credentials": "true",
                "Access-Control-Expose-Headers": "Content-Disposition",
            },
        )
    except Exception as e:
        print("ERROR in personnel export:", traceback.format_exc())
        return JSONResponse(
            status_code=500,
            content={"success": False, "detail": str(e)},
            headers={
                "Access-Control-Allow-Origin": "http://localhost:3000",
                "Access-Control-Allow-Credentials": "true",
            },
        )

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
                "phone": p.phone,          # Added phone
                "condition": c.condition,
                "priority": c.priority,
                "status": c.status,
                "arrival_time": c.created_at.strftime("%H:%M") if c.created_at else "--:--",
            }
            for c, p in queue_data
        ],
    }

# =============================== UPDATED QUICK REGISTRATION ===============================
@app.post("/api/receptionist/patients/quick", tags=["receptionist"])
async def quick_register_patient(data: QuickRegistration, db: Session = Depends(get_db)):
    try:
        p_no = PatientModel.generate_patient_number(db)
        # Create patient with new fields
        new_patient = Patient(
            name=data.patient_name,
            phone=data.phone,
            patient_number=p_no,
            age=data.age,                # NEW
            gender=data.gender,          # NEW
            status="active"              # NEW – default status
        )
        db.add(new_patient)
        db.flush()
        # Create consultation with a default doctor_id so it appears in the doctor's waiting list
        new_consultation = Consultation(
            patient_id=new_patient.id,
            condition=data.condition,
            priority=data.priority,
            department=data.department,
            status="waiting",
            doctor_id="DOC001",          # <-- ADDED: assign to the default doctor
            consultation_number=f"C-{datetime.now().strftime('%y%m%d%H%M%S')}",
        )
        db.add(new_consultation)
        db.commit()

        AdminModel.log_activity(
            user_id=None,
            user_name="Receptionist",
            action="PATIENT_REGISTERED",
            details=f"New patient registered: {data.patient_name} — {data.condition}",
            role="receptionist",
            db=db,
        )

        return {"success": True}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
# ============================================================================

# --------------------------------------------------
# ✅ NOTIFICATIONS ROUTE — reads real ActivityLog data
# --------------------------------------------------
@app.get("/api/notifications", tags=["notifications"])
async def get_notifications(
    limit: int = 20,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),   # any logged-in role can read
):
    """Return recent activity logs as real-time notifications, newest first."""
    logs = (
        db.query(ActivityLog)
        .order_by(desc(ActivityLog.timestamp))
        .limit(limit)
        .all()
    )

    def resolve_type(action: str) -> str:
        a = (action or "").lower()
        if any(k in a for k in ["error", "fail", "denied", "invalid"]):
            return "error"
        if any(k in a for k in ["emergency", "critical", "warn", "low_stock"]):
            return "warning"
        if any(k in a for k in ["treated", "complete", "done", "success", "registered"]):
            return "success"
        return "info"

    return {
        "success": True,
        "notifications": [
            {
                "id": log.id,
                "message": log.details or log.action,
                "type": resolve_type(log.action),
                "user_name": log.user_name,
                "role": log.role,
                "timestamp": log.timestamp.isoformat() if log.timestamp else None,
                "read": False,
            }
            for log in logs
        ],
    }


# --------------------------------------------------
# ✅ AI-POWERED MEDICATION SUGGESTION ENDPOINT
# --------------------------------------------------

@app.post("/api/ai/suggest-medication", tags=["doctors"])
async def suggest_medication(request: Request):
    try:
        body = await request.json()
        diagnosis = body.get("diagnosis", "").strip()

        if not diagnosis:
            raise HTTPException(status_code=400, detail="Diagnosis is required")

        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise HTTPException(status_code=500, detail="ANTHROPIC_API_KEY not configured on server")

        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "claude-sonnet-4-20250514",
                    "max_tokens": 1000,
                    "messages": [
                        {
                            "role": "user",
                            "content": f"""You are a clinical decision support assistant. Given a diagnosis, return medication suggestions as JSON only.

Diagnosis: "{diagnosis}"

Return ONLY a raw JSON array, no markdown, no explanation, no extra text. Example format:
[
  {{
    "medication": "Amoxicillin",
    "dosage": "500mg",
    "frequency": "3x daily",
    "duration": "7 days",
    "instructions": "Take with food",
    "note": "First-line antibiotic"
  }}
]"""
                        }
                    ],
                },
                timeout=30.0,
            )

        print(f"🤖 Anthropic status: {response.status_code}")

        if response.status_code != 200:
            print(f"🤖 Anthropic error: {response.text}")
            return {"success": True, "suggestions": []}

        data = response.json()
        raw = data.get("content", [{}])[0].get("text", "[]")
        print(f"🤖 Raw AI response: {raw}")

        clean = raw.replace("```json", "").replace("```", "").strip()
        suggestions = json.loads(clean)

        return {"success": True, "suggestions": suggestions if isinstance(suggestions, list) else []}

    except json.JSONDecodeError as e:
        print(f"JSON parse error: {e}")
        return {"success": True, "suggestions": []}
    except Exception as e:
        print(f"suggest_medication error: {e}")
        raise HTTPException(status_code=500, detail=str(e)) #functional AI intergration



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
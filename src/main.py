from fastapi import FastAPI, Depends, HTTPException, status, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import desc
from contextlib import asynccontextmanager
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
import os
import json
import traceback
from dotenv import load_dotenv
from jose import JWTError, jwt

# Database Imports
from src.database import SessionLocal, engine, Base

# Models & Services
from src.models.doctor import DoctorModel, DoctorLogin, DoctorCreate
from src.models.patients import (
    Patient, PatientCreate, PatientUpdate, QuickRegistration, Prescription, Consultation, PatientModel  
)
from src.models.admin import StaffCreate, StaffUpdate, AdminModel, StaffLogin, Staff, StaffRole
from src.models.receptionist import ReceptionistCreate, ReceptionistUpdate, ReceptionistModel, ReceptionistLogin
from src.services.queue_manager import QueueManager 
from src.services.patient_service import PatientService
from src.services.admin_service import AdminService
from src.services.receptionist_service import ReceptionistService

load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY", "change-this-secret-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# --------------------------------------------------
# DATABASE & LIFESPAN
# --------------------------------------------------

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

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --------------------------------------------------
# MIDDLEWARE & SECURITY
# --------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    # Explicitly list the frontend origins. Do NOT use "*" here.
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",  # Common for Vite users
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,     # Required for authorization headers/cookies
    allow_methods=["*"],
    allow_headers=["*"],
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/login", auto_error=False)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire, "iat": datetime.utcnow()})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    if not token:
        raise HTTPException(status_code=401, detail="Authentication required")
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        role = payload.get("role")
        if not username or not role:
            raise HTTPException(status_code=401, detail="Invalid token claims")
        return {"username": username, "role": role} 
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

def require_role(required_roles: List[str]):
    def role_checker(current_user = Depends(get_current_user)):
        if current_user["role"] not in required_roles:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return current_user
    return role_checker

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
        print(f"DEBUG: Login Attempt with payload: {body}")

        # 1. Dig into nested objects (Handles {'employee_id': {'username': '...'}})
        # We look for any value that is a dictionary and check it for credentials
        data = body
        for key, value in body.items():
            if isinstance(value, dict) and ("username" in value or "staff_id" in value):
                data = value
                break

        # 2. Extract credentials from the flattened data
        username = data.get("username") or data.get("staff_id") or data.get("employee_id")
        password = data.get("password")

        if not username or not password:
            return JSONResponse(
                status_code=400, 
                content={"success": False, "detail": "Username and password required"}
            )

        # 3. Authenticate
        user = AdminModel.authenticate(db, staff_id=str(username), password=str(password))
        
        if user:
            role_val = user.role.value if hasattr(user.role, 'value') else str(user.role)
            token = create_access_token({"sub": str(user.staff_id), "role": role_val})
            
            return {
                "success": True,
                "access_token": token, 
                "token_type": "bearer", 
                "role": role_val, 
                "username": user.name,
                "staff_id": user.staff_id
            }

        return JSONResponse(status_code=401, content={"success": False, "detail": "Invalid credentials"})

    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse(status_code=400, content={"success": False, "detail": "Invalid request format"})
# --------------------------------------------------
# DOCTOR DASHBOARD SUPPORT ROUTES
# --------------------------------------------------

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
            doctor_id=str(data.get("doctor_id")),
            medications=json.dumps(data.get("medications", [])),
            diagnosis=data.get("diagnosis"),
            instructions=data.get("instructions")
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

# --------------------------------------------------
# OTHER DASHBOARD ROUTES
# --------------------------------------------------

@app.get("/api/admin/dashboard", tags=["admin"])
async def admin_dashboard(current_user = Depends(require_role(["admin"])), db: Session = Depends(get_db)):
    stats = AdminService.get_dashboard_stats(db)
    return {"success": True, "data": stats}

@app.get("/api/receptionist/dashboard", tags=["receptionist"])
async def get_receptionist_dashboard(db: Session = Depends(get_db)):
    result = ReceptionistService.get_dashboard_stats(db)
    return {"success": True, "data": result}

@app.get("/api/receptionist/queue", tags=["receptionist"])
async def get_receptionist_queue(db: Session = Depends(get_db)):
    """Join Consultation + Patient to show name and status together"""
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
    """Atomic: Create Patient -> Flush ID -> Create Consultation"""
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
        

# --- STAFF MANAGEMENT ROUTES ---

@app.get("/api/admin/staff", tags=["admin"])
async def get_all_staff_list(
    role: Optional[str] = None, 
    db: Session = Depends(get_db),
    current_user = Depends(require_role(["admin"])) # Protect this route!
):
    """Fetch all staff members for the Admin Dashboard"""
    staff_members = AdminModel.get_all_staff(role=role, db=db)
    return {"success": True, "data": staff_members}

@app.post("/api/admin/staff", tags=["admin"])
async def add_new_staff(
    staff_data: StaffCreate, 
    db: Session = Depends(get_db),
    current_user = Depends(require_role(["admin"]))
):
    """Create a new staff member (Doctor, Nurse, etc.)"""
    try:
        new_staff = AdminModel.create_staff(staff_data, db)
        return {"success": True, "data": new_staff}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.delete("/api/admin/staff/{staff_id}", tags=["admin"])
async def remove_staff(
    staff_id: int, 
    db: Session = Depends(get_db),
    current_user = Depends(require_role(["admin"]))
):
    """Deactivate a staff member"""
    success = AdminModel.delete_staff(staff_id, db)
    if not success:
        raise HTTPException(status_code=404, detail="Staff member not found")
    return {"success": True, "message": "Staff deactivated"}


# other routes 

@app.get("/api/notifications", tags=["notifications"])
async def get_notifications(db: Session = Depends(get_db)):
    """Fetches system notifications for the logged-in user"""
    # For now, we return a mock notification to stop the 404
    # Later, you can link this to a 'Notifications' table in your DB
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
    return {
        "message": "Mashar Hospital API v2.1",
        "docs": "/docs",
        "health": "/api/health"
    }

@app.get("/api/health", tags=["health"])
async def health_check(db: Session = Depends(get_db)):
    stats = QueueManager.get_queue_stats(db)
    return {
        "success": True,
        "status": "healthy",
        "version": "2.1.0",
        "queue": stats
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.main:app", host="0.0.0.0", port=8000, reload=True) 
"""
====================================================================================================
MASHAR HOSPITAL API - COMPLETE ROUTES & LOGIN CREDENTIALS
====================================================================================================

BASE URL: http://localhost:8000 | DOCS: http://localhost:8000/docs | REDOC: http://localhost:8000/redoc

----------------------------------------------------------------------------------------------------
🚀 NEW: UNIVERSAL LOGIN (Works for all user types - Role Auto-Detection)
----------------------------------------------------------------------------------------------------
POST /api/login
Content-Type: application/json

{
    "username": "A001",     # Can be username, staff_id, or employee_id
    "password": "admin123",
    "role": "admin"          # Optional - system auto-detects if not provided
}

----------------------------------------------------------------------------------------------------
LOGIN CREDENTIALS (Default Users)
----------------------------------------------------------------------------------------------------

┌──────────────┬─────────────┬─────────────────┬─────────────────┬─────────────────┐
│ Role         │ Username/ID │ Password        │ Name            │ Department      │
├──────────────┼─────────────┼─────────────────┼─────────────────┼─────────────────┤
│ Admin        │ A001        │ admin123        │ Admin User      │ Administration  │
│ Doctor       │ D001        │ doctor123       │ Dr. John Kamau  │ Cardiology      │
│ Receptionist │ R001        │ receptionist123 │ Mary Wanjiku    │ Front Desk      │
│ Nurse        │ N001        │ nurse123        │ Nurse Sarah     │ General Ward    │
└──────────────┴─────────────┴─────────────────┴─────────────────┴─────────────────┘

----------------------------------------------------------------------------------------------------
🔐 ROLE-SPECIFIC LOGIN ENDPOINTS
----------------------------------------------------------------------------------------------------

┌─────────────────────┬────────────────────────────────────────────────┐
│ Endpoint            │ Description                                    │
├─────────────────────┼────────────────────────────────────────────────┤
│ POST /api/login     │ Universal login - auto-detects role            │
│ POST /api/doctors/login │ Doctor-specific login                      │
│ POST /api/admin/login    │ Admin-specific login                      │
│ POST /api/receptionist/login │ Receptionist-specific login           │
└─────────────────────┴────────────────────────────────────────────────┘

Example Requests:

1. Universal Login (Auto-detect):
   curl -X POST http://localhost:8000/api/login \
     -H "Content-Type: application/json" \
     -d '{"username":"A001","password":"admin123"}'

2. Doctor Login:
   curl -X POST http://localhost:8000/api/doctors/login \
     -H "Content-Type: application/json" \
     -d '{"username":"D001","password":"doctor123"}'

3. Admin Login:
   curl -X POST http://localhost:8000/api/admin/login \
     -H "Content-Type: application/json" \
     -d '{"staff_id":"A001","password":"admin123"}'

4. Receptionist Login:
   curl -X POST http://localhost:8000/api/receptionist/login \
     -H "Content-Type: application/json" \
     -d '{"employee_id":"R001","password":"receptionist123"}'

----------------------------------------------------------------------------------------------------
🌐 PUBLIC ROUTES (No Authentication Required)
----------------------------------------------------------------------------------------------------

[ROOT & HEALTH]
────────────────────────────────────────────────────────────────────────────────────
GET    /                             - API root with links to documentation
GET    /api/health                   - Health check endpoint with queue status

[DOCTOR ROUTES]
────────────────────────────────────────────────────────────────────────────────────
POST   /api/doctors/login            - Authenticate doctor (returns JWT token)
GET    /api/doctors                   - Get all doctors
GET    /api/doctors/{doctor_id}       - Get specific doctor by ID

[PATIENT ROUTES]
────────────────────────────────────────────────────────────────────────────────────
GET    /api/patients                  - Get all patients (filters: search, status)
GET    /api/patients/{patient_id}     - Get specific patient by ID
POST   /api/patients                  - Create new patient
PUT    /api/patients/{patient_id}     - Update patient information

[QUEUE ROUTES]
────────────────────────────────────────────────────────────────────────────────────
GET    /api/queue/current             - Get current consultation (filters: doctor_id, department)
GET    /api/queue/waiting             - Get waiting patients (filters: doctor_id, department)
POST   /api/queue/register             - Register patient to queue
GET    /api/queue/status               - Get queue statistics

[PRESCRIPTION ROUTES]
────────────────────────────────────────────────────────────────────────────────────
GET    /api/prescriptions              - Get prescriptions (filters: search, patient_id)
POST   /api/prescriptions              - Create prescription

----------------------------------------------------------------------------------------------------
🛡️ PROTECTED ROUTES (Authentication Required)
----------------------------------------------------------------------------------------------------

[USER ROUTES - Any Authenticated User]
────────────────────────────────────────────────────────────────────────────────────
GET    /api/doctors/current            - Get currently logged-in user info

[RECEPTIONIST ROUTES - Receptionist or Admin]
────────────────────────────────────────────────────────────────────────────────────
GET    /api/receptionist/dashboard          - Receptionist dashboard statistics
POST   /api/receptionist/patients/quick     - Quick patient registration
GET    /api/receptionist/queue              - Get patients in queue (filter: department)
GET    /api/receptionists                   - Get all receptionists
GET    /api/receptionists/active            - Get only active receptionists
GET    /api/receptionists/{receptionist_id} - Get receptionist by database ID
GET    /api/receptionists/employee/{employee_id} - Get receptionist by employee ID (R001)

[QUEUE MANAGEMENT - Receptionist/Admin/Doctor]
────────────────────────────────────────────────────────────────────────────────────
GET    /api/queue/priority             - Get queue organized by priority (filter: department)
POST   /api/queue/next/{doctor_id}     - Call next patient for a doctor

[PATIENT SEARCH - Medical Staff (Doctor/Nurse/Admin)]
────────────────────────────────────────────────────────────────────────────────────
GET    /api/patients/search/{query}    - Search patients by name or phone

[NOTIFICATION ROUTES - All Authenticated Users]
────────────────────────────────────────────────────────────────────────────────────
GET    /api/notifications               - Get notifications for current user's role
GET    /api/notifications/unread/count  - Get count of unread notifications
PUT    /api/notifications/{notification_id}/read - Mark notification as read
PUT    /api/notifications/read-all      - Mark all notifications as read

[PATIENT ROUTES - Admin Only]
────────────────────────────────────────────────────────────────────────────────────
DELETE /api/patients/{patient_id}       - Delete patient (Admin only)

[RECEPTIONIST MANAGEMENT - Admin Only]
────────────────────────────────────────────────────────────────────────────────────
POST   /api/receptionists                - Create new receptionist
PUT    /api/receptionists/{receptionist_id} - Update receptionist information
DELETE /api/receptionists/{receptionist_id} - Delete/Deactivate receptionist

----------------------------------------------------------------------------------------------------
👑 ADMIN ONLY ROUTES
----------------------------------------------------------------------------------------------------

[ADMIN AUTHENTICATION]
────────────────────────────────────────────────────────────────────────────────────
POST   /api/admin/login                 - Admin-specific login endpoint

[DASHBOARD]
────────────────────────────────────────────────────────────────────────────────────
GET    /api/admin/dashboard              - Complete admin dashboard with statistics

[STAFF MANAGEMENT]
────────────────────────────────────────────────────────────────────────────────────
GET    /api/admin/staff                  - Get all staff members (filters: role, department)
GET    /api/admin/staff/{staff_id}       - Get specific staff by database ID
GET    /api/admin/staff/employee/{staff_id_str} - Get staff by employee ID (e.g., D001, A001)
GET    /api/admin/staff/statistics       - Get staff statistics (counts by role, status)
POST   /api/admin/staff                  - Create new staff member
PUT    /api/admin/staff/{staff_id}       - Update staff information
DELETE /api/admin/staff/{staff_id}       - Delete/deactivate staff member

[BED MANAGEMENT]
────────────────────────────────────────────────────────────────────────────────────
GET    /api/admin/beds                   - Get all beds with occupancy status & statistics
POST   /api/admin/beds/{bed_id}/assign   - Assign bed to patient (params: patient_id)
POST   /api/admin/beds/{bed_id}/release  - Release bed from patient

[INVENTORY MANAGEMENT]
────────────────────────────────────────────────────────────────────────────────────
GET    /api/admin/inventory              - Get all inventory items with status
PUT    /api/admin/inventory/{item_id}    - Update inventory quantity (params: quantity_change)

[ACTIVITY LOGS]
────────────────────────────────────────────────────────────────────────────────────
GET    /api/admin/activity-logs          - Get recent activity logs (limit: 20)

[RECORDS & REPORTS]
────────────────────────────────────────────────────────────────────────────────────
GET    /api/admin/records                - Get all records (staff, beds, inventory, logs)
GET    /api/admin/reports/monthly        - Generate monthly report with statistics

----------------------------------------------------------------------------------------------------
🔧 DEBUG ENDPOINTS (Development Only - Remove in Production)
----------------------------------------------------------------------------------------------------

POST   /api/debug/login                  - Debug login - shows what client is sending
GET    /api/debug/users                   - List all available users in system

----------------------------------------------------------------------------------------------------
📊 SUMMARY
----------------------------------------------------------------------------------------------------
Total Routes: 60+
├── Public Routes: 15
├── Protected Routes: 40+
│   ├── Any Authenticated User: 5
│   ├── Receptionist/Admin: 10
│   ├── Medical Staff (Doctor/Nurse/Admin): 5
│   └── Admin Only: 25
└── Debug Routes: 2

----------------------------------------------------------------------------------------------------
💡 USAGE EXAMPLES
----------------------------------------------------------------------------------------------------

1. UNIVERSAL LOGIN (Auto-detect role):
   curl -X POST http://localhost:8000/api/login \
     -H "Content-Type: application/json" \
     -d '{"username":"A001","password":"admin123"}'

2. LOGIN AS DOCTOR (with role):
   curl -X POST http://localhost:8000/api/doctors/login \
     -H "Content-Type: application/json" \
     -d '{"username":"D001","password":"doctor123","role":"doctor"}'

3. ACCESS ADMIN DASHBOARD (with token):
   curl -X GET http://localhost:8000/api/admin/dashboard \
     -H "Authorization: Bearer <your_token_here>"

4. CREATE NEW DOCTOR (Admin only):
   curl -X POST http://localhost:8000/api/admin/staff \
     -H "Authorization: Bearer <token>" \
     -H "Content-Type: application/json" \
     -d '{
       "staff_id": "D002",
       "name": "Dr. Jane Smith",
       "role": "doctor",
       "phone": "+254700111555",
       "email": "jane.smith@hospital.com",
       "department": "Pediatrics",
       "specialization": "Pediatrician",
       "password": "doctor456"
     }'

5. CREATE NEW RECEPTIONIST (Admin only):
   curl -X POST http://localhost:8000/api/receptionists \
     -H "Authorization: Bearer <token>" \
     -H "Content-Type: application/json" \
     -d '{
       "employee_id": "R003",
       "name": "Alice Johnson",
       "phone": "+254700111777",
       "email": "alice@hospital.com",
       "department": "Front Desk",
       "password": "receptionist789"
     }'

6. QUICK REGISTER PATIENT (Receptionist):
   curl -X POST http://localhost:8000/api/receptionist/patients/quick \
     -H "Authorization: Bearer <token>" \
     -H "Content-Type: application/json" \
     -d '{
       "patient_name": "John Doe",
       "phone": "+254722333444",
       "age": 35,
       "gender": "male",
       "department": "Cardiology",
       "condition": "Chest pain",
       "priority": 2
     }'

7. GET QUEUE BY PRIORITY:
   curl -X GET "http://localhost:8000/api/queue/priority?department=Cardiology" \
     -H "Authorization: Bearer <token>"

8. ASSIGN BED TO PATIENT (Admin):
   curl -X POST http://localhost:8000/api/admin/beds/5/assign?patient_id=123 \
     -H "Authorization: Bearer <token>"

9. CHECK INVENTORY STATUS (Admin):
   curl -X GET http://localhost:8000/api/admin/inventory \
     -H "Authorization: Bearer <token>"

10. VIEW ACTIVITY LOGS (Admin):
    curl -X GET "http://localhost:8000/api/admin/activity-logs?limit=20" \
      -H "Authorization: Bearer <token>"

11. DEBUG - SEE ALL USERS:
    curl -X GET http://localhost:8000/api/debug/users

12. DEBUG - TEST LOGIN:
    curl -X POST http://localhost:8000/api/debug/login \
      -H "Content-Type: application/json" \
      -d '{"username":"A001","password":"admin123"}'

----------------------------------------------------------------------------------------------------
📝 NOTES
----------------------------------------------------------------------------------------------------
- Role is now OPTIONAL in all login endpoints - system auto-detects
- Username can be: username, staff_id, or employee_id depending on user type
- All protected endpoints require Bearer token in Authorization header
- Admin endpoints require user role = "admin"
- Receptionist endpoints require user role = "receptionist" or "admin"
- Medical staff endpoints require user role = "doctor", "nurse", or "admin"
- Debug endpoints should be disabled in production
- All timestamps are in ISO format
- Default pagination limit is 50 items unless specified
"""
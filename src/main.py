from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer
from contextlib import asynccontextmanager
from typing import Optional, List
from datetime import datetime
import os
from dotenv import load_dotenv
from jose import JWTError, jwt

# Models
from src.models.doctor import DoctorModel, DoctorLogin
from src.models.patients import PatientCreate, PatientUpdate, QuickRegistration, NotificationType
from src.models.admin import StaffCreate, StaffUpdate, StaffRole, StaffStatus
from src.models.receptionist import ReceptionistCreate, ReceptionistUpdate

# Services
from src.services.patient_service import PatientService
from src.services.queue_manager import QueueManager
from src.services.admin_service import AdminService
from src.services.receptionist_service import ReceptionistService

load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY", "secret-key")
ALGORITHM = "HS256"


# --------------------------------------------------
# APPLICATION LIFESPAN
# --------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Starting up...")
    QueueManager.initialize()
    yield
    print("Shutting down...")


app = FastAPI(
    title="Mashar Hospital Queue Management System",
    description="Backend API for hospital queue management",
    version="1.1.0",
    lifespan=lifespan
)


# --------------------------------------------------
# CORS
# --------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --------------------------------------------------
# AUTHENTICATION
# --------------------------------------------------
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/doctors/login", auto_error=False)


async def get_current_user(token: str = Depends(oauth2_scheme)):
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        if not username:
            raise HTTPException(status_code=401, detail="Invalid token")
    except JWTError:
        raise HTTPException(status_code=401, detail="Token error")
    user = DoctorModel.get_by_username(username)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


async def get_optional_user(token: str = Depends(oauth2_scheme)):
    if not token:
        return None
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        if username:
            return DoctorModel.get_by_username(username)
    except JWTError:
        return None
    return None


# --------------------------------------------------
# ROOT & HEALTH CHECK
# --------------------------------------------------
@app.get("/")
async def root():
    return {
        "message": "Mashar Hospital API is running",
        "docs": "http://localhost:8000/docs",
        "health": "http://localhost:8000/api/health"
    }


@app.get("/api/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


# --------------------------------------------------
# DOCTOR ROUTES
# --------------------------------------------------
@app.post("/api/doctors/login")
async def doctor_login(login_data: DoctorLogin):
    result = DoctorModel.authenticate(login_data.username, login_data.password, login_data.role)
    if not result:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return result


@app.get("/api/doctors/current")
async def get_current_doctor(current_user: dict = Depends(get_current_user)):
    return current_user


@app.get("/api/doctors")
async def get_doctors():
    doctors = DoctorModel.get_all_doctors()
    return doctors or {"message": "No doctors found"}


@app.get("/api/doctors/{doctor_id}")
async def get_doctor_by_id(doctor_id: int):
    doctor = DoctorModel.get_doctor_by_id(doctor_id)
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor not found")
    return doctor


# --------------------------------------------------
# PATIENT ROUTES
# --------------------------------------------------
@app.get("/api/patients")
async def get_patients(search: Optional[str] = None, status: Optional[str] = None, current_user: dict = Depends(get_optional_user)):
    return PatientService.get_patients(search, status)


@app.get("/api/patients/{patient_id}")
async def get_patient(patient_id: int):
    patient = PatientService.get_patient_by_id(patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    return patient


@app.post("/api/patients")
async def create_patient(patient: PatientCreate):
    return PatientService.create_patient(patient)


@app.put("/api/patients/{patient_id}")
async def update_patient(patient_id: int, patient_update: PatientUpdate):
    result = PatientService.update_patient(patient_id, patient_update)
    if not result:
        raise HTTPException(status_code=404, detail="Patient not found")
    return result


@app.delete("/api/patients/{patient_id}")
async def delete_patient(patient_id: int, current_user: dict = Depends(get_current_user)):
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    result = PatientService.delete_patient(patient_id)
    if not result:
        raise HTTPException(status_code=404, detail="Patient not found")
    return {"message": "Patient deleted successfully"}


# --------------------------------------------------
# QUEUE ROUTES
# --------------------------------------------------
@app.get("/api/queue/current")
async def get_current_consultation(doctor_id: Optional[int] = None, department: Optional[str] = None):
    return QueueManager.get_current_consultation(doctor_id, department)


@app.get("/api/queue/waiting")
async def get_waiting_patients(doctor_id: Optional[int] = None, department: Optional[str] = "Cardiology"):
    return QueueManager.get_waiting_patients(doctor_id, department)


@app.post("/api/queue/register")
async def register_patient_queue(patient_id: int, department: str = "Cardiology", condition: Optional[str] = None, priority: int = 1, doctor_id: int = 1):
    try:
        return QueueManager.add_to_queue(patient_id, department, condition, priority, doctor_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/queue/status")
async def get_queue_status():
    return QueueManager.get_queue_stats()


# --------------------------------------------------
# PRESCRIPTIONS
# --------------------------------------------------
@app.get("/api/prescriptions")
async def get_prescriptions(search: Optional[str] = None, patient_id: Optional[int] = None):
    return PatientService.get_prescriptions(search, patient_id)


@app.post("/api/prescriptions")
async def create_prescription(patient_id: int, medication: str, instructions: Optional[str] = None, dosage: Optional[str] = None, duration: Optional[str] = None, doctor_id: Optional[int] = None):
    if not doctor_id:
        raise HTTPException(status_code=400, detail="Doctor ID required")
    return PatientService.create_prescription(patient_id, doctor_id, medication, instructions, dosage, duration)


# --------------------------------------------------
# RECEPTIONIST ROUTES (Original)
# --------------------------------------------------
@app.get("/api/receptionist/dashboard")
async def get_receptionist_dashboard(current_user: dict = Depends(get_current_user)):
    if current_user.get("role") not in ["receptionist", "admin"]:
        raise HTTPException(status_code=403, detail="Receptionist access required")
    return ReceptionistService.get_dashboard_stats()


@app.post("/api/receptionist/patients/quick")
async def quick_register_patient(registration: QuickRegistration, current_user: dict = Depends(get_current_user)):
    if current_user.get("role") not in ["receptionist", "admin"]:
        raise HTTPException(status_code=403, detail="Receptionist access required")
    
    # Add receptionist name to registration
    registration.receptionist_name = current_user.get("name", "Receptionist")
    return ReceptionistService.quick_register_patient(registration, current_user.get("id", 0))


@app.get("/api/receptionist/queue")
async def get_receptionist_queue(department: Optional[str] = None, current_user: dict = Depends(get_current_user)):
    if current_user.get("role") not in ["receptionist", "admin", "doctor"]:
        raise HTTPException(status_code=403, detail="Access denied")
    return ReceptionistService.get_patients_in_queue(department)


# --------------------------------------------------
# NEW RECEPTIONIST ROUTES (Added)
# --------------------------------------------------

@app.get("/api/receptionists")
async def get_all_receptionists(current_user: dict = Depends(get_current_user)):
    """Get all receptionists (Active and Inactive)"""
    if current_user.get("role") not in ["receptionist", "admin"]:
        raise HTTPException(status_code=403, detail="Access denied")
    return ReceptionistService.get_all_receptionists()


@app.get("/api/receptionists/active")
async def get_active_receptionists(current_user: dict = Depends(get_current_user)):
    """Get only active receptionists"""
    if current_user.get("role") not in ["receptionist", "admin"]:
        raise HTTPException(status_code=403, detail="Access denied")
    return ReceptionistService.get_active_receptionists()


@app.get("/api/receptionists/{receptionist_id}")
async def get_receptionist_by_id(receptionist_id: int, current_user: dict = Depends(get_current_user)):
    """Get receptionist by ID"""
    if current_user.get("role") not in ["receptionist", "admin"]:
        raise HTTPException(status_code=403, detail="Access denied")
    
    receptionist = ReceptionistService.get_receptionist_by_id(receptionist_id)
    if not receptionist:
        raise HTTPException(status_code=404, detail="Receptionist not found")
    return receptionist


@app.get("/api/receptionists/employee/{employee_id}")
async def get_receptionist_by_employee_id(employee_id: str, current_user: dict = Depends(get_current_user)):
    """Get receptionist by employee ID"""
    if current_user.get("role") not in ["receptionist", "admin"]:
        raise HTTPException(status_code=403, detail="Access denied")
    
    receptionist = ReceptionistService.get_receptionist_by_employee_id(employee_id)
    if not receptionist:
        raise HTTPException(status_code=404, detail="Receptionist not found")
    return receptionist


@app.post("/api/receptionists")
async def create_receptionist(receptionist_data: ReceptionistCreate, current_user: dict = Depends(get_current_user)):
    """Create a new receptionist (Admin only)"""
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    result = ReceptionistService.create_receptionist(receptionist_data)
    if not result.get("success", True):
        raise HTTPException(status_code=400, detail=result.get("error", "Failed to create receptionist"))
    
    return result


@app.put("/api/receptionists/{receptionist_id}")
async def update_receptionist(receptionist_id: int, receptionist_update: ReceptionistUpdate, current_user: dict = Depends(get_current_user)):
    """Update receptionist information (Admin only)"""
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    result = ReceptionistService.update_receptionist(receptionist_id, receptionist_update)
    if not result:
        raise HTTPException(status_code=404, detail="Receptionist not found")
    
    return result


@app.delete("/api/receptionists/{receptionist_id}")
async def delete_receptionist(receptionist_id: int, current_user: dict = Depends(get_current_user)):
    """Delete/Deactivate receptionist (Admin only)"""
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    result = ReceptionistService.delete_receptionist(receptionist_id)
    if not result:
        raise HTTPException(status_code=404, detail="Receptionist not found")
    
    return {"message": "Receptionist deleted successfully"}


# --------------------------------------------------
# QUEUE MANAGEMENT (Enhanced)
# --------------------------------------------------

@app.get("/api/queue/priority")
async def get_queue_by_priority(department: Optional[str] = None, current_user: dict = Depends(get_current_user)):
    """Get queue organized by priority"""
    if current_user.get("role") not in ["receptionist", "admin", "doctor"]:
        raise HTTPException(status_code=403, detail="Access denied")
    
    return ReceptionistService.get_queue_by_priority(department)


@app.post("/api/queue/next/{doctor_id}")
async def call_next_patient(doctor_id: int, current_user: dict = Depends(get_current_user)):
    """Call the next patient for a doctor"""
    if current_user.get("role") not in ["receptionist", "admin", "doctor"]:
        raise HTTPException(status_code=403, detail="Access denied")
    
    result = ReceptionistService.call_next_patient(doctor_id)
    if not result:
        raise HTTPException(status_code=404, detail="No patients in queue")
    
    return result


# --------------------------------------------------
# PATIENT SEARCH
# --------------------------------------------------

@app.get("/api/patients/search/{query}")
async def search_patients(query: str, current_user: dict = Depends(get_current_user)):
    """Search patients by name or phone"""
    if current_user.get("role") not in ["receptionist", "admin", "doctor"]:
        raise HTTPException(status_code=403, detail="Access denied")
    
    return ReceptionistService.search_patients(query)


# --------------------------------------------------
# NOTIFICATION ROUTES
# --------------------------------------------------

@app.get("/api/notifications")
async def get_notifications(limit: int = 50, current_user: dict = Depends(get_current_user)):
    """Get notifications for current user's role"""
    role = current_user.get("role", "receptionist")
    return ReceptionistService.get_notifications(role, limit)


@app.get("/api/notifications/unread/count")
async def get_unread_count(current_user: dict = Depends(get_current_user)):
    """Get count of unread notifications"""
    role = current_user.get("role", "receptionist")
    return {"unread_count": ReceptionistService.get_unread_count(role)}


@app.put("/api/notifications/{notification_id}/read")
async def mark_notification_read(notification_id: int, current_user: dict = Depends(get_current_user)):
    """Mark a notification as read"""
    result = ReceptionistService.mark_notification_read(notification_id)
    if not result:
        raise HTTPException(status_code=404, detail="Notification not found")
    return {"message": "Notification marked as read"}


@app.put("/api/notifications/read-all")
async def mark_all_notifications_read(current_user: dict = Depends(get_current_user)):
    """Mark all notifications as read for current user's role"""
    role = current_user.get("role", "receptionist")
    count = ReceptionistService.mark_all_notifications_read(role)
    return {"message": f"{count} notifications marked as read"}


# --------------------------------------------------
# ADMIN ROUTES
# --------------------------------------------------
@app.get("/api/admin/dashboard")
async def admin_dashboard(current_user: dict = Depends(get_current_user)):
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    return AdminService.get_dashboard_stats()


@app.get("/api/admin/staff")
async def get_all_staff(role: Optional[str] = None, department: Optional[str] = None, current_user: dict = Depends(get_current_user)):
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    staff = AdminService.get_all_staff(role, department)
    return staff or {"message": "No staff found"}


@app.get("/api/admin/staff/{staff_id}")
async def get_staff_by_id(staff_id: int, current_user: dict = Depends(get_current_user)):
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    staff = AdminService.get_staff_by_id(staff_id)
    if not staff:
        raise HTTPException(status_code=404, detail="Staff not found")
    return staff


@app.get("/api/admin/staff/employee/{staff_id_str}")
async def get_staff_by_staff_id(staff_id_str: str, current_user: dict = Depends(get_current_user)):
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    staff = AdminService.get_staff_by_staff_id(staff_id_str)
    if not staff:
        raise HTTPException(status_code=404, detail="Staff not found")
    return staff


@app.post("/api/admin/staff")
async def create_staff(staff_data: StaffCreate, current_user: dict = Depends(get_current_user)):
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    try:
        result = AdminService.create_staff(staff_data)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.put("/api/admin/staff/{staff_id}")
async def update_staff(staff_id: int, staff_update: StaffUpdate, current_user: dict = Depends(get_current_user)):
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    result = AdminService.update_staff(staff_id, staff_update)
    if not result:
        raise HTTPException(status_code=404, detail="Staff not found")
    
    return result


@app.delete("/api/admin/staff/{staff_id}")
async def delete_staff(staff_id: int, current_user: dict = Depends(get_current_user)):
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    # Get staff details before deletion for logging
    staff = AdminService.get_staff_by_id(staff_id)
    if not staff:
        raise HTTPException(status_code=404, detail="Staff not found")
    
    result = AdminService.delete_staff(staff_id)
    if not result:
        raise HTTPException(status_code=400, detail="Failed to delete staff")
    
    return {"message": "Staff deleted successfully"}


@app.get("/api/admin/staff/statistics")
async def get_staff_statistics(current_user: dict = Depends(get_current_user)):
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    return AdminService.get_staff_statistics()


@app.get("/api/admin/beds")
async def get_beds(current_user: dict = Depends(get_current_user)):
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    return AdminService.get_bed_status()


@app.post("/api/admin/beds/{bed_id}/assign")
async def assign_bed(bed_id: int, patient_id: int, current_user: dict = Depends(get_current_user)):
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    result = AdminService.assign_bed(bed_id, patient_id)
    if not result:
        raise HTTPException(status_code=400, detail="Bed not available or invalid")
    
    return result


@app.post("/api/admin/beds/{bed_id}/release")
async def release_bed(bed_id: int, current_user: dict = Depends(get_current_user)):
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    result = AdminService.release_bed(bed_id)
    if not result:
        raise HTTPException(status_code=400, detail="Bed not found or already empty")
    
    return result


@app.get("/api/admin/inventory")
async def get_inventory(current_user: dict = Depends(get_current_user)):
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    return AdminService.get_inventory_status()


@app.put("/api/admin/inventory/{item_id}")
async def update_inventory(item_id: int, quantity_change: int, current_user: dict = Depends(get_current_user)):
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    result = AdminService.update_inventory(item_id, quantity_change)
    if not result:
        raise HTTPException(status_code=404, detail="Inventory item not found")
    
    return result


@app.get("/api/admin/activity-logs")
async def get_activity_logs(limit: int = 10, current_user: dict = Depends(get_current_user)):
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    return AdminService.get_recent_activity(limit)


@app.get("/api/admin/records")
async def get_all_records(current_user: dict = Depends(get_current_user)):
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    return AdminService.get_all_records()


@app.get("/api/admin/reports/monthly")
async def generate_monthly_report(current_user: dict = Depends(get_current_user)):
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    return AdminService.generate_monthly_report()


# --------------------------------------------------
# RUN SERVER
# --------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.main:app", host="0.0.0.0", port=8000, reload=True)






"""
====================================================================================================
MASHAR HOSPITAL API - COMPLETE ROUTES & LOGIN CREDENTIALS
====================================================================================================

BASE URL: http://localhost:8000 | DOCS: http://localhost:8000/docs | REDOC: http://localhost:8000/redoc

----------------------------------------------------------------------------------------------------
LOGIN CREDENTIALS (Default Users)
----------------------------------------------------------------------------------------------------
POST /api/doctors/login
Content-Type: application/json

┌──────────────┬────────────┬─────────────────┬─────────────────┐
│ Role         │ Username   │ Password        │ Name            │
├──────────────┼────────────┼─────────────────┼─────────────────┤
│ Admin        │ A001       │ admin123        │ Admin User      │
│ Doctor       │ D001       │ doctor123       │ Dr. John Kamau  │
│ Receptionist │ R001       │ receptionist123 │ Mary Wanjiku    │
└──────────────┴────────────┴─────────────────┴─────────────────┘

Example Request:
{
    "username": "A001",
    "password": "admin123",
    "role": "admin"
}

----------------------------------------------------------------------------------------------------
PUBLIC ROUTES (No Authentication Required)
----------------------------------------------------------------------------------------------------

[ROOT & HEALTH]
────────────────────────────────────────────────────────────────────────────────────
GET    /                             - API root with links to documentation
GET    /api/health                   - Health check endpoint

[DOCTOR ROUTES]
────────────────────────────────────────────────────────────────────────────────────
POST   /api/doctors/login            - Authenticate user (returns JWT token)
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
POST   /api/queue/register             - Register patient to queue (params: patient_id, department, condition, priority, doctor_id)
GET    /api/queue/status               - Get queue statistics

[PRESCRIPTION ROUTES]
────────────────────────────────────────────────────────────────────────────────────
GET    /api/prescriptions              - Get prescriptions (filters: search, patient_id)
POST   /api/prescriptions              - Create prescription (params: patient_id, medication, instructions, dosage, duration, doctor_id)


----------------------------------------------------------------------------------------------------
PROTECTED ROUTES (Authentication Required)
----------------------------------------------------------------------------------------------------

[DOCTOR ROUTES - Any Authenticated User]
────────────────────────────────────────────────────────────────────────────────────
GET    /api/doctors/current            - Get currently logged-in user info

[RECEPTIONIST ROUTES - Receptionist or Admin]
────────────────────────────────────────────────────────────────────────────────────
GET    /api/receptionist/dashboard          - Receptionist dashboard statistics
POST   /api/receptionist/patients/quick      - Quick patient registration
GET    /api/receptionist/queue               - Get patients in queue (filter: department)
GET    /api/receptionists                     - Get all receptionists
GET    /api/receptionists/active              - Get only active receptionists
GET    /api/receptionists/{receptionist_id}   - Get receptionist by ID
GET    /api/receptionists/employee/{employee_id} - Get receptionist by employee ID

[QUEUE MANAGEMENT - Receptionist/Admin/Doctor]
────────────────────────────────────────────────────────────────────────────────────
GET    /api/queue/priority             - Get queue organized by priority (filter: department)
POST   /api/queue/next/{doctor_id}     - Call next patient for a doctor

[PATIENT SEARCH - Receptionist/Admin/Doctor]
────────────────────────────────────────────────────────────────────────────────────
GET    /api/patients/search/{query}    - Search patients by name or phone

[NOTIFICATION ROUTES - All Authenticated Users]
────────────────────────────────────────────────────────────────────────────────────
GET    /api/notifications               - Get notifications for current user's role (limit: 50)
GET    /api/notifications/unread/count  - Get count of unread notifications
PUT    /api/notifications/{notification_id}/read - Mark notification as read
PUT    /api/notifications/read-all       - Mark all notifications as read for current role

[PATIENT ROUTES - Admin Only]
────────────────────────────────────────────────────────────────────────────────────
DELETE /api/patients/{patient_id}       - Delete patient (Admin only)

[RECEPTIONIST MANAGEMENT - Admin Only]
────────────────────────────────────────────────────────────────────────────────────
POST   /api/receptionists                - Create new receptionist
PUT    /api/receptionists/{receptionist_id} - Update receptionist information
DELETE /api/receptionists/{receptionist_id} - Delete/Deactivate receptionist


----------------------------------------------------------------------------------------------------
ADMIN ONLY ROUTES
----------------------------------------------------------------------------------------------------

[DASHBOARD]
────────────────────────────────────────────────────────────────────────────────────
GET    /api/admin/dashboard              - Complete admin dashboard statistics

[STAFF MANAGEMENT]
────────────────────────────────────────────────────────────────────────────────────
GET    /api/admin/staff                  - Get all staff members (filters: role, department)
GET    /api/admin/staff/{staff_id}       - Get specific staff by ID
GET    /api/admin/staff/employee/{staff_id_str} - Get staff by employee ID (e.g., D001)
GET    /api/admin/staff/statistics       - Get staff statistics (counts by role, status)
POST   /api/admin/staff                  - Create new staff member
PUT    /api/admin/staff/{staff_id}       - Update staff information
DELETE /api/admin/staff/{staff_id}       - Delete staff member (soft delete)

[BED MANAGEMENT]
────────────────────────────────────────────────────────────────────────────────────
GET    /api/admin/beds                   - Get all beds with occupancy status
POST   /api/admin/beds/{bed_id}/assign   - Assign bed to patient (params: patient_id)
POST   /api/admin/beds/{bed_id}/release  - Release bed from patient

[INVENTORY MANAGEMENT]
────────────────────────────────────────────────────────────────────────────────────
GET    /api/admin/inventory              - Get all inventory items with status
PUT    /api/admin/inventory/{item_id}    - Update inventory quantity (params: quantity_change)

[ACTIVITY LOGS]
────────────────────────────────────────────────────────────────────────────────────
GET    /api/admin/activity-logs          - Get recent activity logs (limit: 10)

[RECORDS & REPORTS]
────────────────────────────────────────────────────────────────────────────────────
GET    /api/admin/records                - Get all records (doctors, nurses, patients)
GET    /api/admin/reports/monthly        - Generate monthly report with statistics


----------------------------------------------------------------------------------------------------
SUMMARY
----------------------------------------------------------------------------------------------------
Total Routes: 52
├── Public Routes: 15
└── Protected Routes: 37
    ├── Any Authenticated User: 5
    ├── Receptionist/Admin: 8
    ├── Receptionist/Admin/Doctor: 4
    └── Admin Only: 20

----------------------------------------------------------------------------------------------------
USAGE EXAMPLES
----------------------------------------------------------------------------------------------------

1. LOGIN AS ADMIN:
   curl -X POST http://localhost:8000/api/doctors/login \
     -H "Content-Type: application/json" \
     -d '{"username":"A001","password":"admin123","role":"admin"}'

2. ACCESS ADMIN DASHBOARD (with token):
   curl -X GET http://localhost:8000/api/admin/dashboard \
     -H "Authorization: Bearer <your_token_here>"

3. CREATE NEW STAFF (Admin only):
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

4. QUICK REGISTER PATIENT (Receptionist):
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

5. GET QUEUE BY PRIORITY:
   curl -X GET "http://localhost:8000/api/queue/priority?department=Cardiology" \
     -H "Authorization: Bearer <token>"

6. SEARCH PATIENTS:
   curl -X GET "http://localhost:8000/api/patients/search/John" \
     -H "Authorization: Bearer <token>"

7. CHECK NOTIFICATIONS:
   curl -X GET http://localhost:8000/api/notifications \
     -H "Authorization: Bearer <token>"

8. GENERATE MONTHLY REPORT (Admin):
   curl -X GET http://localhost:8000/api/admin/reports/monthly \
     -H "Authorization: Bearer <admin_token>"
   /api/admin/activity-logs   - Activity logs
"""
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer
from contextlib import asynccontextmanager
from typing import Optional, List
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
from jose import JWTError, jwt

from src.models.doctor import DoctorModel, DoctorCreate, DoctorLogin
from src.models.patients import Patient, PatientCreate, PatientUpdate
from src.services.patient_service import PatientService
from src.services.queue_manager import QueueManager
from src.models.admin import StaffCreate, StaffUpdate, StaffRole
from src.services.admin_service import AdminService
from src.models.patients import QuickRegistration, PatientCreate, NotificationType
from src.services.receptionist_service import ReceptionistService

load_dotenv()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print("Starting up...")
    QueueManager.initialize()
    yield
    # Shutdown
    print("Shutting down...")

app = FastAPI(
    title="Mashar Hospital Queue Management System",
    description="Backend API for hospital queue management",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Your frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token", auto_error=False)

# Helper function to get current user
async def get_current_user(token: str = Depends(oauth2_scheme)):
    if not token:
        return None
    
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, os.getenv("SECRET_KEY", "your-secret-key"), algorithms=["HS256"])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    user = DoctorModel.get_by_username(username)
    if user is None:
        raise credentials_exception
    return user

# Optional auth dependency
async def get_optional_user(token: str = Depends(oauth2_scheme)):
    if not token:
        return None
    try:
        payload = jwt.decode(token, os.getenv("SECRET_KEY", "your-secret-key"), algorithms=["HS256"])
        username: str = payload.get("sub")
        if username:
            return DoctorModel.get_by_username(username)
    except JWTError:
        pass
    return None

# Doctor routes
@app.post("/api/doctors/login")
async def doctor_login(login_data: DoctorLogin):
    """Doctor login endpoint"""
    result = DoctorModel.authenticate(login_data.username, login_data.password, login_data.role)
    if not result:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return result

@app.get("/api/doctors/current")
async def get_current_doctor(current_user: dict = Depends(get_current_user)):
    """Get currently logged in doctor"""
    return current_user

# Patient routes
@app.get("/api/patients")
async def get_patients(
    search: Optional[str] = None,
    status: Optional[str] = None,
    current_user: dict = Depends(get_optional_user)
):
    """Get all patients with optional filters"""
    return PatientService.get_patients(search, status)

@app.get("/api/patients/{patient_id}")
async def get_patient(
    patient_id: int,
    current_user: dict = Depends(get_optional_user)
):
    """Get patient by ID"""
    patient = PatientService.get_patient_by_id(patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    return patient

@app.post("/api/patients")
async def create_patient(
    patient: PatientCreate,
    current_user: dict = Depends(get_optional_user)
):
    """Create a new patient"""
    return PatientService.create_patient(patient)

@app.put("/api/patients/{patient_id}")
async def update_patient(
    patient_id: int,
    patient_update: PatientUpdate,
    current_user: dict = Depends(get_optional_user)
):
    """Update patient information"""
    result = PatientService.update_patient(patient_id, patient_update)
    if not result:
        raise HTTPException(status_code=404, detail="Patient not found")
    return result

@app.delete("/api/patients/{patient_id}")
async def delete_patient(
    patient_id: int,
    current_user: dict = Depends(get_current_user)
):
    """Delete a patient (admin only)"""
    if not current_user or current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Not authorized")
    
    result = PatientService.delete_patient(patient_id)
    if not result:
        raise HTTPException(status_code=404, detail="Patient not found")
    return {"message": "Patient deleted successfully"}

# Queue management routes
@app.get("/api/queue/current")
async def get_current_consultation(
    doctor_id: Optional[int] = None,
    department: Optional[str] = None
):
    """Get current consultation"""
    return QueueManager.get_current_consultation(doctor_id, department)

@app.get("/api/queue/waiting")
async def get_waiting_patients(
    doctor_id: Optional[int] = None,
    department: Optional[str] = "Cardiology"
):
    """Get waiting patients"""
    return QueueManager.get_waiting_patients(doctor_id, department)

@app.post("/api/queue/start/{consultation_id}")
async def start_consultation(
    consultation_id: int,
    doctor_id: int,
    current_user: dict = Depends(get_optional_user)
):
    """Start a consultation"""
    result = QueueManager.start_consultation(consultation_id, doctor_id)
    if not result:
        raise HTTPException(status_code=400, detail="Cannot start consultation")
    return result

@app.post("/api/queue/complete/{consultation_id}")
async def complete_consultation(
    consultation_id: int,
    medication: str,
    instructions: Optional[str] = None,
    dosage: Optional[str] = None,
    doctor_id: int = None,
    current_user: dict = Depends(get_optional_user)
):
    """Complete a consultation with prescription"""
    if not doctor_id and current_user:
        doctor_id = current_user.get("id")
    
    if not doctor_id:
        raise HTTPException(status_code=400, detail="Doctor ID required")
    
    result = QueueManager.complete_consultation(
        consultation_id, doctor_id, medication, instructions, dosage
    )
    if not result:
        raise HTTPException(status_code=400, detail="Cannot complete consultation")
    return result

@app.post("/api/queue/register")
async def register_patient_queue(
    patient_id: int,
    department: str = "Cardiology",
    condition: str = None,
    priority: int = 1,
    doctor_id: int = 1,
    current_user: dict = Depends(get_optional_user)
):
    """Register patient to queue"""
    try:
        result = QueueManager.add_to_queue(patient_id, department, condition, priority, doctor_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/queue/status")
async def get_queue_status():
    """Get queue statistics"""
    return QueueManager.get_queue_stats()

# Prescription routes
@app.get("/api/prescriptions")
async def get_prescriptions(
    search: Optional[str] = None,
    patient_id: Optional[int] = None,
    current_user: dict = Depends(get_optional_user)
):
    """Get prescriptions with filters"""
    return PatientService.get_prescriptions(search, patient_id)

@app.post("/api/prescriptions")
async def create_prescription(
    patient_id: int,
    medication: str,
    instructions: Optional[str] = None,
    dosage: Optional[str] = None,
    duration: Optional[str] = None,
    doctor_id: int = None,
    consultation_id: Optional[int] = None,
    current_user: dict = Depends(get_optional_user)
):
    """Create a new prescription"""
    if not doctor_id and current_user:
        doctor_id = current_user.get("id")
    
    if not doctor_id:
        raise HTTPException(status_code=400, detail="Doctor ID required")
    
    return PatientService.create_prescription(
        patient_id, doctor_id, medication, instructions, dosage, duration, consultation_id
    )

@app.get("/api/admin/dashboard")
async def get_admin_dashboard(current_user: dict = Depends(get_current_user)):
    """Get admin dashboard statistics"""
    if not current_user or current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    return AdminService.get_dashboard_stats()

# Staff Management
@app.get("/api/admin/staff")
async def get_all_staff(
    role: Optional[str] = None,
    department: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """Get all staff members"""
    if not current_user or current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    return AdminService.get_all_staff(role, department)

@app.get("/api/admin/staff/{staff_id}")
async def get_staff(
    staff_id: int,
    current_user: dict = Depends(get_current_user)
):
    """Get staff member by ID"""
    if not current_user or current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    staff = AdminService.get_staff_by_id(staff_id)
    if not staff:
        raise HTTPException(status_code=404, detail="Staff not found")
    return staff

@app.post("/api/admin/staff")
async def create_staff(
    staff_data: StaffCreate,
    current_user: dict = Depends(get_current_user)
):
    """Create a new staff member"""
    if not current_user or current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    try:
        return AdminService.create_staff(staff_data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.put("/api/admin/staff/{staff_id}")
async def update_staff(
    staff_id: int,
    staff_update: StaffUpdate,
    current_user: dict = Depends(get_current_user)
):
    """Update staff information"""
    if not current_user or current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    result = AdminService.update_staff(staff_id, staff_update)
    if not result:
        raise HTTPException(status_code=404, detail="Staff not found")
    return result

@app.delete("/api/admin/staff/{staff_id}")
async def delete_staff(
    staff_id: int,
    current_user: dict = Depends(get_current_user)
):
    """Delete/deactivate a staff member"""
    if not current_user or current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    result = AdminService.delete_staff(staff_id)
    if not result:
        raise HTTPException(status_code=404, detail="Staff not found")
    return {"message": "Staff member deactivated successfully"}

# Bed Management
@app.get("/api/admin/beds")
async def get_bed_status(current_user: dict = Depends(get_current_user)):
    """Get bed occupancy status"""
    if not current_user or current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    return AdminService.get_bed_status()

@app.post("/api/admin/beds/{bed_id}/assign/{patient_id}")
async def assign_bed(
    bed_id: int,
    patient_id: int,
    current_user: dict = Depends(get_current_user)
):
    """Assign a bed to a patient"""
    if not current_user or current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    result = AdminService.assign_bed(bed_id, patient_id)
    if not result:
        raise HTTPException(status_code=400, detail="Cannot assign bed")
    return result

@app.post("/api/admin/beds/{bed_id}/release")
async def release_bed(
    bed_id: int,
    current_user: dict = Depends(get_current_user)
):
    """Release a bed"""
    if not current_user or current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    result = AdminService.release_bed(bed_id)
    if not result:
        raise HTTPException(status_code=400, detail="Cannot release bed")
    return result

# Inventory Management
@app.get("/api/admin/inventory")
async def get_inventory_status(current_user: dict = Depends(get_current_user)):
    """Get inventory status"""
    if not current_user or current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    return AdminService.get_inventory_status()

@app.put("/api/admin/inventory/{item_id}")
async def update_inventory(
    item_id: int,
    quantity_change: int,
    current_user: dict = Depends(get_current_user)
):
    """Update inventory quantity"""
    if not current_user or current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    result = AdminService.update_inventory(item_id, quantity_change)
    if not result:
        raise HTTPException(status_code=404, detail="Item not found")
    return result

# Activity Log
@app.get("/api/admin/activity")
async def get_recent_activity(
    limit: int = 10,
    current_user: dict = Depends(get_current_user)
):
    """Get recent activity logs"""
    if not current_user or current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    return AdminService.get_recent_activity(limit)

# Records
@app.get("/api/admin/records")
async def get_all_records(current_user: dict = Depends(get_current_user)):
    """Get all hospital records"""
    if not current_user or current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    return AdminService.get_all_records()

# Reports
@app.post("/api/admin/reports/monthly")
async def generate_monthly_report(current_user: dict = Depends(get_current_user)):
    """Generate monthly report"""
    if not current_user or current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    return AdminService.generate_monthly_report()

# Staff Statistics
@app.get("/api/admin/staff/statistics")
async def get_staff_statistics(current_user: dict = Depends(get_current_user)):
    """Get staff statistics"""
    if not current_user or current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    return AdminService.get_staff_statistics()

# Statistics routes
@app.get("/api/statistics/weekly")
async def get_weekly_statistics(current_user: dict = Depends(get_optional_user)):
    """Get weekly statistics"""
    return PatientService.get_weekly_statistics()

@app.get("/api/statistics/doctor/{doctor_id}")
async def get_doctor_statistics(
    doctor_id: int,
    current_user: dict = Depends(get_optional_user)
):
    """Get statistics for specific doctor"""
    return PatientService.get_doctor_statistics(doctor_id)



# Health check
@app.get("/api/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

@app.get("/api/receptionist/dashboard")
async def get_receptionist_dashboard(current_user: dict = Depends(get_current_user)):
    """Get receptionist dashboard statistics"""
    if not current_user or current_user.get("role") not in ["receptionist", "admin"]:
        raise HTTPException(status_code=403, detail="Receptionist access required")
    
    return ReceptionistService.get_dashboard_stats()

# Patient Registration
@app.post("/api/receptionist/patients/quick")
async def quick_register_patient(
    registration: QuickRegistration,
    current_user: dict = Depends(get_current_user)
):
    """Quick register a patient and add to queue"""
    if not current_user or current_user.get("role") not in ["receptionist", "admin"]:
        raise HTTPException(status_code=403, detail="Receptionist access required")
    
    return ReceptionistService.quick_register_patient(registration, current_user.get("id", 0))

@app.post("/api/receptionist/patients")
async def register_patient(
    patient_data: PatientCreate,
    current_user: dict = Depends(get_current_user)
):
    """Register a new patient (full registration)"""
    if not current_user or current_user.get("role") not in ["receptionist", "admin"]:
        raise HTTPException(status_code=403, detail="Receptionist access required")
    
    return ReceptionistService.register_patient(patient_data, current_user.get("id", 0))

# Queue Management
@app.get("/api/receptionist/queue")
async def get_queue(
    department: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """Get full queue list"""
    if not current_user or current_user.get("role") not in ["receptionist", "admin", "doctor"]:
        raise HTTPException(status_code=403, detail="Access required")
    
    return ReceptionistService.get_patients_in_queue()

@app.put("/api/receptionist/queue/{consultation_id}/priority")
async def update_queue_priority(
    consultation_id: int,
    priority: int,
    current_user: dict = Depends(get_current_user)
):
    """Update patient priority in queue"""
    if not current_user or current_user.get("role") not in ["receptionist", "admin"]:
        raise HTTPException(status_code=403, detail="Receptionist access required")
    
    result = ReceptionistService.update_queue_priority(consultation_id, priority)
    if not result:
        raise HTTPException(status_code=404, detail="Consultation not found or not in queue")
    return result

@app.delete("/api/receptionist/queue/{consultation_id}")
async def remove_from_queue(
    consultation_id: int,
    current_user: dict = Depends(get_current_user)
):
    """Remove patient from queue"""
    if not current_user or current_user.get("role") not in ["receptionist", "admin"]:
        raise HTTPException(status_code=403, detail="Receptionist access required")
    
    result = ReceptionistService.remove_from_queue(consultation_id)
    if not result:
        raise HTTPException(status_code=404, detail="Consultation not found or not in queue")
    return {"message": "Patient removed from queue"}

# Patient Search
@app.get("/api/receptionist/patients/search")
async def search_patients(
    q: str,
    current_user: dict = Depends(get_current_user)
):
    """Search patients by name or phone"""
    if not current_user or current_user.get("role") not in ["receptionist", "admin", "doctor"]:
        raise HTTPException(status_code=403, detail="Access required")
    
    return ReceptionistService.search_patients(q)

# Recent Patients
@app.get("/api/receptionist/patients/recent")
async def get_recent_patients(
    limit: int = 10,
    current_user: dict = Depends(get_current_user)
):
    """Get recently registered patients"""
    if not current_user or current_user.get("role") not in ["receptionist", "admin", "doctor"]:
        raise HTTPException(status_code=403, detail="Access required")
    
    return ReceptionistService.get_recent_patients(limit)

# Notifications
@app.get("/api/receptionist/notifications")
async def get_notifications(
    limit: int = 20,
    current_user: dict = Depends(get_current_user)
):
    """Get notifications for receptionist"""
    if not current_user or current_user.get("role") not in ["receptionist", "admin", "doctor"]:
        raise HTTPException(status_code=403, detail="Access required")
    
    return ReceptionistService.get_notifications(current_user.get("role", "receptionist"), limit)

@app.get("/api/receptionist/notifications/unread")
async def get_unread_count(current_user: dict = Depends(get_current_user)):
    """Get unread notifications count"""
    if not current_user or current_user.get("role") not in ["receptionist", "admin", "doctor"]:
        raise HTTPException(status_code=403, detail="Access required")
    
    return {"unread_count": ReceptionistService.get_unread_count(current_user.get("role", "receptionist"))}

@app.put("/api/receptionist/notifications/{notification_id}/read")
async def mark_notification_read(
    notification_id: int,
    current_user: dict = Depends(get_current_user)
):
    """Mark a notification as read"""
    if not current_user or current_user.get("role") not in ["receptionist", "admin", "doctor"]:
        raise HTTPException(status_code=403, detail="Access required")
    
    result = ReceptionistService.mark_notification_read(notification_id)
    if not result:
        raise HTTPException(status_code=404, detail="Notification not found")
    return {"message": "Notification marked as read"}

@app.put("/api/receptionist/notifications/read-all")
async def mark_all_notifications_read(current_user: dict = Depends(get_current_user)):
    """Mark all notifications as read"""
    if not current_user or current_user.get("role") not in ["receptionist", "admin", "doctor"]:
        raise HTTPException(status_code=403, detail="Access required")
    
    count = ReceptionistService.mark_all_notifications_read(current_user.get("role", "receptionist"))
    return {"message": f"{count} notifications marked as read"}

# Quick Stats
@app.get("/api/receptionist/stats/quick")
async def get_quick_stats(current_user: dict = Depends(get_current_user)):
    """Get quick statistics for receptionist"""
    if not current_user or current_user.get("role") not in ["receptionist", "admin"]:
        raise HTTPException(status_code=403, detail="Receptionist access required")
    
    return ReceptionistService.get_quick_stats()

# System Notifications (for creating notifications from other services)
@app.post("/api/notifications")
async def create_system_notification(
    message: str,
    type: str = "info",
    role_target: str = "all",
    current_user: dict = Depends(get_current_user)
):
    """Create a system notification (can be called by any service)"""
    if not current_user:
        raise HTTPException(status_code=403, detail="Authentication required")
    
    return ReceptionistService.create_notification(
        user_id=current_user.get("id"),
        user_name=current_user.get("name"),
        message=message,
        type=type,
        role_target=role_target
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)






# 📋 COMPLETE API ROUTES LIST

# 
# Base URL: http://localhost:8000
# 
# 🔐 AUTHENTICATION ROUTES
# ------------------------
# POST   /api/doctors/login                 - Login with username, password, and role
# GET    /api/doctors/current                - Get currently logged in user info
# GET    /api/health                         - Health check endpoint
# 
# 👨‍⚕️ DOCTOR ROUTES
# -----------------
# GET    /api/doctor/dashboard                - Get doctor's dashboard with current and waiting patients
# GET    /api/queue/current                   - Get current consultation (optional doctor_id, department)
# GET    /api/queue/waiting                    - Get waiting patients (optional doctor_id, department)
# POST   /api/queue/start/{consultation_id}    - Start a consultation
# POST   /api/queue/complete/{consultation_id} - Complete consultation with prescription
# GET    /api/statistics/doctor/{doctor_id}    - Get statistics for specific doctor
# 
# 🧑‍💼 RECEPTIONIST ROUTES
# -----------------------
# GET    /api/receptionist/dashboard                - Get receptionist dashboard statistics
# POST   /api/receptionist/patients/quick           - Quick register a patient and add to queue
# POST   /api/receptionist/patients                  - Register a new patient (full registration)
# GET    /api/receptionist/queue                     - Get full queue list with patient details
# PUT    /api/receptionist/queue/{id}/priority       - Update patient priority in queue
# DELETE /api/receptionist/queue/{id}                - Remove patient from queue
# GET    /api/receptionist/patients/search           - Search patients by name or phone
# GET    /api/receptionist/patients/recent           - Get recently registered patients
# GET    /api/receptionist/stats/quick               - Get quick statistics for receptionist
# GET    /api/receptionist/departments               - Get list of departments
# GET    /api/receptionist/department/{dept}/queue   - Get queue for specific department
# 
# 🔔 NOTIFICATION ROUTES
# ----------------------
# GET    /api/receptionist/notifications             - Get notifications for receptionist
# GET    /api/receptionist/notifications/unread      - Get unread notifications count
# PUT    /api/receptionist/notifications/{id}/read   - Mark a notification as read
# PUT    /api/receptionist/notifications/read-all    - Mark all notifications as read
# POST   /api/notifications                          - Create a system notification
# 
# 👤 PATIENT ROUTES
# -----------------
# GET    /api/patients                               - Get all patients with optional filters
# GET    /api/patients/{patient_id}                  - Get patient by ID with consultation history
# POST   /api/patients                               - Create a new patient
# PUT    /api/patients/{patient_id}                  - Update patient information
# DELETE /api/patients/{patient_id}                   - Delete a patient (admin only)
# GET    /api/patients/{id}/queue-status             - Get queue status for a specific patient
# 
# 💊 PRESCRIPTION ROUTES
# ----------------------
# GET    /api/prescriptions                          - Get prescriptions with filters
# POST   /api/prescriptions                          - Create a new prescription
# 
# 📊 QUEUE MANAGEMENT ROUTES
# --------------------------
# GET    /api/queue/status                           - Get queue statistics
# GET    /api/queue/history                          - Get historical queue data
# PUT    /api/queue/reassign/{consultation_id}       - Reassign consultation to another doctor
# 
# 📈 STATISTICS ROUTES
# --------------------
# GET    /api/statistics/weekly                      - Get weekly statistics
# GET    /api/statistics/doctor/{doctor_id}          - Get statistics for specific doctor
# 
# 👑 ADMIN ROUTES
# ---------------
# GET    /api/admin/dashboard                        - Get admin dashboard statistics
# GET    /api/admin/staff                            - Get all staff members
# GET    /api/admin/staff/{staff_id}                 - Get staff member by ID
# POST   /api/admin/staff                            - Create a new staff member
# PUT    /api/admin/staff/{staff_id}                 - Update staff information
# DELETE /api/admin/staff/{staff_id}                  - Delete/deactivate a staff member
# GET    /api/admin/staff/statistics                 - Get staff statistics
# 
# 🛏️ BED MANAGEMENT ROUTES (ADMIN)
# ---------------------------------
# GET    /api/admin/beds                             - Get bed occupancy status
# POST   /api/admin/beds/{bed_id}/assign/{patient_id} - Assign a bed to a patient
# POST   /api/admin/beds/{bed_id}/release            - Release a bed
# 
# 📦 INVENTORY ROUTES (ADMIN)
# ---------------------------
# GET    /api/admin/inventory                        - Get inventory status
# PUT    /api/admin/inventory/{item_id}              - Update inventory quantity
# 
# 📋 RECORDS ROUTES (ADMIN)
# -------------------------
# GET    /api/admin/activity                         - Get recent activity logs
# GET    /api/admin/records                          - Get all hospital records
# POST   /api/admin/reports/monthly                  - Generate monthly report

# 📊 SUMMARY

# Total Routes: 60+ 
# - Authentication: 3
# - Doctor: 7
# - Receptionist: 13
# - Notifications: 5
# - Patient: 6
# - Prescriptions: 2
# - Queue Management: 4
# - Statistics: 2
# - Admin: 18
# 

# 🚀 HOW TO RUN THE SERVER

# 
# 1. Activate virtual environment:
#    source venv/bin/activate
# 
# 2. Start the server:
#    uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
# 
#    Or with custom port:
#    uvicorn src.main:app --reload --port 8000
# 
# 3. For production (without reload):
#    uvicorn src.main:app --host 0.0.0.0 --port 8000
# 

# 📚 API DOCUMENTATION

# 
# Once server is running, visit:
# 🔹 Swagger UI: http://localhost:8000/docs
# 🔹 ReDoc:      http://localhost:8000/redoc
# 

# 🔑 DEFAULT LOGIN CREDENTIALS

# 
# 👑 Admin:
#    Username: admin1
#    Password: admin123
#    Role: admin
# 
# 👨‍⚕️ Doctor:
#    Username: doctor1
#    Password: doc123
#    Role: doctor
# 
# 🧑‍💼 Receptionist:
#    Username: receptionist1
#    Password: rec123
#    Role: receptionist

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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
from fastapi import FastAPI, Depends, HTTPException, status, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer
from contextlib import asynccontextmanager
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
from jose import JWTError, jwt

# Models
from src.models.doctor import DoctorModel, DoctorLogin
from src.models.patients import (
    PatientCreate, PatientUpdate, QuickRegistration, 
    NotificationType, PatientService as PatientModelService
)
from src.models.admin import StaffCreate, StaffUpdate, StaffRole, StaffStatus, AdminModel, StaffLogin
from src.models.receptionist import ReceptionistCreate, ReceptionistUpdate, ReceptionistModel, ReceptionistLogin

# Services
from src.services.patient_service import PatientService
from src.services.queue_manager import QueueManager
from src.services.admin_service import AdminService
from src.services.receptionist_service import ReceptionistService

load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY", "change-this-secret-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30


# --------------------------------------------------
# APPLICATION LIFESPAN
# --------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events"""
    print("🚀 Starting up Mashar Hospital API...")
    
    # Initialize Queue Manager
    QueueManager.initialize()
    
    # Get queue stats
    queue_stats = QueueManager.get_queue_stats()
    print(f"✅ Queue Manager initialized. Current queue: {queue_stats.get('waiting', 0)} waiting, {queue_stats.get('in_progress', 0)} in progress")
    
    # Load sample data counts
    from src.models.patients import patients_db, consultations_db, notifications_db
    print(f"📊 Loaded {len(patients_db)} patients, {len(consultations_db)} consultations, {len(notifications_db)} notifications")
    
    yield
    
    print("🛑 Shutting down Mashar Hospital API...")
    print("✅ Shutdown complete")


app = FastAPI(
    title="Mashar Hospital Queue Management System",
    description="Backend API for hospital queue management with role-based access control",
    version="2.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    contact={
        "name": "Mashar Hospital",
        "email": "info@masharhospital.com",
    },
    license_info={
        "name": "MIT",
    }
)


# --------------------------------------------------
# CORS CONFIGURATION
# --------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5000",
        "http://127.0.0.1:5000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)


# --------------------------------------------------
# JWT TOKEN UTILITIES
# --------------------------------------------------
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Create JWT access token"""
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({
        "exp": expire,
        "iat": datetime.utcnow(),
        "type": "access"
    })
    
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str):
    """Decode and verify JWT token"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )


# --------------------------------------------------
# AUTHENTICATION DEPENDENCIES
# --------------------------------------------------
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/login", auto_error=False)


async def get_current_user(token: str = Depends(oauth2_scheme)):
    """Get current user from JWT token"""
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    try:
        payload = decode_token(token)
        username = payload.get("sub")
        
        if not username:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: missing subject",
            )
        
        # Try to get user from different models
        user = None
        
        # Try doctor model
        user = DoctorModel.get_by_username(username)
        
        # Try admin model
        if not user:
            user = AdminModel.get_staff_by_staff_id(username)
            if user:
                user["role"] = user.get("role", "admin")
        
        # Try receptionist model
        if not user:
            user = ReceptionistModel.get_by_employee_id(username)
            if user:
                user["role"] = "receptionist"
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )
        
        return user
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error in get_current_user: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication error",
        )


async def get_optional_user(token: str = Depends(oauth2_scheme)):
    """Get current user if token exists, otherwise return None"""
    if not token:
        return None
    
    try:
        payload = decode_token(token)
        username = payload.get("sub")
        
        if username:
            # Try doctor model
            user = DoctorModel.get_by_username(username)
            
            # Try admin model
            if not user:
                user = AdminModel.get_staff_by_staff_id(username)
                if user:
                    user["role"] = user.get("role", "admin")
            
            # Try receptionist model
            if not user:
                user = ReceptionistModel.get_by_employee_id(username)
                if user:
                    user["role"] = "receptionist"
            
            return user
    except Exception:
        return None
    
    return None


async def get_admin_user(current_user: dict = Depends(get_current_user)):
    """Ensure user is an admin"""
    if current_user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return current_user


async def get_receptionist_or_admin(current_user: dict = Depends(get_current_user)):
    """Ensure user is a receptionist or admin"""
    if current_user.get("role") not in ["receptionist", "admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Receptionist or admin access required",
        )
    return current_user


async def get_medical_staff(current_user: dict = Depends(get_current_user)):
    """Ensure user is medical staff (doctor, nurse) or admin"""
    if current_user.get("role") not in ["doctor", "nurse", "admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Medical staff access required",
        )
    return current_user


# --------------------------------------------------
# ROOT & HEALTH CHECK
# --------------------------------------------------
@app.get("/")
async def root():
    """API root endpoint with links to documentation"""
    return {
        "success": True,
        "message": "Mashar Hospital API is running",
        "docs": "http://localhost:8000/docs",
        "redoc": "http://localhost:8000/redoc",
        "health": "http://localhost:8000/api/health",
        "version": "2.0.0",
        "endpoints": {
            "login": "/api/login",
            "doctor_login": "/api/doctors/login",
            "admin_login": "/api/admin/login",
            "receptionist_login": "/api/receptionist/login",
            "notifications": "/api/notifications"
        }
    }


@app.get("/api/health")
async def health_check():
    """Health check endpoint with queue status"""
    queue_stats = QueueManager.get_queue_stats()
    return {
        "success": True,
        "status": "healthy", 
        "timestamp": datetime.now().isoformat(),
        "queue_status": queue_stats,
        "uptime": "online"
    }


# --------------------------------------------------
# UNIVERSAL LOGIN ENDPOINT
# --------------------------------------------------
@app.post("/api/login")
async def universal_login(request: Request):
    """
    Universal login endpoint that works for all user types.
    Accepts username/employee_id/staff_id and password.
    Role is optional - system will auto-detect.
    """
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON body",
        )
    
    username = body.get("username") or body.get("employee_id") or body.get("staff_id")
    password = body.get("password")
    role = body.get("role")  # Optional
    
    if not username or not password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username and password are required",
        )
    
    print(f"Universal login attempt - Username: {username}, Role provided: {role}")
    
    # Try doctor authentication
    doctor_result = DoctorModel.authenticate(username, password, role)
    if doctor_result:
        print(f"Login successful as doctor: {username}")
        return doctor_result
    
    # Try admin authentication
    admin_result = AdminModel.authenticate(username, password, role)
    if admin_result:
        print(f"Login successful as admin: {username}")
        # Generate JWT token
        token = create_access_token({"sub": username, "role": "admin"})
        return {
            "access_token": token,
            "token_type": "bearer",
            "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            "user": admin_result["user"]
        }
    
    # Try receptionist authentication
    receptionist_result = ReceptionistModel.authenticate(username, password, role)
    if receptionist_result:
        print(f"Login successful as receptionist: {username}")
        # Generate JWT token
        token = create_access_token({"sub": username, "role": "receptionist"})
        return {
            "access_token": token,
            "token_type": "bearer",
            "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            "user": receptionist_result["user"]
        }
    
    print(f"Authentication failed for user: {username}")
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid credentials. Please check your username and password.",
    )


# --------------------------------------------------
# DOCTOR ROUTES
# --------------------------------------------------
@app.post("/api/doctors/login")
async def doctor_login(login_data: DoctorLogin):
    """
    Doctor login endpoint.
    Role is optional - system will auto-detect.
    """
    print(f"Doctor login received - Username: {login_data.username}, Role provided: {login_data.role}")
    
    result = DoctorModel.authenticate(login_data.username, login_data.password, login_data.role)
    
    if not result:
        print(f"Authentication failed for doctor: {login_data.username}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials. Please check your username and password.",
        )
    
    print(f"Login successful for doctor: {login_data.username}")
    return result


@app.get("/api/doctors/current")
async def get_current_doctor(current_user: dict = Depends(get_current_user)):
    """Get currently logged-in doctor/user"""
    return {
        "success": True,
        "user": current_user
    }


@app.get("/api/doctors")
async def get_doctors(current_user: dict = Depends(get_optional_user)):
    """Get all doctors (public or authenticated)"""
    doctors = DoctorModel.get_all_doctors()
    return {
        "success": True,
        "doctors": doctors,
        "total": len(doctors)
    }


@app.get("/api/doctors/{doctor_id}")
async def get_doctor_by_id(doctor_id: int):
    """Get specific doctor by ID"""
    doctor = DoctorModel.get_doctor_by_id(doctor_id)
    if not doctor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Doctor not found",
        )
    return {
        "success": True,
        "doctor": doctor
    }


# --------------------------------------------------
# ADMIN ROUTES
# --------------------------------------------------
@app.post("/api/admin/login")
async def admin_login(login_data: StaffLogin):
    """
    Admin login endpoint.
    Role is optional - system will auto-detect.
    """
    print(f"Admin login received - Staff ID: {login_data.staff_id}, Role provided: {login_data.role}")
    
    result = AdminModel.authenticate(login_data.staff_id, login_data.password, login_data.role)
    
    if not result:
        print(f"Authentication failed for admin: {login_data.staff_id}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials. Please check your staff ID and password.",
        )
    
    print(f"Login successful for admin: {login_data.staff_id}")
    
    # Generate JWT token for admin
    token = create_access_token({"sub": login_data.staff_id, "role": "admin"})
    
    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        "user": result["user"]
    }


@app.get("/api/admin/dashboard")
async def admin_dashboard(current_user: dict = Depends(get_admin_user)):
    """Get admin dashboard statistics"""
    stats = AdminModel.get_dashboard_stats()
    return {
        "success": True,
        **stats
    }


@app.get("/api/admin/staff")
async def get_all_staff(
    role: Optional[str] = None, 
    department: Optional[str] = None, 
    current_user: dict = Depends(get_admin_user)
):
    """Get all staff members with optional filters"""
    staff = AdminModel.get_all_staff(role, department)
    return {
        "success": True,
        "staff": staff,
        "total": len(staff)
    }


@app.get("/api/admin/staff/{staff_id}")
async def get_staff_by_id(staff_id: int, current_user: dict = Depends(get_admin_user)):
    """Get staff member by database ID"""
    staff = AdminModel.get_staff_by_id(staff_id)
    if not staff:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Staff not found",
        )
    return {
        "success": True,
        "staff": staff
    }


@app.get("/api/admin/staff/employee/{staff_id_str}")
async def get_staff_by_staff_id(staff_id_str: str, current_user: dict = Depends(get_admin_user)):
    """Get staff member by employee ID (e.g., D001, A001)"""
    staff = AdminModel.get_staff_by_staff_id(staff_id_str)
    if not staff:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Staff not found",
        )
    return {
        "success": True,
        "staff": staff
    }


@app.post("/api/admin/staff")
async def create_staff(staff_data: StaffCreate, current_user: dict = Depends(get_admin_user)):
    """Create a new staff member"""
    try:
        result = AdminModel.create_staff(staff_data)
        return {
            "success": True,
            "staff": result,
            "message": f"Staff {staff_data.name} created successfully"
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@app.put("/api/admin/staff/{staff_id}")
async def update_staff(staff_id: int, staff_update: StaffUpdate, current_user: dict = Depends(get_admin_user)):
    """Update staff member information"""
    result = AdminModel.update_staff(staff_id, staff_update)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Staff not found",
        )
    
    return {
        "success": True,
        "staff": result,
        "message": "Staff updated successfully"
    }


@app.delete("/api/admin/staff/{staff_id}")
async def delete_staff(staff_id: int, current_user: dict = Depends(get_admin_user)):
    """Delete/deactivate staff member"""
    # Get staff details before deletion for logging
    staff = AdminModel.get_staff_by_id(staff_id)
    if not staff:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Staff not found",
        )
    
    result = AdminModel.delete_staff(staff_id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to delete staff",
        )
    
    return {
        "success": True,
        "message": f"Staff {staff['name']} deleted successfully"
    }


@app.get("/api/admin/staff/statistics")
async def get_staff_statistics(current_user: dict = Depends(get_admin_user)):
    """Get staff statistics"""
    stats = AdminModel.get_staff_statistics()
    return {
        "success": True,
        **stats
    }


@app.get("/api/admin/beds")
async def get_beds(current_user: dict = Depends(get_admin_user)):
    """Get all beds with occupancy status"""
    beds = AdminModel.get_beds()
    stats = AdminModel.get_bed_status()
    return {
        "success": True,
        "beds": beds,
        "statistics": stats
    }


@app.post("/api/admin/beds/{bed_id}/assign")
async def assign_bed(bed_id: int, patient_id: int, current_user: dict = Depends(get_admin_user)):
    """Assign a bed to a patient"""
    result = AdminModel.assign_bed(bed_id, patient_id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bed not available or invalid",
        )
    
    return {
        "success": True,
        "bed": result,
        "message": f"Bed {bed_id} assigned to patient {patient_id}"
    }


@app.post("/api/admin/beds/{bed_id}/release")
async def release_bed(bed_id: int, current_user: dict = Depends(get_admin_user)):
    """Release a bed from a patient"""
    result = AdminModel.release_bed(bed_id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bed not found or already empty",
        )
    
    return {
        "success": True,
        "bed": result,
        "message": f"Bed {bed_id} released"
    }


@app.get("/api/admin/inventory")
async def get_inventory(current_user: dict = Depends(get_admin_user)):
    """Get inventory items"""
    items = AdminModel.get_inventory()
    status = AdminModel.get_inventory_status()
    return {
        "success": True,
        "items": items,
        "status": status
    }


@app.put("/api/admin/inventory/{item_id}")
async def update_inventory(item_id: int, quantity_change: int, current_user: dict = Depends(get_admin_user)):
    """Update inventory item quantity"""
    result = AdminModel.update_inventory(item_id, quantity_change)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Inventory item not found",
        )
    
    return {
        "success": True,
        "item": result,
        "message": f"Inventory item updated"
    }


@app.get("/api/admin/activity-logs")
async def get_activity_logs(limit: int = 20, current_user: dict = Depends(get_admin_user)):
    """Get recent activity logs"""
    logs = AdminModel.get_activity_logs(limit)
    return {
        "success": True,
        "logs": logs,
        "total": len(logs)
    }


@app.get("/api/admin/records")
async def get_all_records(current_user: dict = Depends(get_admin_user)):
    """Get all records for admin overview"""
    records = AdminModel.get_all_records()
    return {
        "success": True,
        **records
    }


@app.get("/api/admin/reports/monthly")
async def generate_monthly_report(current_user: dict = Depends(get_admin_user)):
    """Generate monthly report"""
    report = AdminModel.generate_monthly_report()
    return {
        "success": True,
        "report": report
    }


# --------------------------------------------------
# RECEPTIONIST ROUTES
# --------------------------------------------------
@app.post("/api/receptionist/login")
async def receptionist_login(login_data: ReceptionistLogin):
    """
    Receptionist login endpoint.
    Role is optional - defaults to receptionist.
    """
    print(f"Receptionist login received - Employee ID: {login_data.employee_id}, Role: {login_data.role}")
    
    result = ReceptionistModel.authenticate(login_data.employee_id, login_data.password, login_data.role)
    
    if not result:
        print(f"Authentication failed for receptionist: {login_data.employee_id}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials. Please check your employee ID and password.",
        )
    
    print(f"Login successful for receptionist: {login_data.employee_id}")
    
    # Generate JWT token for receptionist
    token = create_access_token({"sub": login_data.employee_id, "role": "receptionist"})
    
    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        "user": result["user"]
    }


@app.get("/api/receptionist/dashboard")
async def get_receptionist_dashboard(current_user: dict = Depends(get_receptionist_or_admin)):
    """Get receptionist dashboard statistics"""
    result = ReceptionistService.get_dashboard_stats()
    return {
        "success": True,
        **result
    }


@app.post("/api/receptionist/patients/quick")
async def quick_register_patient(
    registration: QuickRegistration, 
    current_user: dict = Depends(get_receptionist_or_admin)
):
    """Quick register a new patient"""
    try:
        # Add receptionist name to registration
        registration.receptionist_name = current_user.get("name", "Receptionist")
        
        # Log the received data for debugging
        print(f"Quick registration received: {registration.dict()}")
        
        result = ReceptionistService.quick_register_patient(
            registration, 
            current_user.get("id", 0)
        )
        
        return result
        
    except Exception as e:
        print(f"Error in quick registration: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@app.get("/api/receptionist/queue")
async def get_receptionist_queue(
    department: Optional[str] = None, 
    current_user: dict = Depends(get_receptionist_or_admin)
):
    """Get patients in queue"""
    result = ReceptionistService.get_patients_in_queue(department)
    return {
        "success": True,
        **result
    }


# --------------------------------------------------
# RECEPTIONIST MANAGEMENT ROUTES
# --------------------------------------------------
@app.get("/api/receptionists")
async def get_all_receptionists(current_user: dict = Depends(get_receptionist_or_admin)):
    """Get all receptionists (Active and Inactive)"""
    result = ReceptionistService.get_all_receptionists()
    return result


@app.get("/api/receptionists/active")
async def get_active_receptionists(current_user: dict = Depends(get_receptionist_or_admin)):
    """Get only active receptionists"""
    result = ReceptionistService.get_active_receptionists()
    return result


@app.get("/api/receptionists/{receptionist_id}")
async def get_receptionist_by_id(receptionist_id: int, current_user: dict = Depends(get_receptionist_or_admin)):
    """Get receptionist by database ID"""
    result = ReceptionistService.get_receptionist_by_id(receptionist_id)
    if not result.get("success"):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=result.get("error", "Receptionist not found"),
        )
    return result


@app.get("/api/receptionists/employee/{employee_id}")
async def get_receptionist_by_employee_id(employee_id: str, current_user: dict = Depends(get_receptionist_or_admin)):
    """Get receptionist by employee ID"""
    result = ReceptionistService.get_receptionist_by_employee_id(employee_id)
    if not result.get("success"):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=result.get("error", "Receptionist not found"),
        )
    return result


@app.post("/api/receptionists")
async def create_receptionist(
    receptionist_data: ReceptionistCreate, 
    current_user: dict = Depends(get_admin_user)  # Admin only
):
    """Create a new receptionist (Admin only)"""
    result = ReceptionistService.create_receptionist(receptionist_data)
    if not result.get("success"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.get("error", "Failed to create receptionist"),
        )
    
    return result


@app.put("/api/receptionists/{receptionist_id}")
async def update_receptionist(
    receptionist_id: int, 
    receptionist_update: ReceptionistUpdate, 
    current_user: dict = Depends(get_admin_user)  # Admin only
):
    """Update receptionist information (Admin only)"""
    result = ReceptionistService.update_receptionist(receptionist_id, receptionist_update)
    if not result.get("success"):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=result.get("error", "Receptionist not found"),
        )
    
    return result


@app.delete("/api/receptionists/{receptionist_id}")
async def delete_receptionist(
    receptionist_id: int, 
    current_user: dict = Depends(get_admin_user)  # Admin only
):
    """Delete/Deactivate receptionist (Admin only)"""
    result = ReceptionistService.delete_receptionist(receptionist_id)
    if not result.get("success"):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=result.get("error", "Receptionist not found"),
        )
    
    return result


# --------------------------------------------------
# PATIENT ROUTES
# --------------------------------------------------
@app.get("/api/patients")
async def get_patients(
    search: Optional[str] = None, 
    status: Optional[str] = None, 
    current_user: dict = Depends(get_optional_user)
):
    """Get all patients with optional filters"""
    patients = PatientService.get_patients(search, status)
    return {
        "success": True,
        "patients": patients,
        "total": len(patients)
    }


@app.get("/api/patients/{patient_id}")
async def get_patient(patient_id: int):
    """Get specific patient by ID"""
    patient = PatientService.get_patient_by_id(patient_id)
    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient not found",
        )
    return {
        "success": True,
        "patient": patient
    }


@app.post("/api/patients")
async def create_patient(patient: PatientCreate):
    """Create a new patient"""
    result = PatientService.create_patient(patient)
    return result


@app.put("/api/patients/{patient_id}")
async def update_patient(patient_id: int, patient_update: PatientUpdate):
    """Update patient information"""
    result = PatientService.update_patient(patient_id, patient_update)
    if not result.get("success"):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=result.get("error", "Patient not found"),
        )
    return result


@app.delete("/api/patients/{patient_id}")
async def delete_patient(patient_id: int, current_user: dict = Depends(get_admin_user)):
    """Delete patient (Admin only)"""
    result = PatientService.delete_patient(patient_id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient not found",
        )
    return {
        "success": True,
        "message": "Patient deleted successfully"
    }


@app.get("/api/patients/search/{query}")
async def search_patients(query: str, current_user: dict = Depends(get_medical_staff)):
    """Search patients by name or phone"""
    result = ReceptionistService.search_patients(query)
    return result


# --------------------------------------------------
# QUEUE ROUTES
# --------------------------------------------------
@app.get("/api/queue/current")
async def get_current_consultation(
    doctor_id: Optional[int] = None, 
    department: Optional[str] = None
):
    """Get current consultation"""
    result = QueueManager.get_current_consultation(doctor_id, department)
    return {
        "success": True,
        "consultation": result
    }


@app.get("/api/queue/waiting")
async def get_waiting_patients(
    doctor_id: Optional[int] = None, 
    department: Optional[str] = "Cardiology"
):
    """Get waiting patients"""
    result = QueueManager.get_waiting_patients(doctor_id, department)
    return {
        "success": True,
        "waiting": result,
        "total": len(result)
    }


@app.post("/api/queue/register")
async def register_patient_queue(
    patient_id: int, 
    department: str = "Cardiology", 
    condition: Optional[str] = None, 
    priority: int = 1, 
    doctor_id: int = 1
):
    """Register patient to queue"""
    try:
        result = QueueManager.add_to_queue(patient_id, department, condition, priority, doctor_id)
        return {
            "success": True,
            **result
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@app.get("/api/queue/status")
async def get_queue_status():
    """Get queue statistics"""
    stats = QueueManager.get_queue_stats()
    return {
        "success": True,
        **stats
    }


@app.get("/api/queue/priority")
async def get_queue_by_priority(
    department: Optional[str] = None, 
    current_user: dict = Depends(get_medical_staff)
):
    """Get queue organized by priority"""
    result = ReceptionistService.get_queue_by_priority(department)
    return {
        "success": True,
        **result
    }


@app.post("/api/queue/next/{doctor_id}")
async def call_next_patient(
    doctor_id: int, 
    current_user: dict = Depends(get_medical_staff)
):
    """Call the next patient for a doctor"""
    result = ReceptionistService.call_next_patient(doctor_id)
    if not result.get("success"):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=result.get("error", "No patients in queue"),
        )
    
    return result


# --------------------------------------------------
# PRESCRIPTIONS
# --------------------------------------------------
@app.get("/api/prescriptions")
async def get_prescriptions(
    search: Optional[str] = None, 
    patient_id: Optional[int] = None
):
    """Get prescriptions"""
    prescriptions = PatientService.get_prescriptions(search, patient_id)
    return {
        "success": True,
        "prescriptions": prescriptions,
        "total": len(prescriptions)
    }


@app.post("/api/prescriptions")
async def create_prescription(
    patient_id: int, 
    medication: str, 
    instructions: Optional[str] = None, 
    dosage: Optional[str] = None, 
    duration: Optional[str] = None, 
    doctor_id: Optional[int] = None
):
    """Create a new prescription"""
    if not doctor_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Doctor ID required",
        )
    
    result = PatientService.create_prescription(
        patient_id, doctor_id, medication, instructions, dosage, duration
    )
    return result


# --------------------------------------------------
# NOTIFICATION ROUTES - FIXED FOR FRONTEND
# --------------------------------------------------
@app.get("/api/notifications")
async def get_notifications(
    limit: int = 50, 
    current_user: dict = Depends(get_current_user)
):
    """
    Get notifications for current user's role.
    Returns a consistent format that works with the frontend.
    """
    try:
        role = current_user.get("role", "receptionist")
        result = ReceptionistService.get_notifications(role, limit)
        
        # Ensure we return a format that the frontend can handle
        if isinstance(result, dict) and result.get("success"):
            # If service returns success flag with notifications array
            return {
                "success": True,
                "notifications": result.get("notifications", []),
                "unread_count": result.get("unread_count", 0),
                "total": result.get("total", 0)
            }
        elif isinstance(result, list):
            # If service returns array directly
            unread = sum(1 for n in result if not n.get("read", False))
            return {
                "success": True,
                "notifications": result[:limit],
                "unread_count": unread,
                "total": len(result)
            }
        elif isinstance(result, dict) and "notifications" in result:
            # If result already has notifications field
            return {
                "success": True,
                "notifications": result["notifications"],
                "unread_count": result.get("unread_count", 0),
                "total": result.get("total", len(result["notifications"]))
            }
        else:
            # Fallback to empty array
            return {
                "success": True,
                "notifications": [],
                "unread_count": 0,
                "total": 0
            }
    except Exception as e:
        print(f"Error in get_notifications endpoint: {str(e)}")
        # Return empty array on error so frontend doesn't break
        return {
            "success": False,
            "notifications": [],
            "unread_count": 0,
            "total": 0,
            "error": str(e)
        }


@app.get("/api/notifications/unread/count")
async def get_unread_count(current_user: dict = Depends(get_current_user)):
    """Get count of unread notifications"""
    try:
        role = current_user.get("role", "receptionist")
        result = ReceptionistService.get_unread_count(role)
        
        # Handle different response formats
        if isinstance(result, dict):
            if "unread_count" in result:
                return {
                    "success": True,
                    "unread_count": result["unread_count"]
                }
            elif "count" in result:
                return {
                    "success": True,
                    "unread_count": result["count"]
                }
        
        # If result is a number
        if isinstance(result, int):
            return {
                "success": True,
                "unread_count": result
            }
        
        # Fallback
        return {
            "success": True,
            "unread_count": 0
        }
    except Exception as e:
        print(f"Error in get_unread_count endpoint: {str(e)}")
        return {
            "success": False,
            "unread_count": 0,
            "error": str(e)
        }


@app.put("/api/notifications/{notification_id}/read")
async def mark_notification_read(
    notification_id: int, 
    current_user: dict = Depends(get_current_user)
):
    """Mark a notification as read"""
    try:
        result = ReceptionistService.mark_notification_read(notification_id)
        
        if isinstance(result, dict) and not result.get("success", True):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=result.get("error", "Notification not found"),
            )
        
        return {
            "success": True,
            "message": "Notification marked as read"
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error marking notification as read: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@app.put("/api/notifications/read-all")
async def mark_all_notifications_read(current_user: dict = Depends(get_current_user)):
    """Mark all notifications as read for current user's role"""
    try:
        role = current_user.get("role", "receptionist")
        result = ReceptionistService.mark_all_notifications_read(role)
        
        if isinstance(result, dict):
            count = result.get("marked_count", 0)
        else:
            count = result
        
        return {
            "success": True,
            "marked_count": count,
            "message": f"{count} notifications marked as read"
        }
    except Exception as e:
        print(f"Error marking all notifications as read: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


# --------------------------------------------------
# DEBUG ENDPOINTS
# --------------------------------------------------
@app.post("/api/debug/login")
async def debug_login(request: Request):
    """
    Debug endpoint to see what the frontend is sending.
    Remove this in production!
    """
    try:
        body = await request.json()
    except:
        body = {}
    
    print("=== DEBUG LOGIN ===")
    print("Received data:", body)
    
    # Get available users from different models
    doctors = DoctorModel.get_all_doctors()
    admins = AdminModel.get_all_staff()
    receptionists = ReceptionistModel.get_all_receptionists()
    
    print("Available doctors:", [{"username": d["username"], "role": "doctor"} for d in doctors])
    print("Available admins:", [{"staff_id": a["staff_id"], "role": a["role"], "name": a["name"]} for a in admins])
    print("Available receptionists:", [{"employee_id": r["employee_id"], "role": "receptionist", "name": r["name"]} for r in receptionists])
    print("===================")
    
    # Try to authenticate
    username = body.get("username") or body.get("employee_id") or body.get("staff_id")
    password = body.get("password")
    role = body.get("role")
    
    auth_result = None
    auth_model = None
    
    if username and password:
        # Try doctor
        auth_result = DoctorModel.authenticate(username, password, role)
        if auth_result:
            auth_model = "doctor"
        
        # Try admin
        if not auth_result:
            admin_result = AdminModel.authenticate(username, password, role)
            if admin_result:
                auth_result = admin_result
                auth_model = "admin"
        
        # Try receptionist
        if not auth_result:
            rec_result = ReceptionistModel.authenticate(username, password, role)
            if rec_result:
                auth_result = rec_result
                auth_model = "receptionist"
    
    return {
        "received": body,
        "authentication_success": auth_result is not None,
        "authenticated_as": auth_model,
        "available_users": {
            "doctors": len(doctors),
            "admins": len(admins),
            "receptionists": len(receptionists)
        },
        "message": "Check console for details"
    }


@app.get("/api/debug/users")
async def debug_users():
    """List all available users (debug only)"""
    doctors = DoctorModel.get_all_doctors()
    admins = AdminModel.get_all_staff()
    receptionists = ReceptionistModel.get_all_receptionists()
    
    return {
        "doctors": [{"username": d["username"], "name": d["name"], "role": "doctor"} for d in doctors],
        "admins": [{"staff_id": a["staff_id"], "name": a["name"], "role": a["role"]} for a in admins],
        "receptionists": [{"employee_id": r["employee_id"], "name": r["name"], "role": "receptionist"} for r in receptionists]
    }


@app.get("/api/debug/notifications")
async def debug_notifications():
    """Debug endpoint to check notifications data structure"""
    try:
        from src.services.receptionist_service import notifications_db
        return {
            "success": True,
            "notifications": notifications_db[-20:],  # Last 20 notifications
            "total": len(notifications_db),
            "structure": "Array of notification objects"
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


# --------------------------------------------------
# RUN SERVER
# --------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "src.main:app", 
        host="0.0.0.0", 
        port=8000, 
        reload=True,
        log_level="info"
    )






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
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from src.models.admin import (
    staff_db, beds_db, inventory_db, activity_log_db,
    Staff, StaffCreate, StaffUpdate, StaffRole, StaffStatus,
    Bed, InventoryItem, ActivityLog, next_staff_id, next_activity_id
)
from src.models.doctor import DoctorModel, hash_password

class AdminService:
    
    # ========== Staff Management ==========
    
    @staticmethod
    def get_all_staff(role: Optional[str] = None, department: Optional[str] = None) -> List[Dict]:
        """Get all staff members with optional filters"""
        staff_list = []
        
        for staff in staff_db.values():
            if role and staff["role"] != role:
                continue
            if department and staff.get("department") != department:
                continue
            
            staff_list.append(staff)
        
        return sorted(staff_list, key=lambda x: x["name"])

    @staticmethod
    def get_staff_by_id(staff_id: int) -> Optional[Dict]:
        """Get staff member by ID"""
        return staff_db.get(staff_id)

    @staticmethod
    def get_staff_by_staff_id(staff_id_str: str) -> Optional[Dict]:
        """Get staff member by staff ID (e.g., D001)"""
        for staff in staff_db.values():
            if staff["staff_id"] == staff_id_str:
                return staff
        return None

    @staticmethod
    def create_staff(staff_data: StaffCreate) -> Dict:
        """Create a new staff member"""
        global next_staff_id
        
        # Check if staff_id already exists
        for staff in staff_db.values():
            if staff["staff_id"] == staff_data.staff_id:
                raise ValueError(f"Staff ID {staff_data.staff_id} already exists")
        
        new_staff = {
            "id": next_staff_id,
            **staff_data.dict(exclude={"password"}),
            "status": StaffStatus.ACTIVE,
            "joining_date": staff_data.joining_date or datetime.now(),
            "created_at": datetime.now(),
            "updated_at": None,
            "last_login": None
        }
        
        # Also create user account for login
        from src.models.doctor import doctors_db
        doctor_id = max(doctors_db.keys()) + 1 if doctors_db else 1
        
        doctors_db[doctor_id] = {
            "id": doctor_id,
            "username": staff_data.staff_id,
            "name": staff_data.name,
            "role": staff_data.role,
            "department": staff_data.department,
            "specialization": staff_data.specialization,
            "hashed_password": hash_password(staff_data.password),
            "is_active": True,
            "created_at": datetime.now(),
            "last_login": None
        }
        
        staff_db[next_staff_id] = new_staff
        next_staff_id += 1
        
        # Log activity
        AdminService.log_activity(
            user_id=1,  # Admin user
            user_name="Admin",
            role="admin",
            action="create_staff",
            details=f"Created new staff: {staff_data.name} ({staff_data.role})"
        )
        
        return new_staff

    @staticmethod
    def update_staff(staff_id: int, staff_update: StaffUpdate) -> Optional[Dict]:
        """Update staff information"""
        if staff_id not in staff_db:
            return None
        
        staff = staff_db[staff_id]
        update_data = staff_update.dict(exclude_unset=True)
        
        for key, value in update_data.items():
            if value is not None:
                staff[key] = value
        
        staff["updated_at"] = datetime.now()
        
        # Update corresponding user account
        from src.models.doctor import doctors_db
        for user in doctors_db.values():
            if user.get("username") == staff["staff_id"]:
                if "name" in update_data:
                    user["name"] = update_data["name"]
                if "department" in update_data:
                    user["department"] = update_data["department"]
                if "specialization" in update_data:
                    user["specialization"] = update_data["specialization"]
                break
        
        return staff

    @staticmethod
    def delete_staff(staff_id: int) -> bool:
        """Delete a staff member (soft delete or permanent)"""
        if staff_id not in staff_db:
            return False
        
        # Soft delete - mark as inactive
        staff_db[staff_id]["status"] = StaffStatus.INACTIVE
        staff_db[staff_id]["updated_at"] = datetime.now()
        
        return True

    @staticmethod
    def get_staff_statistics() -> Dict:
        """Get staff statistics"""
        total_doctors = len([s for s in staff_db.values() if s["role"] == "doctor"])
        total_nurses = len([s for s in staff_db.values() if s["role"] == "nurse"])
        total_receptionists = len([s for s in staff_db.values() if s["role"] == "receptionist"])
        
        active_doctors = len([
            s for s in staff_db.values() 
            if s["role"] == "doctor" and s["status"] == "active"
        ])
        
        active_nurses = len([
            s for s in staff_db.values() 
            if s["role"] == "nurse" and s["status"] == "active"
        ])
        
        on_leave = len([s for s in staff_db.values() if s["status"] == "on_leave"])
        
        return {
            "total_doctors": total_doctors,
            "total_nurses": total_nurses,
            "total_receptionists": total_receptionists,
            "total_staff": len(staff_db),
            "active_doctors": active_doctors,
            "active_nurses": active_nurses,
            "on_leave": on_leave,
            "inactive": len([s for s in staff_db.values() if s["status"] == "inactive"])
        }

    # ========== Bed Management ==========
    
    @staticmethod
    def get_bed_status() -> Dict:
        """Get bed occupancy status"""
        total_beds = len(beds_db)
        occupied_beds = len([b for b in beds_db if b["is_occupied"]])
        available_beds = total_beds - occupied_beds
        
        # Beds by department
        beds_by_dept = {}
        for bed in beds_db:
            dept = bed["department"]
            if dept not in beds_by_dept:
                beds_by_dept[dept] = {"total": 0, "occupied": 0, "available": 0}
            
            beds_by_dept[dept]["total"] += 1
            if bed["is_occupied"]:
                beds_by_dept[dept]["occupied"] += 1
            else:
                beds_by_dept[dept]["available"] += 1
        
        return {
            "total_beds": total_beds,
            "occupied_beds": occupied_beds,
            "available_beds": available_beds,
            "occupancy_rate": round((occupied_beds / total_beds) * 100, 1),
            "by_department": beds_by_dept
        }

    @staticmethod
    def assign_bed(bed_id: int, patient_id: int) -> Optional[Dict]:
        """Assign a bed to a patient"""
        bed = next((b for b in beds_db if b["id"] == bed_id), None)
        if not bed or bed["is_occupied"]:
            return None
        
        bed["is_occupied"] = True
        bed["patient_id"] = patient_id
        bed["assigned_at"] = datetime.now()
        
        return bed

    @staticmethod
    def release_bed(bed_id: int) -> Optional[Dict]:
        """Release a bed"""
        bed = next((b for b in beds_db if b["id"] == bed_id), None)
        if not bed or not bed["is_occupied"]:
            return None
        
        bed["is_occupied"] = False
        bed["patient_id"] = None
        bed["assigned_at"] = None
        
        return bed

    # ========== Inventory Management ==========
    
    @staticmethod
    def get_inventory_status() -> Dict:
        """Get inventory status"""
        total_items = len(inventory_db)
        
        # Stock level status
        low_stock = []
        for item in inventory_db.values():
            if item["quantity"] <= item["reorder_level"]:
                low_stock.append(item)
        
        # Count by category
        by_category = {}
        for item in inventory_db.values():
            cat = item["category"]
            if cat not in by_category:
                by_category[cat] = {"count": 0, "items": []}
            by_category[cat]["count"] += 1
            by_category[cat]["items"].append(item)
        
        # Overall stock level
        total_quantity = sum(item["quantity"] for item in inventory_db.values())
        
        return {
            "total_items": total_items,
            "total_quantity": total_quantity,
            "low_stock_count": len(low_stock),
            "low_stock_items": low_stock,
            "by_category": by_category,
            "status": "Good" if len(low_stock) < 3 else "Reorder Needed"
        }

    @staticmethod
    def update_inventory(item_id: int, quantity_change: int) -> Optional[Dict]:
        """Update inventory quantity"""
        if item_id not in inventory_db:
            return None
        
        item = inventory_db[item_id]
        item["quantity"] += quantity_change
        item["last_restocked"] = datetime.now() if quantity_change > 0 else item["last_restocked"]
        
        return item

    # ========== Activity Log ==========
    
    @staticmethod
    def log_activity(user_id: int, user_name: str, role: str, action: str, details: str) -> Dict:
        """Log an activity"""
        global next_activity_id
        
        log_entry = {
            "id": next_activity_id,
            "user_id": user_id,
            "user_name": user_name,
            "role": role,
            "action": action,
            "details": details,
            "timestamp": datetime.now()
        }
        
        activity_log_db.append(log_entry)
        next_activity_id += 1
        
        return log_entry

    @staticmethod
    def get_recent_activity(limit: int = 10) -> List[Dict]:
        """Get recent activity logs"""
        return sorted(activity_log_db, key=lambda x: x["timestamp"], reverse=True)[:limit]

    # ========== Dashboard Statistics ==========
    
    @staticmethod
    def get_dashboard_stats() -> Dict:
        """Get all statistics for admin dashboard"""
        staff_stats = AdminService.get_staff_statistics()
        bed_stats = AdminService.get_bed_status()
        inventory_stats = AdminService.get_inventory_status()
        recent_activity = AdminService.get_recent_activity(5)
        
        # Patient statistics from patients_db
        from src.models.patients import patients_db, consultations_db
        total_patients = len(patients_db)
        
        # Today's patients
        today_start = datetime.now().replace(hour=0, minute=0, second=0)
        patients_today = len([
            c for c in consultations_db.values()
            if c["created_at"] >= today_start
        ])
        
        # Currently in hospital (in progress or waiting)
        current_patients = len([
            c for c in consultations_db.values()
            if c["status"] in ["in_progress", "waiting"]
        ])
        
        return {
            "staff": staff_stats,
            "beds": bed_stats,
            "inventory": inventory_stats,
            "patients": {
                "total": total_patients,
                "today": patients_today,
                "current": current_patients,
                "discharged_today": len([
                    c for c in consultations_db.values()
                    if c["status"] == "treated" and c["completed_at"] and c["completed_at"] >= today_start
                ])
            },
            "recent_activity": recent_activity,
            "last_updated": datetime.now().isoformat()
        }

    # ========== Records Management ==========
    
    @staticmethod
    def get_all_records() -> Dict:
        """Get all records for display"""
        from src.models.patients import patients_db
        
        # Get all doctors
        doctors = [
            {
                "id": s["staff_id"],
                "name": s["name"],
                "specialty": s.get("specialization", "General"),
                "phone": s["phone"],
                "department": s["department"]
            }
            for s in staff_db.values()
            if s["role"] == "doctor" and s["status"] == "active"
        ]
        
        # Get all nurses
        nurses = [
            {
                "id": s["staff_id"],
                "name": s["name"],
                "department": s["department"],
                "phone": s["phone"]
            }
            for s in staff_db.values()
            if s["role"] == "nurse" and s["status"] == "active"
        ]
        
        # Get all patients
        patients = [
            {
                "id": f"P{str(p['id']).zfill(3)}",
                "name": p["name"],
                "condition": AdminService._get_patient_condition(p["id"]),
                "phone": p.get("phone", "N/A")
            }
            for p in patients_db.values()
        ]
        
        return {
            "doctors": doctors,
            "nurses": nurses,
            "patients": patients,
            "total_doctors": len(doctors),
            "total_nurses": len(nurses),
            "total_patients": len(patients)
        }

    @staticmethod
    def _get_patient_condition(patient_id: int) -> str:
        """Helper to get patient's current condition"""
        from src.models.patients import consultations_db
        
        for consultation in consultations_db.values():
            if consultation["patient_id"] == patient_id:
                return consultation["condition"]
        return "Not specified"

    # ========== Report Generation ==========
    
    @staticmethod
    def generate_monthly_report() -> Dict:
        """Generate monthly report"""
        month_start = datetime.now().replace(day=1, hour=0, minute=0, second=0)
        
        from src.models.patients import consultations_db
        
        # Monthly consultations
        monthly_consultations = [
            c for c in consultations_db.values()
            if c["created_at"] >= month_start
        ]
        
        # By doctor
        by_doctor = {}
        for consultation in monthly_consultations:
            doctor_id = consultation["doctor_id"]
            doctor_name = next(
                (s["name"] for s in staff_db.values() if s["id"] == doctor_id),
                f"Doctor {doctor_id}"
            )
            
            if doctor_name not in by_doctor:
                by_doctor[doctor_name] = 0
            by_doctor[doctor_name] += 1
        
        # By department
        by_department = {}
        for consultation in monthly_consultations:
            dept = consultation["department"]
            if dept not in by_department:
                by_department[dept] = 0
            by_department[dept] += 1
        
        # Log report generation
        AdminService.log_activity(
            user_id=1,
            user_name="Admin",
            role="admin",
            action="generate_report",
            details="Generated monthly report"
        )
        
        return {
            "month": month_start.strftime("%B %Y"),
            "generated_at": datetime.now().isoformat(),
            "total_consultations": len(monthly_consultations),
            "by_doctor": by_doctor,
            "by_department": by_department,
            "average_per_day": round(len(monthly_consultations) / 30, 1),
            "peak_day": max(set([c["created_at"].day for c in monthly_consultations]), 
                           key=list([c["created_at"].day for c in monthly_consultations]).count)
        }
from typing import Optional, List, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session
from src.models.admin import (
    Staff, StaffCreate, StaffUpdate, StaffRole, StaffStatus,
    Bed, InventoryItem, ActivityLog, AdminModel
)

class AdminService:
    
    # ========== Staff Management ==========
    
    @staticmethod
    def get_all_staff(db: Session, role: Optional[str] = None, department: Optional[str] = None) -> List[Staff]:
        """Get all staff members from the database with optional filtering"""
        return AdminModel.get_all_staff(role=role, department=department, db=db)

    @staticmethod
    def get_staff_by_id(db: Session, staff_id: int) -> Optional[Staff]:
        """Get staff member by primary key ID"""
        return AdminModel.get_staff_by_id(staff_id, db=db)

    @staticmethod
    def get_staff_by_staff_id(db: Session, staff_id_str: str) -> Optional[Staff]:
        """Get staff member by public staff ID (e.g., D001)"""
        return AdminModel.get_staff_by_staff_id(staff_id_str, db=db)

    @staticmethod
    def create_staff(db: Session, staff_data: StaffCreate) -> Staff:
        """Create a new staff member and handle DB persistence"""
        # AdminModel.create_staff handles password hashing and activity logging
        return AdminModel.create_staff(staff_data, db=db)

    @staticmethod
    def update_staff(db: Session, staff_id: int, staff_update: StaffUpdate) -> Optional[Staff]:
        """Update staff information in the database"""
        return AdminModel.update_staff(staff_id, staff_update, db=db)

    @staticmethod
    def delete_staff(db: Session, staff_id: int) -> bool:
        """Deactivate a staff member (Soft Delete)"""
        return AdminModel.delete_staff(staff_id, db=db)

    # ========== Bed Management ==========
    
    @staticmethod
    def get_bed_status(db: Session) -> Dict:
        """Get bed occupancy status statistics"""
        return AdminModel.get_bed_status(db=db)

    @staticmethod
    def assign_bed(db: Session, bed_id: int, patient_id: int) -> Optional[Bed]:
        """Assign a bed to a patient via ORM"""
        return AdminModel.assign_bed(bed_id, patient_id, db=db)

    @staticmethod
    def release_bed(db: Session, bed_id: int) -> Optional[Bed]:
        """Release an occupied bed"""
        return AdminModel.release_bed(bed_id, db=db)

    # ========== Inventory Management ==========
    
    @staticmethod
    def get_inventory_status(db: Session) -> Dict:
        """Get inventory stock levels and low-stock alerts"""
        return AdminModel.get_inventory_status(db=db)

    @staticmethod
    def update_inventory(db: Session, item_id: int, quantity_change: int) -> Optional[InventoryItem]:
        """Update quantity levels for a specific inventory item"""
        return AdminModel.update_inventory(item_id, quantity_change, db=db)

    # ========== Activity Log ==========
    
    @staticmethod
    def log_activity(db: Session, user_id: int, user_name: str, role: str, action: str, details: str):
        """Manually log a system or user activity"""
        AdminModel.log_activity(
            user_id=user_id, 
            user_name=user_name, 
            action=action, 
            details=details, 
            role=role, 
            db=db
        )

    @staticmethod
    def get_recent_activity(db: Session, limit: int = 10) -> List[ActivityLog]:
        """Fetch the most recent system activity logs"""
        return AdminModel.get_activity_logs(limit=limit, db=db)

    # ========== Dashboard Statistics ==========
    
    @staticmethod
    def get_dashboard_stats(db: Session) -> Dict:
        """Retrieve aggregated data for the Admin Dashboard"""
        staff_stats = AdminModel.get_staff_statistics(db)
        bed_stats = AdminModel.get_bed_status(db)
        inv_stats = AdminModel.get_inventory_status(db)
        
        # Pulling recent logs and converting to dictionary for frontend ease
        logs = AdminModel.get_activity_logs(limit=5, db=db)
        recent_activity = [
            {
                "user": log.user_name,
                "action": log.action,
                "time": log.timestamp.isoformat(),
                "details": log.details
            } for log in logs
        ]

        return {
            "staff": staff_stats,
            "beds": bed_stats,
            "inventory": inv_stats,
            "recent_activity": recent_activity,
            "server_time": datetime.now().isoformat()
        }  
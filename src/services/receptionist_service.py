from typing import Optional, List, Dict
from datetime import datetime
from src.models.receptionist import (
    receptionist_db,
    ReceptionistCreate,
    ReceptionistUpdate,
    ReceptionistModel
)
from src.models.patients import (
    patients_db,
    consultations_db,
    QuickRegistration,
    NotificationType,
    notifications_db
)
from src.services.queue_manager import QueueManager

# Global counter for notifications
next_notification_id = len(notifications_db) + 1 if notifications_db else 1

class ReceptionistService:

    # ----------------------
    # Dashboard stats
    # ----------------------
    @staticmethod
    def get_dashboard_stats() -> Dict:
        try:
            queue_stats = QueueManager.get_queue_stats()
            today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            registered_today = len([
                c for c in consultations_db.values()
                if c.get("created_at") and c["created_at"] >= today_start
            ])
            
            # Get waiting patients by department
            waiting_by_dept = {}
            for consultation in consultations_db.values():
                if consultation.get("status") == "waiting":
                    dept = consultation.get("department", "General")
                    waiting_by_dept[dept] = waiting_by_dept.get(dept, 0) + 1
            
            return {
                "total_in_queue": queue_stats.get("waiting", 0),
                "registered_today": registered_today,
                "in_progress": queue_stats.get("in_progress", 0),
                "waiting_by_department": waiting_by_dept,
                "average_wait_time": queue_stats.get("average_wait_time", 0)
            }
        except Exception as e:
            print(f"Error in get_dashboard_stats: {e}")
            return {
                "total_in_queue": 0,
                "registered_today": 0,
                "in_progress": 0,
                "waiting_by_department": {},
                "average_wait_time": 0
            }

    # ----------------------
    # Receptionist CRUD
    # ----------------------
    @staticmethod
    def create_receptionist(data: ReceptionistCreate) -> Dict:
        """Create a new receptionist"""
        try:
            return ReceptionistModel.create_receptionist(data)
        except Exception as e:
            print(f"Error creating receptionist: {e}")
            return {"success": False, "error": str(e)}

    @staticmethod
    def update_receptionist(r_id: int, data: ReceptionistUpdate) -> Optional[Dict]:
        """Update receptionist information"""
        try:
            return ReceptionistModel.update_receptionist(r_id, data)
        except Exception as e:
            print(f"Error updating receptionist: {e}")
            return None

    @staticmethod
    def get_all_receptionists() -> List[Dict]:
        """Get all receptionists"""
        try:
            return ReceptionistModel.get_all()
        except Exception as e:
            print(f"Error getting receptionists: {e}")
            return []

    @staticmethod
    def get_receptionist_by_id(r_id: int) -> Optional[Dict]:
        """Get receptionist by ID"""
        try:
            return ReceptionistModel.get_by_id(r_id)
        except Exception as e:
            print(f"Error getting receptionist: {e}")
            return None

    @staticmethod
    def delete_receptionist(r_id: int) -> bool:
        """Delete receptionist (soft delete)"""
        try:
            return ReceptionistModel.delete_receptionist(r_id)
        except Exception as e:
            print(f"Error deleting receptionist: {e}")
            return False

    @staticmethod
    def get_active_receptionists() -> List[Dict]:
        """Get all active receptionists"""
        try:
            all_receptionists = ReceptionistModel.get_all()
            return [r for r in all_receptionists if r.get("status") == "active"]
        except Exception as e:
            print(f"Error getting active receptionists: {e}")
            return []

    @staticmethod
    def get_receptionist_by_employee_id(employee_id: str) -> Optional[Dict]:
        """Get receptionist by employee ID"""
        try:
            for receptionist in ReceptionistModel.get_all():
                if receptionist.get("employee_id") == employee_id:
                    return receptionist
            return None
        except Exception as e:
            print(f"Error getting receptionist by employee ID: {e}")
            return None

    # ----------------------
    # Quick Patient Registration
    # ----------------------
    @staticmethod
    def quick_register_patient(registration: QuickRegistration, receptionist_id: int) -> Dict:
        """Quickly register a new patient and add to queue"""
        try:
            if not registration.patient_name or not registration.phone:
                return {
                    "success": False, 
                    "error": "Patient name and phone are required",
                    "patient_id": None,
                    "queue_number": None
                }

            # Check if patient exists
            existing_patient = None
            for p in patients_db.values():
                if p.get("phone") == registration.phone:
                    existing_patient = p
                    break

            if existing_patient:
                patient_id = existing_patient["id"]
                is_new = False
            else:
                patient_id = max(patients_db.keys(), default=0) + 1
                patients_db[patient_id] = {
                    "id": patient_id,
                    "name": registration.patient_name,
                    "phone": registration.phone,
                    "age": registration.age,
                    "gender": registration.gender,
                    "email": None,
                    "address": None,
                    "emergency_contact": registration.emergency_contact,
                    "created_at": datetime.now(),
                    "updated_at": None,
                    "created_by": receptionist_id
                }
                is_new = True

            # Add to queue
            result = QueueManager.add_to_queue(
                patient_id=patient_id,
                department=registration.department or "General",
                condition=registration.condition or "General checkup",
                priority=registration.priority or 3,
                doctor_id=registration.doctor_id or 1,
                room=registration.room or "Waiting Area"
            )

            if result.get("success"):
                # Create notification
                queue_number = result.get('consultation', {}).get('queue_number', 'N/A')
                ReceptionistService.create_notification(
                    user_id=receptionist_id,
                    user_name=registration.receptionist_name or "Receptionist",
                    message=f"Patient {registration.patient_name} registered in queue #{queue_number}",
                    type=NotificationType.INFO,
                    role_target="all"
                )

                return {
                    "success": True,
                    "patient_id": patient_id,
                    "queue_number": queue_number,
                    "position": result.get('consultation', {}).get('position', 0),
                    "estimated_wait_time": result.get('consultation', {}).get('estimated_wait_time', 0),
                    "is_new_patient": is_new,
                    "message": f"Patient registered successfully in queue #{queue_number}"
                }
            else:
                return {
                    "success": False,
                    "error": result.get("error", "Failed to add to queue"),
                    "patient_id": patient_id,
                    "queue_number": None,
                    "is_new_patient": is_new
                }

        except Exception as e:
            print(f"Error in quick_register_patient: {e}")
            return {
                "success": False, 
                "error": str(e),
                "patient_id": None,
                "queue_number": None
            }

    # ----------------------
    # Queue Management
    # ----------------------
    @staticmethod
    def get_patients_in_queue(department: Optional[str] = None) -> List[Dict]:
        """Get patients currently in queue"""
        try:
            waiting_patients = QueueManager.get_waiting_patients(department=department)
            
            # Enhance with patient details
            enhanced_list = []
            for item in waiting_patients:
                patient = patients_db.get(item.get("patient_id"))
                if patient:
                    enhanced_list.append({
                        **item,
                        "patient_name": patient.get("name", "Unknown"),
                        "patient_phone": patient.get("phone", "N/A"),
                        "patient_age": patient.get("age", "N/A"),
                        "patient_gender": patient.get("gender", "N/A"),
                        "registered_by": item.get("created_by", "Receptionist")
                    })
            
            return enhanced_list
        except Exception as e:
            print(f"Error getting patients in queue: {e}")
            return []

    @staticmethod
    def get_queue_by_priority(department: Optional[str] = None) -> Dict:
        """Get queue organized by priority"""
        try:
            queue = QueueManager.get_waiting_patients(department=department)
            
            priority_groups = {
                "emergency": [],    # Priority 1
                "urgent": [],       # Priority 2
                "normal": [],       # Priority 3
                "non_urgent": []    # Priority 4
            }
            
            for item in queue:
                priority = item.get("priority", 3)
                patient = patients_db.get(item.get("patient_id"))
                
                enhanced_item = {
                    **item,
                    "patient_name": patient.get("name", "Unknown") if patient else "Unknown"
                }
                
                if priority == 1:
                    priority_groups["emergency"].append(enhanced_item)
                elif priority == 2:
                    priority_groups["urgent"].append(enhanced_item)
                elif priority == 3:
                    priority_groups["normal"].append(enhanced_item)
                else:
                    priority_groups["non_urgent"].append(enhanced_item)
            
            return priority_groups
        except Exception as e:
            print(f"Error getting queue by priority: {e}")
            return {
                "emergency": [],
                "urgent": [],
                "normal": [],
                "non_urgent": []
            }

    @staticmethod
    def call_next_patient(doctor_id: int) -> Optional[Dict]:
        """Call the next patient for a doctor"""
        try:
            return QueueManager.call_next_patient(doctor_id)
        except Exception as e:
            print(f"Error calling next patient: {e}")
            return None

    # ----------------------
    # Notifications
    # ----------------------
    @staticmethod
    def create_notification(user_id: Optional[int], user_name: str, message: str, 
                           type: NotificationType, role_target: str = "all") -> Dict:
        """Create a new notification"""
        global next_notification_id
        
        notif_id = next_notification_id
        notification = {
            "id": notif_id,
            "user_id": user_id,
            "user_name": user_name,
            "message": message,
            "type": type,
            "timestamp": datetime.now(),
            "read": False,
            "role_target": role_target
        }
        notifications_db.append(notification)
        next_notification_id += 1
        return notification

    @staticmethod
    def get_notifications(role: str = "receptionist", limit: int = 50) -> List[Dict]:
        """Get notifications for a specific role"""
        try:
            notifs = [n for n in notifications_db if n.get("role_target") in ["all", role]]
            sorted_notifs = sorted(notifs, key=lambda x: x["timestamp"], reverse=True)
            return sorted_notifs[:limit]
        except Exception as e:
            print(f"Error getting notifications: {e}")
            return []

    @staticmethod
    def mark_notification_read(notification_id: int) -> bool:
        """Mark a notification as read"""
        try:
            for notification in notifications_db:
                if notification.get("id") == notification_id:
                    notification["read"] = True
                    return True
            return False
        except Exception as e:
            print(f"Error marking notification as read: {e}")
            return False

    @staticmethod
    def mark_all_notifications_read(role: str = "receptionist") -> int:
        """Mark all notifications for a role as read"""
        try:
            count = 0
            for notification in notifications_db:
                if notification.get("role_target") in ["all", role] and not notification.get("read"):
                    notification["read"] = True
                    count += 1
            return count
        except Exception as e:
            print(f"Error marking all notifications as read: {e}")
            return 0

    @staticmethod
    def get_unread_count(role: str = "receptionist") -> int:
        """Get count of unread notifications"""
        try:
            return len([
                n for n in notifications_db 
                if n.get("role_target") in ["all", role] and not n.get("read")
            ])
        except Exception as e:
            print(f"Error getting unread count: {e}")
            return 0

    # ----------------------
    # Patient Search
    # ----------------------
    @staticmethod
    def search_patients(query: str) -> List[Dict]:
        """Search patients by name or phone"""
        try:
            results = []
            query = query.lower()
            
            for patient in patients_db.values():
                if (query in patient.get("name", "").lower() or 
                    query in patient.get("phone", "").lower()):
                    results.append({
                        "id": patient["id"],
                        "name": patient["name"],
                        "phone": patient.get("phone", "N/A"),
                        "age": patient.get("age", "N/A"),
                        "gender": patient.get("gender", "N/A"),
                        "created_at": patient.get("created_at")
                    })
            
            return results
        except Exception as e:
            print(f"Error searching patients: {e}")
            return [] 
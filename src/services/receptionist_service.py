from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from src.models.patients import (
    patients_db, consultations_db, notifications_db,
    Patient, PatientCreate, Consultation,
    Notification, NotificationType,
    QuickRegistration, next_notification_id
)
from src.services.queue_manager import QueueManager

class ReceptionistService:
    
    # ========== Dashboard Statistics ==========
    
    @staticmethod
    def get_dashboard_stats() -> Dict:
        """Get receptionist dashboard statistics"""
        try:
            # Queue statistics
            queue_stats = QueueManager.get_queue_stats()
            
            # Registered today
            today_start = datetime.now().replace(hour=0, minute=0, second=0)
            registered_today = len([
                c for c in consultations_db.values()
                if c.get("created_at") and c["created_at"] >= today_start
            ])
            
            # Emergency queue count
            emergency_queue = len([
                c for c in consultations_db.values()
                if c.get("status") == "waiting" and c.get("priority") == 3
            ])
            
            # Normal queue count
            normal_queue = len([
                c for c in consultations_db.values()
                if c.get("status") == "waiting" and c.get("priority") == 1
            ])
            
            # Urgent queue count
            urgent_queue = len([
                c for c in consultations_db.values()
                if c.get("status") == "waiting" and c.get("priority") == 2
            ])
            
            return {
                "total_in_queue": queue_stats.get("waiting", 0),
                "emergency_queue": emergency_queue,
                "urgent_queue": urgent_queue,
                "normal_queue": normal_queue,
                "registered_today": registered_today,
                "in_progress": queue_stats.get("in_progress", 0),
                "queue_status": queue_stats
            }
        except Exception as e:
            print(f"Error in get_dashboard_stats: {e}")
            return {
                "total_in_queue": 0,
                "emergency_queue": 0,
                "urgent_queue": 0,
                "normal_queue": 0,
                "registered_today": 0,
                "in_progress": 0,
                "queue_status": {}
            }
    
    # ========== Patient Registration ==========
    
    @staticmethod
    def quick_register_patient(registration: QuickRegistration, receptionist_id: int) -> Dict:
        """Quickly register a new patient and add to queue"""
        
        try:
            # Validate input
            if not registration.patient_name or not registration.phone:
                return {
                    "success": False,
                    "error": "Patient name and phone are required"
                }
            
            # Use the global patients_db
            from src.models.patients import patients_db as global_patients_db
            
            # Check if patient already exists by phone
            existing_patient = None
            for patient in global_patients_db.values():
                if patient.get("phone") == registration.phone:
                    existing_patient = patient
                    break
            
            if existing_patient:
                patient_id = existing_patient["id"]
                patient = existing_patient
                is_new = False
            else:
                # Create new patient
                new_id = max(global_patients_db.keys()) + 1 if global_patients_db else 1
                patient = {
                    "id": new_id,
                    "name": registration.patient_name,
                    "phone": registration.phone,
                    "age": None,
                    "email": None,
                    "address": None,
                    "created_at": datetime.now(),
                    "updated_at": None
                }
                global_patients_db[new_id] = patient
                patient_id = new_id
                is_new = True
            
            # Add to queue using QueueManager
            result = QueueManager.add_to_queue(
                patient_id=patient_id,
                department=registration.department or "General",
                condition=registration.condition,
                priority=registration.priority,
                doctor_id=1,  # Default doctor
                room="4B"
            )
            
            if result.get("success"):
                # Create notification
                ReceptionistService.create_notification(
                    user_id=receptionist_id,
                    user_name="Receptionist",
                    message=f"New patient {registration.patient_name} registered in queue #{result['consultation']['queue_number']}",
                    type=NotificationType.INFO,
                    role_target="all"
                )
                
                return {
                    "success": True,
                    "patient": patient,
                    "consultation": result["consultation"],
                    "queue_position": result["consultation"]["queue_number"],
                    "is_new_patient": is_new,
                    "message": f"Patient registered successfully with queue number {result['consultation']['queue_number']}"
                }
            else:
                return {
                    "success": False,
                    "error": result.get("error", "Failed to add to queue"),
                    "patient": patient,
                    "is_new_patient": is_new
                }
                
        except Exception as e:
            print(f"Error in quick_register_patient: {str(e)}")
            import traceback
            traceback.print_exc()
            return {
                "success": False,
                "error": f"Registration failed: {str(e)}"
            }
    
    @staticmethod
    def register_patient(patient_data: PatientCreate, receptionist_id: int) -> Dict:
        """Register a new patient (full registration)"""
        
        try:
            from src.models.patients import patients_db as global_patients_db
            
            # Create patient
            new_id = max(global_patients_db.keys()) + 1 if global_patients_db else 1
            patient = {
                "id": new_id,
                "name": patient_data.name,
                "phone": patient_data.phone,
                "age": patient_data.age,
                "email": patient_data.email,
                "address": patient_data.address,
                "created_at": datetime.now(),
                "updated_at": None
            }
            global_patients_db[new_id] = patient
            
            # Create notification
            ReceptionistService.create_notification(
                user_id=receptionist_id,
                user_name="Receptionist",
                message=f"New patient {patient_data.name} registered",
                type=NotificationType.INFO,
                role_target="all"
            )
            
            return {
                "success": True,
                "patient": patient,
                "message": "Patient registered successfully"
            }
            
        except Exception as e:
            print(f"Error in register_patient: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    # ========== Queue Management ==========
    
    @staticmethod
    def get_queue_list(department: Optional[str] = None) -> List[Dict]:
        """Get full queue list with patient details"""
        try:
            waiting = QueueManager.get_waiting_patients(department=department)
            return waiting
        except Exception as e:
            print(f"Error in get_queue_list: {e}")
            return []
    
    @staticmethod
    def get_patients_in_queue() -> List[Dict]:
        """Get all patients in queue with their status"""
        queue_patients = []
        
        try:
            from src.models.patients import patients_db as global_patients_db
            from src.models.patients import consultations_db as global_consultations_db
            
            for consultation in global_consultations_db.values():
                if consultation.get("status") in ["waiting", "in_progress"]:
                    patient = global_patients_db.get(consultation.get("patient_id"))
                    if patient:
                        queue_patients.append({
                            "consultation_id": consultation["id"],
                            "patient_id": consultation["patient_id"],
                            "patient_name": patient["name"],
                            "patient_phone": patient.get("phone"),
                            "condition": consultation["condition"],
                            "priority": consultation["priority"],
                            "status": consultation["status"],
                            "queue_number": consultation["queue_number"],
                            "waiting_time": ReceptionistService._calculate_waiting_time(consultation.get("created_at")),
                            "department": consultation.get("department", "General"),
                            "room": consultation.get("room")
                        })
            
            # Sort by priority (highest first) and then queue number
            queue_patients.sort(key=lambda x: (-x["priority"], x["queue_number"]))
            
        except Exception as e:
            print(f"Error getting patients in queue: {e}")
        
        return queue_patients
    
    @staticmethod
    def _calculate_waiting_time(created_at: Optional[datetime]) -> str:
        """Calculate waiting time in human readable format"""
        if not created_at:
            return "Unknown"
        
        try:
            delta = datetime.now() - created_at
            minutes = int(delta.total_seconds() / 60)
            
            if minutes < 1:
                return "Just now"
            elif minutes < 60:
                return f"{minutes} min ago"
            elif minutes < 120:
                return "1 hour ago"
            else:
                hours = minutes // 60
                return f"{hours} hours ago"
        except:
            return "Unknown"
    
    @staticmethod
    def update_queue_priority(consultation_id: int, new_priority: int) -> Optional[Dict]:
        """Update priority of a waiting patient"""
        try:
            result = QueueManager.update_priority(consultation_id, new_priority)
            
            if result and result.get("success"):
                # Get patient info for notification
                from src.models.patients import consultations_db as global_consultations_db
                from src.models.patients import patients_db as global_patients_db
                
                consultation = global_consultations_db.get(consultation_id)
                if consultation:
                    patient = global_patients_db.get(consultation.get("patient_id"))
                    if patient:
                        ReceptionistService.create_notification(
                            user_id=None,
                            user_name="System",
                            message=f"Priority updated for {patient['name']} to {ReceptionistService._priority_name(new_priority)}",
                            type=NotificationType.INFO,
                            role_target="all"
                        )
            
            return result
            
        except Exception as e:
            print(f"Error updating priority: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    @staticmethod
    def _priority_name(priority: int) -> str:
        """Convert priority number to name"""
        if priority == 3:
            return "EMERGENCY"
        elif priority == 2:
            return "URGENT"
        else:
            return "NORMAL"
    
    @staticmethod
    def remove_from_queue(consultation_id: int) -> bool:
        """Remove a patient from queue"""
        try:
            # Get consultation info for notification
            from src.models.patients import consultations_db as global_consultations_db
            from src.models.patients import patients_db as global_patients_db
            
            consultation = global_consultations_db.get(consultation_id)
            if consultation:
                patient = global_patients_db.get(consultation.get("patient_id"))
                if patient:
                    ReceptionistService.create_notification(
                        user_id=None,
                        user_name="System",
                        message=f"{patient['name']} removed from queue",
                        type=NotificationType.INFO,
                        role_target="receptionist"
                    )
            
            return QueueManager.remove_from_queue(consultation_id)
            
        except Exception as e:
            print(f"Error removing from queue: {e}")
            return False
    
    # ========== Patient Search ==========
    
    @staticmethod
    def search_patients(search_term: str) -> List[Dict]:
        """Search patients by name or phone"""
        results = []
        search_term = search_term.lower().strip()
        
        if not search_term:
            return []
        
        try:
            from src.models.patients import patients_db as global_patients_db
            from src.models.patients import consultations_db as global_consultations_db
            
            for patient in global_patients_db.values():
                name_match = search_term in patient["name"].lower()
                phone_match = patient.get("phone") and search_term in patient["phone"]
                
                if name_match or phone_match:
                    # Get current queue status if any
                    current_consultation = None
                    for consultation in global_consultations_db.values():
                        if consultation.get("patient_id") == patient["id"] and consultation.get("status") in ["waiting", "in_progress"]:
                            current_consultation = consultation
                            break
                    
                    # Format datetime for JSON
                    created_at = patient["created_at"]
                    if isinstance(created_at, datetime):
                        created_at = created_at.isoformat()
                    
                    results.append({
                        "id": patient["id"],
                        "name": patient["name"],
                        "phone": patient.get("phone"),
                        "age": patient.get("age"),
                        "email": patient.get("email"),
                        "created_at": created_at,
                        "current_status": current_consultation["status"] if current_consultation else "discharged",
                        "current_condition": current_consultation["condition"] if current_consultation else None,
                        "queue_number": current_consultation["queue_number"] if current_consultation else None,
                        "priority": current_consultation["priority"] if current_consultation else None,
                        "priority_name": ReceptionistService._priority_name(current_consultation["priority"]) if current_consultation else None
                    })
            
        except Exception as e:
            print(f"Error searching patients: {e}")
        
        return results
    
    # ========== Notifications ==========
    
    @staticmethod
    def create_notification(
        user_id: Optional[int],
        user_name: Optional[str],
        message: str,
        type: NotificationType,
        role_target: str = "all"
    ) -> Dict:
        """Create a new notification"""
        global next_notification_id
        
        try:
            from src.models.patients import notifications_db as global_notifications_db
            from src.models.patients import next_notification_id as global_next_id
            
            notification = {
                "id": global_next_id,
                "user_id": user_id,
                "user_name": user_name or "System",
                "message": message,
                "type": type,
                "timestamp": datetime.now(),
                "read": False,
                "role_target": role_target
            }
            
            global_notifications_db.append(notification)
            
            # Update the global variable
            import src.models.patients
            src.models.patients.next_notification_id = global_next_id + 1
            
            return notification
            
        except Exception as e:
            print(f"Error creating notification: {e}")
            return {}
    
    @staticmethod
    def get_notifications(role: str = "receptionist", limit: int = 20) -> List[Dict]:
        """Get notifications for a specific role"""
        try:
            from src.models.patients import notifications_db as global_notifications_db
            
            notifications = []
            for n in global_notifications_db:
                if n.get("role_target") in ["all", role]:
                    notification_copy = n.copy()
                    # Format datetime for JSON
                    if isinstance(notification_copy.get("timestamp"), datetime):
                        notification_copy["timestamp"] = notification_copy["timestamp"].isoformat()
                    notifications.append(notification_copy)
            
            # Sort by timestamp (newest first)
            notifications.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
            
            return notifications[:limit]
            
        except Exception as e:
            print(f"Error getting notifications: {e}")
            return []
    
    @staticmethod
    def mark_notification_read(notification_id: int) -> bool:
        """Mark a notification as read"""
        try:
            from src.models.patients import notifications_db as global_notifications_db
            
            for notification in global_notifications_db:
                if notification["id"] == notification_id:
                    notification["read"] = True
                    return True
            return False
            
        except Exception as e:
            print(f"Error marking notification read: {e}")
            return False
    
    @staticmethod
    def mark_all_notifications_read(role: str = "receptionist") -> int:
        """Mark all notifications as read for a role"""
        count = 0
        try:
            from src.models.patients import notifications_db as global_notifications_db
            
            for notification in global_notifications_db:
                if notification.get("role_target") in ["all", role] and not notification.get("read"):
                    notification["read"] = True
                    count += 1
            return count
            
        except Exception as e:
            print(f"Error marking all notifications read: {e}")
            return count
    
    @staticmethod
    def get_unread_count(role: str = "receptionist") -> int:
        """Get count of unread notifications"""
        try:
            from src.models.patients import notifications_db as global_notifications_db
            
            return len([
                n for n in global_notifications_db
                if n.get("role_target") in ["all", role] and not n.get("read")
            ])
        except Exception as e:
            print(f"Error getting unread count: {e}")
            return 0
    
    # ========== Recent Patients ==========
    
    @staticmethod
    def get_recent_patients(limit: int = 10) -> List[Dict]:
        """Get recently registered patients"""
        try:
            from src.models.patients import patients_db as global_patients_db
            from src.models.patients import consultations_db as global_consultations_db
            
            # Get all patients sorted by creation date
            recent = sorted(
                global_patients_db.values(),
                key=lambda x: x.get("created_at", datetime.min),
                reverse=True
            )[:limit]
            
            # Add their latest status
            result = []
            for patient in recent:
                patient_copy = patient.copy()
                latest_consultation = ReceptionistService._get_latest_consultation(patient["id"])
                if latest_consultation:
                    patient_copy["latest_status"] = latest_consultation.get("status")
                    patient_copy["latest_condition"] = latest_consultation.get("condition")
                    if isinstance(latest_consultation.get("created_at"), datetime):
                        patient_copy["latest_status_date"] = latest_consultation["created_at"].isoformat()
                    else:
                        patient_copy["latest_status_date"] = latest_consultation.get("created_at")
                else:
                    patient_copy["latest_status"] = "no_visit"
                    patient_copy["latest_condition"] = "N/A"
                    patient_copy["latest_status_date"] = None
                
                # Format datetime for JSON
                if isinstance(patient_copy.get("created_at"), datetime):
                    patient_copy["created_at"] = patient_copy["created_at"].isoformat()
                result.append(patient_copy)
            
            return result
            
        except Exception as e:
            print(f"Error getting recent patients: {e}")
            return []
    
    @staticmethod
    def _get_latest_consultation(patient_id: int) -> Optional[Dict]:
        """Get latest consultation for a patient"""
        try:
            from src.models.patients import consultations_db as global_consultations_db
            
            patient_consultations = [
                c for c in global_consultations_db.values()
                if c.get("patient_id") == patient_id
            ]
            
            if patient_consultations:
                return max(patient_consultations, key=lambda x: x.get("created_at", datetime.min))
            return None
            
        except Exception as e:
            print(f"Error getting latest consultation: {e}")
            return None
    
    # ========== Quick Actions ==========
    
    @staticmethod
    def get_quick_stats() -> Dict:
        """Get quick statistics for receptionist"""
        try:
            from src.models.patients import consultations_db as global_consultations_db
            from src.models.patients import patients_db as global_patients_db
            
            today_start = datetime.now().replace(hour=0, minute=0, second=0)
            
            return {
                "total_in_queue": len([c for c in global_consultations_db.values() if c.get("status") == "waiting"]),
                "emergency_cases": len([c for c in global_consultations_db.values() if c.get("status") == "waiting" and c.get("priority") == 3]),
                "urgent_cases": len([c for c in global_consultations_db.values() if c.get("status") == "waiting" and c.get("priority") == 2]),
                "registered_today": len([c for c in global_consultations_db.values() if c.get("created_at") and c["created_at"] >= today_start]),
                "unread_notifications": ReceptionistService.get_unread_count("receptionist"),
                "total_patients": len(global_patients_db)
            }
            
        except Exception as e:
            print(f"Error getting quick stats: {e}")
            return {
                "total_in_queue": 0,
                "emergency_cases": 0,
                "urgent_cases": 0,
                "registered_today": 0,
                "unread_notifications": 0,
                "total_patients": 0
            }
    
    # ========== Department Management ==========
    
    @staticmethod
    def get_departments() -> List[str]:
        """Get list of departments"""
        try:
            from src.models.patients import consultations_db as global_consultations_db
            
            departments = set()
            for consultation in global_consultations_db.values():
                if consultation.get("department"):
                    departments.add(consultation["department"])
            return sorted(list(departments))
            
        except Exception as e:
            print(f"Error getting departments: {e}")
            return []
    
    @staticmethod
    def get_queue_by_department(department: str) -> Dict:
        """Get queue statistics for a specific department"""
        try:
            from src.models.patients import consultations_db as global_consultations_db
            from src.models.patients import patients_db as global_patients_db
            
            department_queue = [
                c for c in global_consultations_db.values()
                if c.get("department") == department and c.get("status") == "waiting"
            ]
            
            patients_list = []
            for c in sorted(department_queue, key=lambda x: (-x.get("priority", 1), x.get("queue_number", 999))):
                patient = global_patients_db.get(c.get("patient_id"), {})
                patients_list.append({
                    "consultation_id": c["id"],
                    "patient_name": patient.get("name", "Unknown"),
                    "condition": c.get("condition"),
                    "priority": c.get("priority"),
                    "priority_name": ReceptionistService._priority_name(c.get("priority", 1)),
                    "queue_number": c.get("queue_number"),
                    "waiting_time": ReceptionistService._calculate_waiting_time(c.get("created_at"))
                })
            
            return {
                "department": department,
                "total_waiting": len(department_queue),
                "emergency": len([c for c in department_queue if c.get("priority") == 3]),
                "urgent": len([c for c in department_queue if c.get("priority") == 2]),
                "normal": len([c for c in department_queue if c.get("priority") == 1]),
                "patients": patients_list
            }
            
        except Exception as e:
            print(f"Error getting queue by department: {e}")
            return {
                "department": department,
                "total_waiting": 0,
                "emergency": 0,
                "urgent": 0,
                "normal": 0,
                "patients": []
            }
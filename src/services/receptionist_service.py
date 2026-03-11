from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
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
        """Get comprehensive dashboard statistics for receptionist"""
        try:
            queue_stats = QueueManager.get_queue_stats()
            today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            
            # Calculate today's registrations
            registered_today = len([
                c for c in consultations_db.values()
                if c.get("created_at") and 
                isinstance(c["created_at"], datetime) and 
                c["created_at"] >= today_start
            ])
            
            # Get waiting patients by department
            waiting_by_dept = {}
            in_progress_by_dept = {}
            total_wait_time = 0
            waiting_count = 0
            
            for consultation in consultations_db.values():
                if consultation.get("status") == "waiting":
                    dept = consultation.get("department", "General")
                    waiting_by_dept[dept] = waiting_by_dept.get(dept, 0) + 1
                    
                    # Calculate wait time
                    if consultation.get("joined_at"):
                        if isinstance(consultation["joined_at"], datetime):
                            wait_time = (datetime.now() - consultation["joined_at"]).seconds // 60
                        else:
                            wait_time = 0
                        total_wait_time += wait_time
                        waiting_count += 1
                        
                elif consultation.get("status") == "in-progress":
                    dept = consultation.get("department", "General")
                    in_progress_by_dept[dept] = in_progress_by_dept.get(dept, 0) + 1
            
            avg_wait_time = total_wait_time // waiting_count if waiting_count > 0 else 0
            
            # Get recent registrations
            recent_registrations = []
            for consultation in sorted(
                consultations_db.values(), 
                key=lambda x: x.get("created_at", datetime.min), 
                reverse=True
            )[:5]:
                if consultation.get("patient_id"):
                    patient = patients_db.get(consultation["patient_id"])
                    if patient:
                        recent_registrations.append({
                            "patient_name": patient.get("name", "Unknown"),
                            "department": consultation.get("department", "General"),
                            "queue_number": consultation.get("queue_number", "N/A"),
                            "time": consultation.get("created_at"),
                            "priority": consultation.get("priority", 3)
                        })
            
            return {
                "success": True,
                "total_in_queue": queue_stats.get("waiting", 0),
                "registered_today": registered_today,
                "in_progress": queue_stats.get("in_progress", 0),
                "waiting_by_department": waiting_by_dept,
                "in_progress_by_department": in_progress_by_dept,
                "average_wait_time": avg_wait_time,
                "estimated_total_wait": avg_wait_time * waiting_count,
                "recent_registrations": recent_registrations,
                "queue_stats": queue_stats,
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            print(f"Error in get_dashboard_stats: {e}")
            return {
                "success": False,
                "total_in_queue": 0,
                "registered_today": 0,
                "in_progress": 0,
                "waiting_by_department": {},
                "in_progress_by_department": {},
                "average_wait_time": 0,
                "estimated_total_wait": 0,
                "recent_registrations": [],
                "queue_stats": {},
                "timestamp": datetime.now().isoformat(),
                "error": str(e)
            }

    # ----------------------
    # Receptionist CRUD
    # ----------------------
    @staticmethod
    def create_receptionist(data: ReceptionistCreate) -> Dict:
        """Create a new receptionist"""
        try:
            # Validate required fields
            if not data.name or not data.phone or not data.employee_id:
                return {
                    "success": False, 
                    "error": "Name, phone, and employee ID are required"
                }
            
            # Check if employee_id already exists
            existing = ReceptionistModel.get_by_employee_id(data.employee_id)
            if existing:
                return {
                    "success": False,
                    "error": f"Receptionist with employee ID {data.employee_id} already exists"
                }
            
            result = ReceptionistModel.create_receptionist(data)
            
            # Create notification for new receptionist
            ReceptionistService.create_notification(
                user_id=None,
                user_name="System",
                message=f"New receptionist {data.name} added",
                type=NotificationType.INFO,
                role_target="admin"
            )
            
            return {
                "success": True,
                "receptionist": result.get("receptionist") if isinstance(result, dict) else result,
                "message": f"Receptionist {data.name} created successfully"
            }
        except Exception as e:
            print(f"Error creating receptionist: {e}")
            return {"success": False, "error": str(e)}

    @staticmethod
    def update_receptionist(r_id: int, data: ReceptionistUpdate) -> Dict:
        """Update receptionist information"""
        try:
            # Check if receptionist exists
            existing = ReceptionistModel.get_by_id(r_id)
            if not existing:
                return {
                    "success": False,
                    "error": f"Receptionist with ID {r_id} not found"
                }
            
            result = ReceptionistModel.update_receptionist(r_id, data)
            
            return {
                "success": True,
                "receptionist": result,
                "message": "Receptionist updated successfully"
            }
        except Exception as e:
            print(f"Error updating receptionist: {e}")
            return {"success": False, "error": str(e)}

    @staticmethod
    def get_all_receptionists() -> Dict:
        """Get all receptionists"""
        try:
            receptionists = ReceptionistModel.get_all()
            
            # Enhance with additional stats
            enhanced_list = []
            for rec in receptionists:
                # Count patients registered by this receptionist today
                today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
                patients_registered_today = len([
                    p for p in patients_db.values()
                    if p.get("created_by") == rec.get("id") and
                    p.get("created_at") and
                    p["created_at"] >= today_start
                ])
                
                enhanced_list.append({
                    **rec,
                    "patients_registered_today": patients_registered_today,
                    "is_active": rec.get("status") == "active"
                })
            
            return {
                "success": True,
                "receptionists": enhanced_list,
                "total": len(enhanced_list),
                "active_count": len([r for r in enhanced_list if r.get("is_active")])
            }
        except Exception as e:
            print(f"Error getting receptionists: {e}")
            return {"success": False, "receptionists": [], "total": 0, "error": str(e)}

    @staticmethod
    def get_receptionist_by_id(r_id: int) -> Dict:
        """Get receptionist by ID"""
        try:
            receptionist = ReceptionistModel.get_by_id(r_id)
            if not receptionist:
                return {
                    "success": False,
                    "error": f"Receptionist with ID {r_id} not found"
                }
            
            # Get registration stats
            today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            patients_registered = len([
                p for p in patients_db.values()
                if p.get("created_by") == r_id
            ])
            patients_registered_today = len([
                p for p in patients_db.values()
                if p.get("created_by") == r_id and
                p.get("created_at") and
                p["created_at"] >= today_start
            ])
            
            return {
                "success": True,
                "receptionist": {
                    **receptionist,
                    "stats": {
                        "total_registered": patients_registered,
                        "registered_today": patients_registered_today
                    }
                }
            }
        except Exception as e:
            print(f"Error getting receptionist: {e}")
            return {"success": False, "error": str(e)}

    @staticmethod
    def delete_receptionist(r_id: int) -> Dict:
        """Delete receptionist (soft delete)"""
        try:
            # Check if receptionist exists
            existing = ReceptionistModel.get_by_id(r_id)
            if not existing:
                return {
                    "success": False,
                    "error": f"Receptionist with ID {r_id} not found"
                }
            
            result = ReceptionistModel.delete_receptionist(r_id)
            
            if result:
                # Create notification
                ReceptionistService.create_notification(
                    user_id=None,
                    user_name="System",
                    message=f"Receptionist {existing.get('name')} deactivated",
                    type=NotificationType.WARNING,
                    role_target="admin"
                )
                
                return {
                    "success": True,
                    "message": f"Receptionist {existing.get('name')} deactivated successfully"
                }
            else:
                return {
                    "success": False,
                    "error": "Failed to delete receptionist"
                }
        except Exception as e:
            print(f"Error deleting receptionist: {e}")
            return {"success": False, "error": str(e)}

    @staticmethod
    def get_active_receptionists() -> Dict:
        """Get all active receptionists"""
        try:
            all_receptionists = ReceptionistModel.get_all()
            active = [r for r in all_receptionists if r.get("status") == "active"]
            
            return {
                "success": True,
                "receptionists": active,
                "total": len(active)
            }
        except Exception as e:
            print(f"Error getting active receptionists: {e}")
            return {"success": False, "receptionists": [], "total": 0, "error": str(e)}

    @staticmethod
    def get_receptionist_by_employee_id(employee_id: str) -> Dict:
        """Get receptionist by employee ID"""
        try:
            receptionist = ReceptionistModel.get_by_employee_id(employee_id)
            if not receptionist:
                return {
                    "success": False,
                    "error": f"Receptionist with employee ID {employee_id} not found"
                }
            
            return {
                "success": True,
                "receptionist": receptionist
            }
        except Exception as e:
            print(f"Error getting receptionist by employee ID: {e}")
            return {"success": False, "error": str(e)}

    # ----------------------
    # Quick Patient Registration
    # ----------------------
    @staticmethod
    def quick_register_patient(registration: QuickRegistration, receptionist_id: int) -> Dict:
        """Quickly register a new patient and add to queue"""
        try:
            # Validate required fields
            if not registration.patient_name:
                return {
                    "success": False, 
                    "error": "Patient name is required",
                    "patient_id": None,
                    "queue_number": None
                }
            
            if not registration.phone:
                return {
                    "success": False, 
                    "error": "Phone number is required",
                    "patient_id": None,
                    "queue_number": None
                }
            
            # Validate phone number format (simple validation)
            if not registration.phone.replace("+", "").replace("-", "").isdigit():
                return {
                    "success": False,
                    "error": "Invalid phone number format",
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
                patient_name = existing_patient.get("name", registration.patient_name)
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
                    "created_by": receptionist_id,
                    "medical_history": registration.medical_history or []
                }
                is_new = True
                patient_name = registration.patient_name

            # Validate department
            valid_departments = ["Cardiology", "General", "Pediatrics", "Emergency", "Orthopedics"]
            department = registration.department or "General"
            if department not in valid_departments:
                department = "General"

            # Add to queue
            result = QueueManager.add_to_queue(
                patient_id=patient_id,
                department=department,
                condition=registration.condition or "General checkup",
                priority=registration.priority or 3,
                doctor_id=registration.doctor_id or 1,
                room=registration.room or "Waiting Area"
            )

            if result and result.get("success"):
                # Create notification
                queue_number = result.get('consultation', {}).get('queue_number', 'N/A')
                position = result.get('consultation', {}).get('position', 0)
                estimated_time = result.get('consultation', {}).get('estimated_wait_time', 0)
                
                ReceptionistService.create_notification(
                    user_id=receptionist_id,
                    user_name=registration.receptionist_name or "Receptionist",
                    message=f"Patient {patient_name} registered in {department} - Queue #{queue_number}",
                    type=NotificationType.INFO,
                    role_target="all"
                )

                # Create notification for doctor if specified
                if registration.doctor_id:
                    ReceptionistService.create_notification(
                        user_id=registration.doctor_id,
                        user_name="System",
                        message=f"New patient {patient_name} added to your queue in {department}",
                        type=NotificationType.INFO,
                        role_target="doctor"
                    )

                return {
                    "success": True,
                    "patient_id": patient_id,
                    "patient_name": patient_name,
                    "queue_number": queue_number,
                    "position": position,
                    "estimated_wait_time": estimated_time,
                    "estimated_wait_minutes": f"{estimated_time} minutes",
                    "department": department,
                    "is_new_patient": is_new,
                    "message": f"Patient registered successfully in queue #{queue_number}",
                    "timestamp": datetime.now().isoformat()
                }
            else:
                error_msg = result.get("error", "Failed to add to queue") if result else "Queue service unavailable"
                return {
                    "success": False,
                    "error": error_msg,
                    "patient_id": patient_id,
                    "patient_name": patient_name,
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
    def get_patients_in_queue(department: Optional[str] = None) -> Dict:
        """Get patients currently in queue"""
        try:
            waiting_patients = QueueManager.get_waiting_patients(department=department)
            
            # Enhance with patient details
            enhanced_list = []
            for item in waiting_patients:
                patient = patients_db.get(item.get("patient_id"))
                if patient:
                    # Calculate wait time
                    wait_time = 0
                    if item.get("joined_at"):
                        if isinstance(item["joined_at"], datetime):
                            wait_time = (datetime.now() - item["joined_at"]).seconds // 60
                    
                    enhanced_list.append({
                        "queue_id": item.get("id"),
                        "queue_number": item.get("queue_number"),
                        "patient_id": patient["id"],
                        "patient_name": patient.get("name", "Unknown"),
                        "patient_phone": patient.get("phone", "N/A"),
                        "patient_age": patient.get("age", "N/A"),
                        "patient_gender": patient.get("gender", "N/A"),
                        "department": item.get("department", "General"),
                        "priority": item.get("priority", 3),
                        "condition": item.get("condition", "General checkup"),
                        "status": item.get("status", "waiting"),
                        "joined_at": item.get("joined_at"),
                        "wait_time_minutes": wait_time,
                        "estimated_remaining": max(0, 15 - wait_time) if wait_time < 15 else 0,
                        "registered_by": item.get("created_by", "Receptionist"),
                        "room": item.get("room", "Waiting Area")
                    })
            
            # Sort by priority (higher priority first) then by join time
            enhanced_list.sort(key=lambda x: (-x["priority"], x.get("joined_at", datetime.max)))
            
            # Group by priority for easy display
            by_priority = {
                "emergency": [p for p in enhanced_list if p["priority"] == 1],
                "urgent": [p for p in enhanced_list if p["priority"] == 2],
                "normal": [p for p in enhanced_list if p["priority"] == 3],
                "non_urgent": [p for p in enhanced_list if p["priority"] >= 4]
            }
            
            return {
                "success": True,
                "queue": enhanced_list,
                "total": len(enhanced_list),
                "by_priority": by_priority,
                "department": department or "All",
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            print(f"Error getting patients in queue: {e}")
            return {
                "success": False,
                "queue": [],
                "total": 0,
                "by_priority": {},
                "error": str(e)
            }

    @staticmethod
    def get_queue_by_priority(department: Optional[str] = None) -> Dict:
        """Get queue organized by priority"""
        try:
            queue_result = ReceptionistService.get_patients_in_queue(department)
            
            if not queue_result.get("success"):
                return {
                    "emergency": [],
                    "urgent": [],
                    "normal": [],
                    "non_urgent": [],
                    "total": 0
                }
            
            return queue_result.get("by_priority", {
                "emergency": [],
                "urgent": [],
                "normal": [],
                "non_urgent": []
            })
        except Exception as e:
            print(f"Error getting queue by priority: {e}")
            return {
                "emergency": [],
                "urgent": [],
                "normal": [],
                "non_urgent": [],
                "total": 0,
                "error": str(e)
            }

    @staticmethod
    def call_next_patient(doctor_id: int) -> Dict:
        """Call the next patient for a doctor"""
        try:
            # Validate doctor exists
            from src.models.admin import AdminModel
            doctor = AdminModel.get_staff_by_id(doctor_id)
            if not doctor and doctor_id != 1:  # Allow default doctor
                return {
                    "success": False,
                    "error": f"Doctor with ID {doctor_id} not found"
                }
            
            result = QueueManager.call_next_patient(doctor_id)
            
            if result and result.get("success"):
                patient = patients_db.get(result.get("patient_id"))
                
                # Create notification
                ReceptionistService.create_notification(
                    user_id=doctor_id,
                    user_name="System",
                    message=f"Patient {patient.get('name', 'Unknown')} called for consultation",
                    type=NotificationType.INFO,
                    role_target="doctor"
                )
                
                return {
                    "success": True,
                    "patient": {
                        "id": patient.get("id") if patient else None,
                        "name": patient.get("name", "Unknown") if patient else "Unknown",
                        "queue_number": result.get("queue_number"),
                        "room": result.get("room", "Consultation Room")
                    },
                    "message": f"Patient called successfully"
                }
            else:
                return {
                    "success": False,
                    "error": result.get("error", "No patients in queue") if result else "Queue service unavailable"
                }
        except Exception as e:
            print(f"Error calling next patient: {e}")
            return {"success": False, "error": str(e)}

    # ----------------------
    # Notifications
    # ----------------------
    @staticmethod
    def create_notification(user_id: Optional[int], user_name: str, message: str, 
                           type: NotificationType, role_target: str = "all") -> Dict:
        """Create a new notification"""
        global next_notification_id
        
        try:
            notif_id = next_notification_id
            notification = {
                "id": notif_id,
                "user_id": user_id,
                "user_name": user_name,
                "message": message,
                "type": type.value if hasattr(type, 'value') else str(type),
                "timestamp": datetime.now(),
                "read": False,
                "role_target": role_target
            }
            notifications_db.append(notification)
            next_notification_id += 1
            
            # Keep only last 100 notifications
            if len(notifications_db) > 100:
                while len(notifications_db) > 100:
                    notifications_db.pop(0)
            
            return notification
        except Exception as e:
            print(f"Error creating notification: {e}")
            return {}

    @staticmethod
    def get_notifications(role: str = "receptionist", limit: int = 50) -> Dict:
        """Get notifications for a specific role"""
        try:
            # Filter by role
            notifs = [
                n for n in notifications_db 
                if n.get("role_target") in ["all", role]
            ]
            
            # Sort by timestamp (newest first)
            sorted_notifs = sorted(
                notifs, 
                key=lambda x: x.get("timestamp", datetime.min), 
                reverse=True
            )[:limit]
            
            # Format for response
            formatted_notifs = []
            for n in sorted_notifs:
                formatted_notifs.append({
                    "id": n.get("id"),
                    "message": n.get("message"),
                    "type": n.get("type"),
                    "timestamp": n.get("timestamp").isoformat() if isinstance(n.get("timestamp"), datetime) else n.get("timestamp"),
                    "read": n.get("read", False),
                    "user_name": n.get("user_name", "System")
                })
            
            unread_count = len([n for n in notifs if not n.get("read")])
            
            return {
                "success": True,
                "notifications": formatted_notifs,
                "unread_count": unread_count,
                "total": len(formatted_notifs)
            }
        except Exception as e:
            print(f"Error getting notifications: {e}")
            return {
                "success": False,
                "notifications": [],
                "unread_count": 0,
                "total": 0,
                "error": str(e)
            }

    @staticmethod
    def mark_notification_read(notification_id: int) -> Dict:
        """Mark a notification as read"""
        try:
            for notification in notifications_db:
                if notification.get("id") == notification_id:
                    notification["read"] = True
                    return {
                        "success": True,
                        "message": "Notification marked as read"
                    }
            return {
                "success": False,
                "error": f"Notification with ID {notification_id} not found"
            }
        except Exception as e:
            print(f"Error marking notification as read: {e}")
            return {"success": False, "error": str(e)}

    @staticmethod
    def mark_all_notifications_read(role: str = "receptionist") -> Dict:
        """Mark all notifications for a role as read"""
        try:
            count = 0
            for notification in notifications_db:
                if notification.get("role_target") in ["all", role] and not notification.get("read"):
                    notification["read"] = True
                    count += 1
            
            return {
                "success": True,
                "marked_count": count,
                "message": f"{count} notifications marked as read"
            }
        except Exception as e:
            print(f"Error marking all notifications as read: {e}")
            return {"success": False, "error": str(e), "marked_count": 0}

    @staticmethod
    def get_unread_count(role: str = "receptionist") -> Dict:
        """Get count of unread notifications"""
        try:
            count = len([
                n for n in notifications_db 
                if n.get("role_target") in ["all", role] and not n.get("read")
            ])
            
            return {
                "success": True,
                "unread_count": count
            }
        except Exception as e:
            print(f"Error getting unread count: {e}")
            return {"success": False, "unread_count": 0, "error": str(e)}

    # ----------------------
    # Patient Search
    # ----------------------
    @staticmethod
    def search_patients(query: str) -> Dict:
        """Search patients by name or phone"""
        try:
            if not query or len(query.strip()) < 2:
                return {
                    "success": True,
                    "patients": [],
                    "total": 0,
                    "message": "Search query too short"
                }
            
            results = []
            query = query.lower().strip()
            
            for patient in patients_db.values():
                name_match = query in patient.get("name", "").lower()
                phone_match = query in patient.get("phone", "").lower()
                
                if name_match or phone_match:
                    # Get patient's current queue status if any
                    current_queue = None
                    for consultation in consultations_db.values():
                        if consultation.get("patient_id") == patient["id"] and consultation.get("status") == "waiting":
                            current_queue = {
                                "queue_number": consultation.get("queue_number"),
                                "department": consultation.get("department"),
                                "position": consultation.get("position"),
                                "estimated_wait": consultation.get("estimated_wait_time")
                            }
                            break
                    
                    results.append({
                        "id": patient["id"],
                        "name": patient["name"],
                        "phone": patient.get("phone", "N/A"),
                        "age": patient.get("age", "N/A"),
                        "gender": patient.get("gender", "N/A"),
                        "created_at": patient.get("created_at").isoformat() if isinstance(patient.get("created_at"), datetime) else patient.get("created_at"),
                        "current_queue": current_queue,
                        "visit_count": len([
                            c for c in consultations_db.values() 
                            if c.get("patient_id") == patient["id"]
                        ])
                    })
            
            return {
                "success": True,
                "patients": results,
                "total": len(results),
                "query": query
            }
        except Exception as e:
            print(f"Error searching patients: {e}")
            return {
                "success": False,
                "patients": [],
                "total": 0,
                "error": str(e)
            } 
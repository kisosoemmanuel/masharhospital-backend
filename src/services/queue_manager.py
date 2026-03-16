from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime, timedelta
from src.models.patients import (
    consultations_db, patients_db, prescriptions_db,
    Consultation, ConsultationCreate, PatientPriority, PatientStatus
)

class QueueManager:
    _instance = None
    _current_queue_number = 1
    
    @classmethod
    def initialize(cls):
        """Initialize queue manager and check for any active consultations"""
        try:
            if consultations_db:
                # Get max queue number safely
                queue_numbers = [c["queue_number"] for c in consultations_db.values() if c.get("queue_number")]
                if queue_numbers:
                    cls._current_queue_number = max(queue_numbers) + 1
                else:
                    cls._current_queue_number = 1
            else:
                cls._current_queue_number = 1
            print(f"Queue Manager initialized. Current queue number: {cls._current_queue_number}")

            # --- Warn if any active consultations exist at startup ---
            active = [c for c in consultations_db.values() if c.get("status") == "in_progress"]
            if active:
                print("WARNING: Active consultations found on startup:")
                for c in active:
                    print(f"  - id={c.get('id')}, doctor={c.get('doctor_id')}, started={c.get('started_at')}")
            # ---------------------------------------------------------

        except Exception as e:
            print(f"Error initializing queue manager: {e}")
            cls._current_queue_number = 1

    @classmethod
    def get_current_consultation(cls, doctor_id: Optional[int] = None, department: Optional[str] = None) -> Optional[Dict]:
        """Get current consultation for a doctor/department"""
        try:
            for consultation in consultations_db.values():
                if consultation.get("status") == "in_progress":
                    if doctor_id and consultation.get("doctor_id") != doctor_id:
                        continue
                    if department and consultation.get("department") != department:
                        continue
                    
                    # --- LOGGING ---
                    print(f"[get_current] Found active consultation: id={consultation.get('id')}, doctor={consultation.get('doctor_id')}, status={consultation.get('status')}")
                    # -----------------
                    
                    # Enrich with patient data
                    patient = patients_db.get(consultation.get("patient_id"))
                    if patient:
                        result = consultation.copy()
                        result["patient"] = patient
                        result["waiting_time"] = cls._calculate_session_duration(consultation.get("started_at"))
                        return result
            return None
        except Exception as e:
            print(f"Error getting current consultation: {e}")
            return None

    @classmethod
    def get_waiting_patients(cls, doctor_id: Optional[int] = None, department: Optional[str] = None) -> List[Dict]:
        """Get waiting patients for a doctor/department"""
        waiting = []
        
        try:
            for consultation in consultations_db.values():
                if consultation.get("status") == "waiting":
                    if doctor_id and consultation.get("doctor_id") != doctor_id:
                        continue
                    if department and consultation.get("department") != department:
                        continue
                    
                    # Enrich with patient data
                    patient = patients_db.get(consultation.get("patient_id"))
                    if patient:
                        enriched = consultation.copy()
                        enriched["patient"] = patient
                        enriched["patient_name"] = patient.get("name")
                        enriched["patient_phone"] = patient.get("phone")
                        enriched["waiting_time"] = cls._calculate_waiting_time(consultation.get("created_at"))
                        waiting.append(enriched)
            
            # Sort by priority (highest first) then queue number
            waiting.sort(key=lambda x: (-x.get("priority", 1), x.get("queue_number", 999)))
            
        except Exception as e:
            print(f"Error getting waiting patients: {e}")
        
        return waiting

    @classmethod
    def _calculate_waiting_time(cls, created_at: Optional[datetime]) -> str:
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

    @classmethod
    def _calculate_session_duration(cls, started_at: Optional[datetime]) -> str:
        """Calculate current session duration"""
        if not started_at:
            return "Not started"
        
        try:
            delta = datetime.now() - started_at
            minutes = int(delta.total_seconds() / 60)
            
            if minutes < 1:
                return "Just started"
            elif minutes < 60:
                return f"{minutes} min"
            else:
                hours = minutes // 60
                minutes_remainder = minutes % 60
                return f"{hours}h {minutes_remainder}m"
        except:
            return "Unknown"

    @classmethod
    def add_to_queue(
        cls,
        patient_id: int,
        department: str = "General",
        condition: str = None,
        priority: int = 1,
        doctor_id: int = 1,  # Default doctor
        room: str = "4B"
    ) -> Dict:
        """Add a patient to the queue"""
        try:
            # Validate patient exists
            if patient_id not in patients_db:
                raise ValueError(f"Patient with ID {patient_id} not found")
            
            # Check if patient already in queue
            for consultation in consultations_db.values():
                if (consultation.get("patient_id") == patient_id and 
                    consultation.get("status") in ["waiting", "in_progress"]):
                    raise ValueError(f"Patient is already in queue (Status: {consultation.get('status')})")
            
            # Generate new ID
            new_id = max(consultations_db.keys()) + 1 if consultations_db else 1
            
            # Create new consultation
            new_consultation = {
                "id": new_id,
                "patient_id": patient_id,
                "doctor_id": doctor_id,
                "department": department,
                "room": room,
                "condition": condition or "General Consultation",
                "priority": priority,
                "status": "waiting",
                "queue_number": cls._current_queue_number,
                "created_at": datetime.now(),
                "started_at": None,
                "completed_at": None,
                "satisfaction_rating": None,
                "notes": None
            }
            
            consultations_db[new_id] = new_consultation
            cls._current_queue_number += 1
            
            # Get patient info for response
            patient = patients_db.get(patient_id)
            
            return {
                "success": True,
                "consultation": new_consultation,
                "patient": patient,
                "queue_position": new_consultation["queue_number"],
                "message": f"Patient added to queue with number {new_consultation['queue_number']}"
            }
            
        except ValueError as e:
            return {
                "success": False,
                "error": str(e)
            }
        except Exception as e:
            print(f"Error adding to queue: {e}")
            return {
                "success": False,
                "error": f"Failed to add patient to queue: {str(e)}"
            }

    @classmethod
    def start_consultation(cls, consultation_id: int, doctor_id: int) -> Optional[Dict]:
        """Start a consultation"""
        try:
            consultation = consultations_db.get(consultation_id)
            
            if not consultation:
                return {
                    "success": False,
                    "error": "Consultation not found"
                }
            
            if consultation["status"] != "waiting":
                return {
                    "success": False,
                    "error": f"Cannot start consultation. Current status: {consultation['status']}"
                }
            
            # Check if doctor already has an active consultation
            for cons in consultations_db.values():
                if cons.get("doctor_id") == doctor_id and cons.get("status") == "in_progress":
                    # Optionally, we could auto-complete or warn
                    pass
            
            consultation["status"] = "in_progress"
            consultation["started_at"] = datetime.now()
            
            # Get patient info
            patient = patients_db.get(consultation["patient_id"])
            
            return {
                "success": True,
                "consultation": consultation,
                "patient": patient,
                "message": "Consultation started"
            }
            
        except Exception as e:
            print(f"Error starting consultation: {e}")
            return {
                "success": False,
                "error": f"Failed to start consultation: {str(e)}"
            }

    @classmethod
    def complete_consultation(
        cls,
        consultation_id: int,
        doctor_id: int,
        medication: str = None,
        instructions: Optional[str] = None,
        dosage: Optional[str] = None,
        diagnosis: Optional[str] = None,
        satisfaction_rating: Optional[int] = None
    ) -> Optional[Dict]:
        """Complete a consultation with prescription, but do NOT auto-start next patient."""
        try:
            consultation = consultations_db.get(consultation_id)
            
            if not consultation:
                return {
                    "success": False,
                    "error": "Consultation not found"
                }
            
            # --- LOGGING ---
            print(f"[complete] Attempting to complete consultation {consultation_id} for doctor {doctor_id}, current status: {consultation.get('status')}")
            # -----------------
            
            if consultation["status"] != "in_progress":
                return {
                    "success": False,
                    "error": f"Cannot complete consultation. Current status: {consultation['status']}"
                }
            
            if consultation["doctor_id"] != doctor_id:
                return {
                    "success": False,
                    "error": "This consultation is assigned to another doctor"
                }
            
            # Update consultation
            consultation["status"] = "treated"
            consultation["completed_at"] = datetime.now()
            if satisfaction_rating:
                consultation["satisfaction_rating"] = satisfaction_rating
            
            # --- LOGGING ---
            print(f"[complete] After update: status={consultation['status']}, completed_at={consultation.get('completed_at')}")
            # -----------------
            
            # Create prescription if medication provided
            prescription = None
            if medication:
                from src.models.patients import next_prescription_id, prescriptions_db
                
                new_prescription = {
                    "id": next_prescription_id,
                    "patient_id": consultation["patient_id"],
                    "doctor_id": doctor_id,
                    "consultation_id": consultation_id,
                    "medication": medication,
                    "instructions": instructions,
                    "dosage": dosage,
                    "diagnosis": diagnosis,
                    "created_at": datetime.now()
                }
                
                prescriptions_db[next_prescription_id] = new_prescription
                next_prescription_id += 1
                prescription = new_prescription
            
            # Do NOT automatically start the next patient - doctor will call call_next_patient explicitly
            
            # Get patient info
            patient = patients_db.get(consultation["patient_id"])
            
            return {
                "success": True,
                "consultation": consultation,
                "patient": patient,
                "prescription": prescription,
                "next_patient": None,  # No auto-start
                "message": "Consultation completed successfully"
            }
            
        except Exception as e:
            print(f"Error completing consultation: {e}")
            return {
                "success": False,
                "error": f"Failed to complete consultation: {str(e)}"
            }

    @classmethod
    def _process_next_in_queue(cls, doctor_id: int, department: str) -> Optional[Dict]:
        """Process the next patient in queue"""
        try:
            waiting = cls.get_waiting_patients(doctor_id, department)
            
            if waiting:
                # Get highest priority patient
                next_patient = waiting[0]
                consultation_id = next_patient["id"]
                consultation = consultations_db.get(consultation_id)
                
                if consultation:
                    consultation["status"] = "in_progress"
                    consultation["started_at"] = datetime.now()
                    return consultation
            return None
            
        except Exception as e:
            print(f"Error processing next in queue: {e}")
            return None

    @classmethod
    def get_queue_stats(cls) -> Dict:
        """Get queue statistics"""
        try:
            today_start = datetime.now().replace(hour=0, minute=0, second=0)
            
            # Count by status
            waiting_count = len([c for c in consultations_db.values() if c.get("status") == "waiting"])
            in_progress_count = len([c for c in consultations_db.values() if c.get("status") == "in_progress"])
            treated_today = len([
                c for c in consultations_db.values()
                if c.get("status") == "treated" 
                and c.get("completed_at") 
                and c["completed_at"] >= today_start
            ])
            
            # Count by priority
            emergency_waiting = len([
                c for c in consultations_db.values()
                if c.get("status") == "waiting" and c.get("priority") == 3
            ])
            
            urgent_waiting = len([
                c for c in consultations_db.values()
                if c.get("status") == "waiting" and c.get("priority") == 2
            ])
            
            normal_waiting = waiting_count - emergency_waiting - urgent_waiting
            
            # Average wait time
            wait_times = []
            for c in consultations_db.values():
                if c.get("status") == "waiting" and c.get("created_at"):
                    delta = datetime.now() - c["created_at"]
                    wait_times.append(delta.total_seconds() / 60)  # in minutes
            
            avg_wait_time = sum(wait_times) / len(wait_times) if wait_times else 0
            
            return {
                "waiting": waiting_count,
                "in_progress": in_progress_count,
                "treated_today": treated_today,
                "emergency_waiting": emergency_waiting,
                "urgent_waiting": urgent_waiting,
                "normal_waiting": normal_waiting,
                "current_queue_number": cls._current_queue_number,
                "average_wait_time_minutes": round(avg_wait_time, 1),
                "total_in_system": waiting_count + in_progress_count,
                "by_department": cls._get_stats_by_department()
            }
            
        except Exception as e:
            print(f"Error getting queue stats: {e}")
            return {
                "waiting": 0,
                "in_progress": 0,
                "treated_today": 0,
                "emergency_waiting": 0,
                "urgent_waiting": 0,
                "normal_waiting": 0,
                "current_queue_number": cls._current_queue_number,
                "average_wait_time_minutes": 0,
                "total_in_system": 0,
                "by_department": {}
            }

    @classmethod
    def _get_stats_by_department(cls) -> Dict:
        """Get queue statistics by department"""
        stats = {}
        
        try:
            for consultation in consultations_db.values():
                dept = consultation.get("department", "General")
                if dept not in stats:
                    stats[dept] = {
                        "waiting": 0,
                        "in_progress": 0,
                        "emergency": 0
                    }
                
                status = consultation.get("status")
                if status == "waiting":
                    stats[dept]["waiting"] += 1
                    if consultation.get("priority") == 3:
                        stats[dept]["emergency"] += 1
                elif status == "in_progress":
                    stats[dept]["in_progress"] += 1
            
        except Exception as e:
            print(f"Error getting department stats: {e}")
        
        return stats

    @classmethod
    def update_priority(cls, consultation_id: int, new_priority: int) -> Optional[Dict]:
        """Update priority of a waiting consultation"""
        try:
            consultation = consultations_db.get(consultation_id)
            
            if not consultation:
                return {
                    "success": False,
                    "error": "Consultation not found"
                }
            
            if consultation["status"] != "waiting":
                return {
                    "success": False,
                    "error": "Can only update priority for waiting patients"
                }
            
            old_priority = consultation["priority"]
            consultation["priority"] = new_priority
            
            return {
                "success": True,
                "consultation": consultation,
                "old_priority": old_priority,
                "new_priority": new_priority,
                "message": f"Priority updated from {old_priority} to {new_priority}"
            }
            
        except Exception as e:
            print(f"Error updating priority: {e}")
            return {
                "success": False,
                "error": f"Failed to update priority: {str(e)}"
            }

    @classmethod
    def remove_from_queue(cls, consultation_id: int) -> bool:
        """Remove a patient from queue (if they leave)"""
        try:
            consultation = consultations_db.get(consultation_id)
            
            if not consultation:
                return False
            
            if consultation["status"] != "waiting":
                return False
            
            consultation["status"] = "cancelled"
            consultation["completed_at"] = datetime.now()
            consultation["notes"] = "Removed from queue"
            
            return True
            
        except Exception as e:
            print(f"Error removing from queue: {e}")
            return False

    @classmethod
    def get_patient_queue_status(cls, patient_id: int) -> Optional[Dict]:
        """Get queue status for a specific patient"""
        try:
            for consultation in consultations_db.values():
                if consultation.get("patient_id") == patient_id:
                    status = consultation.get("status")
                    if status in ["waiting", "in_progress"]:
                        return {
                            "in_queue": True,
                            "consultation_id": consultation["id"],
                            "status": status,
                            "queue_number": consultation.get("queue_number"),
                            "priority": consultation.get("priority"),
                            "estimated_wait": cls._estimate_wait_time(consultation),
                            "department": consultation.get("department"),
                            "room": consultation.get("room")
                        }
            
            return {
                "in_queue": False,
                "message": "Patient not in queue"
            }
            
        except Exception as e:
            print(f"Error getting patient queue status: {e}")
            return {
                "in_queue": False,
                "error": str(e)
            }

    @classmethod
    def get_doctor_queue_stats(cls, doctor_id: int) -> Dict:
        """Get queue statistics for a specific doctor"""
        try:
            # Get waiting patients count
            waiting_patients = cls.get_waiting_patients(doctor_id=doctor_id)
            waiting_count = len(waiting_patients)
            
            # Get current consultation
            current_consultation = cls.get_current_consultation(doctor_id=doctor_id)
            
            # Get current patient details
            current_patient = None
            if current_consultation:
                current_patient = {
                    "id": current_consultation.get("id"),
                    "patient_id": current_consultation.get("patient_id"),
                    "patient_name": current_consultation.get("patient", {}).get("name"),
                    "status": current_consultation.get("status"),
                    "queue_number": current_consultation.get("queue_number"),
                    "waiting_time": current_consultation.get("waiting_time")
                }
            
            return {
                "waiting": waiting_count,
                "current_patient": current_patient
            }
            
        except Exception as e:
            print(f"Error getting doctor queue stats: {e}")
            return {
                "waiting": 0,
                "current_patient": None
            }

    # ========== UPDATED METHOD WITH SAFETY NET ==========
    @classmethod
    def call_next_patient(cls, doctor_id: int) -> Dict:
        """
        Call the next patient for a specific doctor.
        Returns the consultation that is now in progress.
        """
        try:
            # --- LOGGING ---
            print(f"[call_next] Checking for doctor {doctor_id}")
            # -----------------

            # --- SAFETY NET: Auto‑clear any stuck active consultation for this doctor ---
            cleared_any = False
            for cons in consultations_db.values():
                if cons.get("doctor_id") == doctor_id and cons.get("status") == "in_progress":
                    cons["status"] = "treated"
                    cons["completed_at"] = datetime.now()
                    cons["notes"] = "Auto‑completed by call_next_patient (cleanup)"
                    print(f"[call_next] Auto‑completed stuck consultation {cons['id']} for doctor {doctor_id}")
                    cleared_any = True
            if cleared_any:
                print("[call_next] Cleared at least one stuck consultation. Now proceeding to call next patient.")
            # ------------------------------------------------------------------------------

            # 1. Check if the doctor already has an active consultation
            current = cls.get_current_consultation(doctor_id=doctor_id)
            print(f"[call_next] get_current_consultation returned: {current}")

            if current:
                return {
                    "success": False,
                    "error": "Doctor already has an active consultation",
                    "message": "Please complete the current consultation first"
                }

            # 2. Get waiting patients for this doctor
            waiting_patients = cls.get_waiting_patients(doctor_id=doctor_id)

            if not waiting_patients:
                return {
                    "success": False,
                    "error": "No waiting patients for this doctor",
                    "message": "Queue is empty"
                }

            # 3. Take the first patient (highest priority, earliest queue number)
            next_patient = waiting_patients[0]
            consultation_id = next_patient["id"]

            # 4. Start the consultation
            result = cls.start_consultation(consultation_id, doctor_id)

            if not result.get("success"):
                return {
                    "success": False,
                    "error": result.get("error", "Failed to start consultation")
                }

            # 5. Return the consultation with patient data
            return {
                "success": True,
                "consultation": result["consultation"],
                "patient": result["patient"],
                "message": f"Patient {result['patient'].get('name')} called for consultation"
            }

        except Exception as e:
            print(f"Error calling next patient: {e}")
            return {
                "success": False,
                "error": f"Failed to call next patient: {str(e)}"
            }
    # ====================================================

    @classmethod
    def _estimate_wait_time(cls, consultation: Dict) -> str:
        """Estimate wait time for a patient"""
        try:
            if consultation["status"] == "in_progress":
                return "Currently in consultation"
            
            # Count patients ahead with same or higher priority
            position = 1
            for c in consultations_db.values():
                if c.get("status") == "waiting" and c.get("queue_number", 999) < consultation.get("queue_number", 999):
                    if c.get("priority", 1) >= consultation.get("priority", 1):
                        position += 1
            
            # Rough estimate: 15 minutes per patient
            estimated_minutes = position * 15
            
            if estimated_minutes < 60:
                return f"~{estimated_minutes} minutes"
            else:
                hours = estimated_minutes // 60
                minutes = estimated_minutes % 60
                return f"~{hours}h {minutes}m"
                
        except:
            return "Unknown"

    @classmethod
    def reassign_doctor(cls, consultation_id: int, new_doctor_id: int) -> Optional[Dict]:
        """Reassign consultation to another doctor"""
        try:
            consultation = consultations_db.get(consultation_id)
            
            if not consultation:
                return {
                    "success": False,
                    "error": "Consultation not found"
                }
            
            old_doctor_id = consultation["doctor_id"]
            consultation["doctor_id"] = new_doctor_id
            consultation["updated_at"] = datetime.now()
            
            return {
                "success": True,
                "consultation": consultation,
                "old_doctor_id": old_doctor_id,
                "new_doctor_id": new_doctor_id,
                "message": f"Reassigned to doctor {new_doctor_id}"
            }
            
        except Exception as e:
            print(f"Error reassigning doctor: {e}")
            return {
                "success": False,
                "error": f"Failed to reassign: {str(e)}"
            }

    @classmethod
    def get_queue_history(cls, limit: int = 50) -> List[Dict]:
        """Get historical queue data"""
        try:
            completed = [
                {
                    "id": c["id"],
                    "patient_id": c["patient_id"],
                    "patient_name": patients_db.get(c["patient_id"], {}).get("name", "Unknown"),
                    "department": c.get("department"),
                    "condition": c.get("condition"),
                    "priority": c.get("priority"),
                    "status": c.get("status"),
                    "created_at": c.get("created_at"),
                    "started_at": c.get("started_at"),
                    "completed_at": c.get("completed_at"),
                    "duration": cls._calculate_session_duration(c.get("started_at")) if c.get("completed_at") else None
                }
                for c in consultations_db.values()
                if c.get("status") in ["treated", "cancelled"]
            ]
            
            # Sort by completion date (most recent first)
            completed.sort(key=lambda x: x.get("completed_at") or x.get("created_at"), reverse=True)
            
            return completed[:limit]
            
        except Exception as e:
            print(f"Error getting queue history: {e}")
            return []
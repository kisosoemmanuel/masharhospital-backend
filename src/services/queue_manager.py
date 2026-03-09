from typing import Optional, List, Dict, Any
from datetime import datetime
from src.models.patients import (
    consultations_db, patients_db, prescriptions_db,
    Consultation, ConsultationCreate, PatientPriority, PatientStatus
)

class QueueManager:
    _instance = None
    _current_queue_number = 1
    
    @classmethod
    def initialize(cls):
        """Initialize queue manager"""
        if consultations_db:
            cls._current_queue_number = max([c["queue_number"] for c in consultations_db.values() if c["queue_number"]]) + 1
        else:
            cls._current_queue_number = 1

    @classmethod
    def get_current_consultation(cls, doctor_id: Optional[int] = None, department: Optional[str] = None) -> Optional[Dict]:
        """Get current consultation for a doctor/department"""
        for consultation in consultations_db.values():
            if consultation["status"] == "in_progress":
                if doctor_id and consultation["doctor_id"] != doctor_id:
                    continue
                if department and consultation["department"] != department:
                    continue
                
                # Enrich with patient data
                patient = patients_db.get(consultation["patient_id"])
                return {
                    **consultation,
                    "patient": patient
                }
        return None

    @classmethod
    def get_waiting_patients(cls, doctor_id: Optional[int] = None, department: Optional[str] = "Cardiology") -> List[Dict]:
        """Get waiting patients for a doctor/department"""
        waiting = []
        
        for consultation in consultations_db.values():
            if consultation["status"] == "waiting":
                if doctor_id and consultation["doctor_id"] != doctor_id:
                    continue
                if department and consultation["department"] != department:
                    continue
                
                # Enrich with patient data
                patient = patients_db.get(consultation["patient_id"])
                waiting.append({
                    **consultation,
                    "patient": patient
                })
        
        # Sort by priority (highest first) then queue number
        waiting.sort(key=lambda x: (-x["priority"], x["queue_number"]))
        return waiting

    @classmethod
    def add_to_queue(
        cls,
        patient_id: int,
        department: str = "Cardiology",
        condition: str = None,
        priority: int = 1,
        doctor_id: int = 1  # Default doctor
    ) -> Dict:
        """Add a patient to the queue"""
        if patient_id not in patients_db:
            raise ValueError(f"Patient {patient_id} not found")
        
        # Check if patient already in queue
        for consultation in consultations_db.values():
            if (consultation["patient_id"] == patient_id and 
                consultation["status"] in ["waiting", "in_progress"]):
                raise ValueError("Patient already in queue")
        
        new_id = max(consultations_db.keys()) + 1 if consultations_db else 1
        
        new_consultation = {
            "id": new_id,
            "patient_id": patient_id,
            "doctor_id": doctor_id,
            "department": department,
            "room": "4B",  # Default room
            "condition": condition or "General Consultation",
            "priority": priority,
            "status": "waiting",
            "queue_number": cls._current_queue_number,
            "created_at": datetime.now(),
            "started_at": None,
            "completed_at": None,
            "satisfaction_rating": None
        }
        
        consultations_db[new_id] = new_consultation
        cls._current_queue_number += 1
        
        return new_consultation

    @classmethod
    def start_consultation(cls, consultation_id: int, doctor_id: int) -> Optional[Dict]:
        """Start a consultation"""
        consultation = consultations_db.get(consultation_id)
        
        if not consultation:
            return None
        
        if consultation["status"] != "waiting":
            return None
        
        # Check if doctor already has an active consultation
        for cons in consultations_db.values():
            if cons["doctor_id"] == doctor_id and cons["status"] == "in_progress":
                # End the current consultation automatically?
                cons["status"] = "waiting"  # Move back to waiting
        
        consultation["status"] = "in_progress"
        consultation["started_at"] = datetime.now()
        
        return consultation

    @classmethod
    def complete_consultation(
        cls,
        consultation_id: int,
        doctor_id: int,
        medication: str,
        instructions: Optional[str] = None,
        dosage: Optional[str] = None
    ) -> Optional[Dict]:
        """Complete a consultation with prescription"""
        consultation = consultations_db.get(consultation_id)
        
        if not consultation:
            return None
        
        if consultation["status"] != "in_progress":
            return None
        
        if consultation["doctor_id"] != doctor_id:
            return None
        
        consultation["status"] = "treated"
        consultation["completed_at"] = datetime.now()
        
        # Create prescription
        from src.models.patients import next_prescription_id, prescriptions_db
        global next_prescription_id
        
        new_prescription = {
            "id": next_prescription_id,
            "patient_id": consultation["patient_id"],
            "doctor_id": doctor_id,
            "consultation_id": consultation_id,
            "medication": medication,
            "instructions": instructions,
            "dosage": dosage,
            "created_at": datetime.now()
        }
        
        prescriptions_db[next_prescription_id] = new_prescription
        next_prescription_id += 1
        
        # Process next in queue
        cls._process_next_in_queue(consultation["doctor_id"], consultation["department"])
        
        return {
            "consultation": consultation,
            "prescription": new_prescription
        }

    @classmethod
    def _process_next_in_queue(cls, doctor_id: int, department: str):
        """Process the next patient in queue"""
        waiting = cls.get_waiting_patients(doctor_id, department)
        
        if waiting:
            # Get highest priority patient
            next_patient = waiting[0]
            next_patient["status"] = "in_progress"
            next_patient["started_at"] = datetime.now()

    @classmethod
    def get_queue_stats(cls) -> Dict:
        """Get queue statistics"""
        waiting_count = len([c for c in consultations_db.values() if c["status"] == "waiting"])
        in_progress_count = len([c for c in consultations_db.values() if c["status"] == "in_progress"])
        
        today_start = datetime.now().replace(hour=0, minute=0, second=0)
        treated_today = len([
            c for c in consultations_db.values()
            if c["status"] == "treated" and c["completed_at"] and c["completed_at"] >= today_start
        ])
        
        # Count by priority
        emergency_waiting = len([
            c for c in consultations_db.values()
            if c["status"] == "waiting" and c["priority"] == 3
        ])
        
        urgent_waiting = len([
            c for c in consultations_db.values()
            if c["status"] == "waiting" and c["priority"] == 2
        ])
        
        return {
            "waiting": waiting_count,
            "in_progress": in_progress_count,
            "treated_today": treated_today,
            "emergency_waiting": emergency_waiting,
            "urgent_waiting": urgent_waiting,
            "normal_waiting": waiting_count - emergency_waiting - urgent_waiting,
            "current_queue_number": cls._current_queue_number
        }

    @classmethod
    def update_priority(cls, consultation_id: int, new_priority: int) -> Optional[Dict]:
        """Update priority of a waiting consultation"""
        consultation = consultations_db.get(consultation_id)
        
        if not consultation or consultation["status"] != "waiting":
            return None
        
        consultation["priority"] = new_priority
        return consultation

    @classmethod
    def remove_from_queue(cls, consultation_id: int) -> bool:
        """Remove a patient from queue (if they leave)"""
        consultation = consultations_db.get(consultation_id)
        
        if not consultation or consultation["status"] != "waiting":
            return False
        
        consultation["status"] = "cancelled"
        return True

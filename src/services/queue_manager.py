from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload
from datetime import datetime
from typing import Optional, List, Dict
from src.models.patients import Patient, Consultation, Prescription, PatientStatus

class QueueManager:
    
    @staticmethod
    def get_waiting_patients(db: Session, doctor_id: Optional[str] = None, department: Optional[str] = None) -> List[Consultation]:
        """Fetch waiting patients sorted by priority (Emergency first) and queue number.
           Returns ORM Consultation objects (internal use)."""
        query = db.query(Consultation).filter(Consultation.status == "waiting")
        
        if doctor_id:
            query = query.filter(Consultation.doctor_id == str(doctor_id))
        if department:
            query = query.filter(Consultation.department == department)
            
        # Priority 4 (Critical) -> 1 (Normal), then FIFO by queue number
        return query.order_by(Consultation.priority.desc(), Consultation.queue_number.asc()).all()

    @staticmethod
    def get_waiting_by_doctor(db: Session, doctor_id: str) -> List[Dict]:
        """
        Returns a list of waiting patients for a specific doctor, including patient name.
        Used by /api/queue/waiting endpoint.
        """
        consultations = db.query(Consultation).join(
            Patient, Consultation.patient_id == Patient.id
        ).filter(
            Consultation.doctor_id == str(doctor_id),
            Consultation.status == "waiting"
        ).order_by(
            Consultation.priority.desc(),
            Consultation.queue_number.asc()
        ).all()
        
        result = []
        for c in consultations:
            result.append({
                "id": c.id,
                "consultation_number": c.consultation_number,
                "patient_id": c.patient_id,
                "patient_name": c.patient.name,  # from joined Patient
                "department": c.department,
                "priority": c.priority,
                "condition": c.condition,
                "created_at": c.created_at.isoformat() if c.created_at else None,
                "status": c.status,
                "queue_number": c.queue_number,
                "room": c.room,
                "started_at": c.started_at.isoformat() if c.started_at else None,
                "completed_at": c.completed_at.isoformat() if c.completed_at else None,
                "doctor_id": c.doctor_id,
            })
        return result

    @staticmethod
    def get_current_patient(db: Session, doctor_id: str) -> Optional[Dict]:
        """
        Returns the patient currently 'in_progress' with this doctor, including patient name.
        Used by /api/queue/current endpoint.
        """
        consultation = db.query(Consultation).join(
            Patient, Consultation.patient_id == Patient.id
        ).filter(
            Consultation.doctor_id == str(doctor_id),
            Consultation.status == "in_progress"
        ).first()
        
        if not consultation:
            return None
        
        return {
            "id": consultation.id,
            "consultation_number": consultation.consultation_number,
            "patient_id": consultation.patient_id,
            "patient_name": consultation.patient.name,
            "department": consultation.department,
            "priority": consultation.priority,
            "condition": consultation.condition,
            "created_at": consultation.created_at.isoformat() if consultation.created_at else None,
            "status": consultation.status,
            "queue_number": consultation.queue_number,
            "room": consultation.room,
            "started_at": consultation.started_at.isoformat() if consultation.started_at else None,
            "completed_at": consultation.completed_at.isoformat() if consultation.completed_at else None,
            "doctor_id": consultation.doctor_id,
        }

    @staticmethod
    def add_to_queue(db: Session, patient_id: int, department: str, doctor_id: str, priority: int, condition: str) -> Dict:
        """Add a patient to the persistent database queue."""
        # 1. Check if already in queue
        existing = db.query(Consultation).filter(
            Consultation.patient_id == patient_id,
            Consultation.status.in_(["waiting", "in_progress"])
        ).first()
        
        if existing:
            return {"success": False, "error": "Patient is already in the queue."}

        # 2. Generate next queue number for the day
        today = datetime.utcnow().date()
        count = db.query(Consultation).filter(func.date(Consultation.created_at) == today).count()
        queue_num = count + 1

        # 3. Create record
        new_consultation = Consultation(
            patient_id=patient_id,
            doctor_id=str(doctor_id),
            department=department,
            priority=priority,
            condition=condition,
            status="waiting",
            queue_number=queue_num,
            consultation_number=f"C-{datetime.now().strftime('%Y%m%d')}-{queue_num:04d}"
        )

        db.add(new_consultation)
        db.commit()
        db.refresh(new_consultation)

        return {
            "success": True, 
            "consultation_id": new_consultation.id, 
            "queue_number": queue_num
        }

    @classmethod
    def call_next_patient(cls, db: Session, doctor_id: str) -> Dict:
        """Calls the next patient, includes safety net for stuck sessions."""
        
        # SAFETY NET: Clear any stuck 'in_progress' sessions for this doctor
        stuck_sessions = db.query(Consultation).filter(
            Consultation.doctor_id == str(doctor_id),
            Consultation.status == "in_progress"
        ).all()
        
        for session in stuck_sessions:
            session.status = "treated"
            session.completed_at = datetime.utcnow()
        
        db.commit()

        # Get next in line (using ORM objects)
        waiting = cls.get_waiting_patients(db, doctor_id=doctor_id)
        
        if not waiting:
            return {"success": False, "message": "Queue is empty."}

        next_patient = waiting[0]
        next_patient.status = "in_progress"
        next_patient.started_at = datetime.utcnow()
        
        db.commit()
        db.refresh(next_patient)

        # Return patient name via the relationship
        patient_name = next_patient.patient.name if next_patient.patient else "Unknown"
        
        return {
            "success": True,
            "patient_name": patient_name,
            "consultation_id": next_patient.id
        }

    @staticmethod
    def get_queue_stats(db: Session) -> Dict:
        """Get real-time statistics from the database."""
        waiting_count = db.query(Consultation).filter(Consultation.status == "waiting").count()
        active_count = db.query(Consultation).filter(Consultation.status == "in_progress").count()
        
        return {
            "waiting": waiting_count,
            "in_progress": active_count,
            "total_today": db.query(Consultation).filter(
                func.date(Consultation.created_at) == datetime.utcnow().date()
            ).count()
        } 
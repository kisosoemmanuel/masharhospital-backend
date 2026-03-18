from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from src.models.patients import (
    Patient, Consultation, Prescription,
    PatientCreate, PatientUpdate
)

class PatientService:
    @staticmethod
    def get_patients(db: Session, search: Optional[str] = None, status: Optional[str] = None) -> List[Patient]:
        """Get all patients from DB with optional search and status filters"""
        query = db.query(Patient)
        
        if search:
            query = query.filter(
                or_(
                    Patient.name.ilike(f"%{search}%"),
                    Patient.phone.ilike(f"%{search}%")
                )
            )
        
        # Note: Status usually lives in the Consultation table. 
        # For a "Patient Status" filter, we check their most recent consultation.
        patients = query.all()
        
        if status:
            filtered_patients = []
            for p in patients:
                latest = PatientService._get_latest_consultation(db, p.id)
                if latest and latest.status == status:
                    filtered_patients.append(p)
            return filtered_patients
            
        return patients

    @staticmethod
    def get_patient_by_id(db: Session, patient_id: int) -> Optional[Dict]:
        """Get patient by ID with full history from database"""
        patient = db.query(Patient).filter(Patient.id == patient_id).first()
        if not patient:
            return None
        
        # Get history
        consultations = db.query(Consultation).filter(Consultation.patient_id == patient_id).order_by(Consultation.created_at.desc()).all()
        prescriptions = db.query(Prescription).filter(Prescription.patient_id == patient_id).all()
        
        return {
            "patient": patient,
            "consultations": consultations,
            "prescriptions": prescriptions
        }

    @staticmethod
    def create_patient(db: Session, patient_data: PatientCreate) -> Patient:
        """Create a new patient record in the database"""
        new_patient = Patient(
            **patient_data.dict(),
            created_at=datetime.utcnow()
        )
        db.add(new_patient)
        db.commit()
        db.refresh(new_patient)
        return new_patient

    @staticmethod
    def update_patient(db: Session, patient_id: int, patient_update: PatientUpdate) -> Optional[Patient]:
        """Update existing patient information"""
        patient = db.query(Patient).filter(Patient.id == patient_id).first()
        if not patient:
            return None
        
        update_data = patient_update.dict(exclude_unset=True)
        for key, value in update_data.items():
            setattr(patient, key, value)
        
        patient.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(patient)
        return patient

    @staticmethod
    def delete_patient(db: Session, patient_id: int) -> bool:
        """Permanently delete a patient"""
        patient = db.query(Patient).filter(Patient.id == patient_id).first()
        if patient:
            db.delete(patient)
            db.commit()
            return True
        return False

    @staticmethod
    def _get_latest_consultation(db: Session, patient_id: int) -> Optional[Consultation]:
        """Helper to find a patient's most recent visit"""
        return db.query(Consultation)\
                 .filter(Consultation.patient_id == patient_id)\
                 .order_by(Consultation.created_at.desc())\
                 .first()

    # ----------------------
    # Statistics Logic
    # ----------------------
    @staticmethod
    def get_weekly_statistics(db: Session) -> Dict:
        """Get real-time hospital statistics for the last 7 days"""
        week_start = datetime.utcnow() - timedelta(days=7)
        
        # Counts using optimized SQL count queries
        new_patients = db.query(Patient).filter(Patient.created_at >= week_start).count()
        total_consultations = db.query(Consultation).filter(Consultation.created_at >= week_start).count()
        
        # Calculate Average Consultation Time (treated patients only)
        completed = db.query(Consultation).filter(
            Consultation.status == "treated",
            Consultation.completed_at >= week_start,
            Consultation.started_at != None
        ).all()
        
        avg_time = 14 # Default fallback
        if completed:
            times = [(c.completed_at - c.started_at).total_seconds() / 60 for c in completed]
            avg_time = round(sum(times) / len(completed))

        # Emergency count (Priority 3)
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0)
        emergencies = db.query(Consultation).filter(
            Consultation.created_at >= today_start,
            Consultation.priority == 3
        ).count()

        return {
            "patients_this_week": new_patients,
            "consultations_this_week": total_consultations,
            "avg_consultation_time": avg_time,
            "emergency_today": emergencies,
            "timestamp": datetime.utcnow().isoformat()
        }

    @staticmethod
    def get_doctor_statistics(db: Session, doctor_id: int) -> Dict:
        """Get performance and load stats for a specific doctor"""
        doc_query = db.query(Consultation).filter(Consultation.doctor_id == doctor_id)
        
        total = doc_query.count()
        waiting = doc_query.filter(Consultation.status == "waiting").count()
        in_progress = doc_query.filter(Consultation.status == "in_progress").count()
        
        return {
            "doctor_id": doctor_id,
            "total_patients": total,
            "waiting": waiting,
            "in_progress": in_progress,
            "completion_rate": round((total - waiting - in_progress) / max(total, 1) * 100)
        }
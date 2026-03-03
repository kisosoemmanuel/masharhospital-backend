import re
from datetime import datetime
from typing import Optional, List, Dict

class Patient:
    """Represents a single patient in the system."""

    def __init__(
        self,
        patient_id: str,
        name: str,
        age: int,
        gender: str,
        contact: str,
        email: str,
        patient_type: str,
        medical_history: Optional[str] = None
    ):
        self.patient_id = patient_id
        self.name = name
        self.age = age
        self.gender = gender
        self.contact = contact
        self.email = email
        self.patient_type = patient_type.lower()   
        self.medical_history = medical_history or ""
        self.registration_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Validation
    
    def validate(self) -> tuple[bool, str]:

        if not self.name or len(self.name.strip()) < 2:
            return False, "Name must be at least 2 characters long."

        if not isinstance(self.age, int) or self.age < 0 or self.age > 150:
            return False, "Age must be between 0 and 150."

        if self.gender.lower() not in ["male", "female", "other"]:
            return False, "Gender must be male, female, or other."

        phone_pattern = r"^\d{10}$"
        if not re.match(phone_pattern, self.contact):
            return False, "Phone number must be exactly 10 digits."

        email_pattern = r"^[^\s@]+@[^\s@]+\.[^\s@]+$"
        if not re.match(email_pattern, self.email):
            return False, "Invalid email format."

        return True, "Validation successful."

    # Convert to dictionary

    def to_dict(self) -> Dict:
        return {
            "patient_id": self.patient_id,
            "name": self.name,
            "age": self.age,
            "gender": self.gender,
            "contact": self.contact,
            "email": self.email,
            "patient_type": self.patient_type,
            "medical_history": self.medical_history,
            "registration_date": self.registration_date
        }

    def __str__(self):
         return f"Patient({self.patient_id}, {self.name}, Type: {self.patient_type}, Age: {self.age})"


# Patient Registry


class PatientRegistry:
    """Handles storing and managing multiple patients."""

    def __init__(self):
        self.patients: Dict[str, Patient] = {}

    # Register Patient
   
    def register_patient(self, patient: Patient) -> tuple[bool, str]:
        is_valid, message = patient.validate()
        if not is_valid:
            return False, message

        if patient.patient_id in self.patients:
            return False, f"Patient ID {patient.patient_id} already exists."

        self.patients[patient.patient_id] = patient
        return True, patient  # return the patient object on successful registration

     # Retrieve Patient
    def get_patient(self, patient_id: str) -> Optional[Patient]:
        return self.patients.get(patient_id)

    # Update Patient
    def update_patient(self, patient_id: str, **kwargs) -> tuple[bool, str]:

        if patient_id not in self.patients:
            return False, "Patient not found."

        patient = self.patients[patient_id]

        for key, value in kwargs.items():
            if hasattr(patient, key):
                setattr(patient, key, value)

        return patient.validate()

    # Delete Patient
    def delete_patient(self, patient_id: str) -> tuple[bool, str]:

        if patient_id in self.patients:
            del self.patients[patient_id]
            return True, "Patient deleted successfully."

        return False, "Patient not found."

    # List All Patients
    def list_all_patients(self) -> List[Dict]:
        return [patient.to_dict() for patient in self.patients.values()]

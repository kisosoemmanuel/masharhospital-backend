# patient_service.py

from patient import Patient, PatientRegistry

# Shared registry instance
registry = PatientRegistry()

def register_patient():
    """
    Interactive patient registration.
    Returns:
        tuple: (success: bool, patient: Patient | str)
    """
    print("\n--- Register New Patient ---")
    
    patient_id = input("Enter patient ID: ").strip()
    name = input("Enter patient name: ").strip()
    
    try:
        age = int(input("Enter patient age: ").strip())
    except ValueError:
        return False, "Age must be a number."
    
    gender = input("Enter gender (male/female/other): ").strip().lower()
    contact = input("Enter contact number (10 digits): ").strip()
    email = input("Enter email: ").strip()
    
    patient_type = input("Enter patient type (emergency/normal): ").strip().lower()
    
    # Create Patient object
    patient = Patient(
        patient_id=patient_id,
        name=name,
        age=age,
        gender=gender,
        contact=contact,
        email=email,
        patient_type=patient_type
    )
    
    # Register in registry
    success, result = registry.register_patient(patient)
    if not success:
        return False, result  # return error message
    return True, patient      # return patient object for QueueManager
from src.database import SessionLocal, engine
from src.models.admin import AdminModel, StaffCreate, StaffRole, Base, Staff

# 1. Ensure the database and tables exist
print("🔧 Checking database tables...")
Base.metadata.create_all(bind=engine)

def seed_doctor():
    db = SessionLocal()
    try:
        print("👨‍⚕️ Preparing to seed Doctor data...")
        
        # Check if doctor already exists using a direct query to avoid AdminModel attribute errors
        doctor_id = "DOC001"
        existing = db.query(Staff).filter(Staff.staff_id == doctor_id).first()
        
        if existing:
            print(f"⚠️ Doctor {doctor_id} already exists in the database.")
            return

        # Define the doctor details
        doctor_data = StaffCreate(
            staff_id=doctor_id,
            name="Dr. Charity",
            role=StaffRole.DOCTOR,
            phone="+254711223344",
            email="charity.doc@mashar.com",
            password="password123",  # Will be hashed by create_staff
            department="General Medicine",
            specialization="General Practitioner"
        )

        # Create the staff member
        AdminModel.create_staff(doctor_data, db)
        print(f"✅ Successfully seeded Doctor: {doctor_id} / password123")

    except Exception as e:
        print(f"❌ Error during seeding: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    seed_doctor()

from src.database import SessionLocal, engine
from src.models.admin import AdminModel, StaffCreate, StaffRole, Base

# Create tables if they don't exist
Base.metadata.create_all(bind=engine)

db = SessionLocal()
try:
    # 1. Clean up old test data if you want a fresh start
    # db.query(Staff).delete() 

    # 2. Create the Admin
    admin_data = StaffCreate(
        staff_id="A001",
        name="Charity Admin",
        role=StaffRole.ADMIN,
        phone="+254700000000",
        password="password123", # This will be hashed automatically by create_staff
        department="IT"
    )
    
    AdminModel.create_staff(admin_data, db)
    print("✅ Successfully seeded Admin: A001 / password123")

except Exception as e:
    print(f"❌ Error: {e}")
finally:
    db.close()
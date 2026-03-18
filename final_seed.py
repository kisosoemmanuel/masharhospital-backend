from src.database import SessionLocal, engine
from src.models.admin import AdminModel, StaffCreate, StaffRole, Base

# This ensures the tables are created in the .db file
print("🔧 Creating database tables...")
Base.metadata.create_all(bind=engine)

db = SessionLocal()
try:
    print("🌱 Seeding Admin user...")
    admin_data = StaffCreate(
        staff_id="A001",
        name="Charity Admin",
        role=StaffRole.ADMIN,
        phone="+254700000000",
        password="password123",
        department="IT"
    )
    
    AdminModel.create_staff(admin_data, db)
    print("✅ Successfully seeded Admin: A001 / password123")

except Exception as e:
    print(f"❌ Error: {e}")
finally:
    db.close()

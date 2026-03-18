from src.database import SessionLocal
from src.models.admin import Staff, StaffRole, hash_password

def reset_admin():
    db = SessionLocal()
    try:
        # 1. Look for existing admin
        admin = db.query(Staff).filter(Staff.staff_id == "A001").first()
        
        hashed_pw = hash_password("admin123")
        
        if admin:
            print(f"Updating existing admin A001...")
            admin.hashed_password = hashed_pw
            admin.role = StaffRole.ADMIN
        else:
            print(f"Creating new admin A001...")
            admin = Staff(
                staff_id="A001",
                name="System Admin",
                role=StaffRole.ADMIN,
                phone="+254700000000",
                email="admin@mashar.com",
                hashed_password=hashed_pw
            )
            db.add(admin)
        
        db.commit()
        print("✅ Success! You can now log in with A001 / admin123")
    except Exception as e:
        print(f"❌ Error: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    reset_admin()

from sqlalchemy import create_engine, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
import os

# Updated to use the consistent filename for Mashar Hospital
SQLALCHEMY_DATABASE_URL = "sqlite:///./mashar_hospital.db"

# SQLite-specific settings optimized for FastAPI
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    pool_pre_ping=True,
    # StaticPool is used if you switch to in-memory, 
    # but for a .db file, it ensures the connection stays robust
    poolclass=StaticPool, 
    connect_args={
        "check_same_thread": False,  
        "timeout": 30
    },
    echo=False  # Set to True only when debugging SQL queries
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    """
    Dependency to get DB session for FastAPI endpoints.
    Usage: db: Session = Depends(get_db)
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    """
    Initializes the database schema.
    Import all models here before calling create_all to ensure they are registered.
    """
    try:
        # Import models locally to avoid circular imports
        from src.models.admin import Staff, Bed, InventoryItem
        from src.models.receptionist import Receptionist
        from src.models.patients import Patient
        
        print("🛠️ Creating tables for Mashar Hospital...")
        Base.metadata.create_all(bind=engine)
        
        # Verify connection
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
        print("✅ Database initialized successfully.")
    except Exception as e:
        print(f"❌ Database initialization failed: {e}")

def drop_all_tables():
    """
    Drop all tables (used for testing or hard resets).
    """
    print("⚠️ Dropping all tables...")
    Base.metadata.drop_all(bind=engine)  

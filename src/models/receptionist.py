from typing import Optional, Dict, List
from pydantic import BaseModel
from datetime import datetime

# Receptionist "database"
receptionist_db: Dict[int, Dict] = {}
next_receptionist_id: int = 1

# Pydantic Models
class ReceptionistCreate(BaseModel):
    name: str
    phone: str
    email: Optional[str] = None
    department: Optional[str] = "General"

class ReceptionistUpdate(BaseModel):
    name: Optional[str]
    phone: Optional[str]
    email: Optional[str]
    department: Optional[str]

class ReceptionistModel:
    @staticmethod
    def create_receptionist(data: ReceptionistCreate) -> Dict:
        global next_receptionist_id
        r_id = next_receptionist_id
        receptionist_db[r_id] = {
            "id": r_id,
            "name": data.name,
            "phone": data.phone,
            "email": data.email,
            "department": data.department,
            "created_at": datetime.now(),
            "updated_at": None
        }
        next_receptionist_id += 1
        return receptionist_db[r_id]

    @staticmethod
    def update_receptionist(r_id: int, data: ReceptionistUpdate) -> Optional[Dict]:
        receptionist = receptionist_db.get(r_id)
        if not receptionist:
            return None
        for key, value in data.dict(exclude_unset=True).items():
            receptionist[key] = value
        receptionist["updated_at"] = datetime.now()
        return receptionist

    @staticmethod
    def get_all() -> List[Dict]:
        return list(receptionist_db.values())

    @staticmethod
    def get_by_id(r_id: int) -> Optional[Dict]:
        return receptionist_db.get(r_id)

    @staticmethod
    def delete_receptionist(r_id: int) -> bool:
        if r_id in receptionist_db:
            del receptionist_db[r_id]
            return True
        return False
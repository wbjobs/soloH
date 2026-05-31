from fastapi import Request
from typing import Optional
from app.db.material_db import MaterialDatabase


def get_db(request: Request) -> Optional[MaterialDatabase]:
    db = getattr(request.app.state, "db", None)
    if db is not None and db.connected:
        return db
    return None

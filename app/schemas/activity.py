# backend-server/app/schemas/activity.py
from pydantic import BaseModel
from datetime import datetime
from typing import List

class ActivityLogEntry(BaseModel):
    timestamp: datetime
    state: str
    app: str | None = None
    title: str | None = None

class ActivityPayload(BaseModel):
    employee_id: str
    logs: List[ActivityLogEntry]
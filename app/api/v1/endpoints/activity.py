# In your backend's API endpoint file (e.g., app/api/v1/activity.py)

import asyncio
from fastapi import APIRouter, Depends, Security, HTTPException, status
from sqlalchemy.orm import Session
from fastapi.security.api_key import APIKeyHeader

from app.schemas.activity import ActivityPayload
from app.core.config import settings
from app.db import session, models
from app.services import categorization

router = APIRouter()

# --- Security Dependency ---
api_key_header_scheme = APIKeyHeader(name="X-API-Key")

def get_api_key(key: str = Security(api_key_header_scheme)):
    """Checks if the provided API key matches the one in our settings."""
    if key == settings.DAEMON_API_KEY:
        return key
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid or missing API key"
        )

# --- API Endpoint (Corrected and Asynchronous) ---

@router.post("/activity")
async def receive_activity(
    payload: ActivityPayload,
    api_key: str = Depends(get_api_key),
    db: Session = Depends(session.get_db)
):
    """
    Receives a batch of activity logs, categorizes them concurrently,
    and saves them to the database with the correct duration.
    """
    user = db.query(models.User).filter(models.User.employee_id == payload.employee_id).first()
    if not user:
        raise HTTPException(status_code=404, detail=f"Employee ID '{payload.employee_id}' not found")

    # --- Concurrent AI Classification ---
    # Create a list of tasks to be run at the same time
    classification_tasks = [categorization.classify_activity(log) for log in payload.logs]
    
    # Run all the AI classification tasks concurrently
    processed_results = await asyncio.gather(*classification_tasks)

    # --- Database Saving ---
    logs_to_add = []
    # Loop through the original logs and the processed results together
    for original_log, (category, details) in zip(payload.logs, processed_results):
        
        db_log = models.ActivityLog(
            user_id=user.id,
            start_time=original_log.timestamp,
            # Use the duration sent by the daemon, not a hardcoded value
            duration_seconds=original_log.duration, 
            category=category,
            details=details
        )
        logs_to_add.append(db_log)
    
    if logs_to_add:
        db.add_all(logs_to_add)
        db.commit()

    return {"status": "ok", "logs_processed": len(logs_to_add)}
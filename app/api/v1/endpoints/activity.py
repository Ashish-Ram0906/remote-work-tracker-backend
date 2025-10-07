# backend-server/app/api/v1/endpoints/activity.py
from fastapi import APIRouter, Depends, Security, HTTPException, status
from fastapi.security.api_key import APIKeyHeader
from sqlalchemy.orm import Session

from app.schemas.activity import ActivityPayload
from app.core.config import settings
from app.db import session, models
from app.services import categorization

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
router = APIRouter()

async def get_api_key(key: str = Security(api_key_header)):
    if key == settings.DAEMON_API_KEY:
        return key
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid or missing API key"
        )

@router.post("/activity", status_code=status.HTTP_200_OK)
async def receive_activity(
    payload: ActivityPayload,
    api_key: str = Depends(get_api_key),
    db: Session = Depends(session.get_db)
):
    """
    Receives activity logs from a client daemon, categorizes them,
    and saves them to the database.
    """
    user = db.query(models.User).filter(models.User.employee_id == payload.employee_id).first()
    if not user:
        raise HTTPException(status_code=404, detail=f"Employee ID '{payload.employee_id}' not found")

    for log in payload.logs:
        category, details = categorization.classify_activity(log)

        # Assuming each log entry from the daemon represents a 5-second interval.
        # A more complex implementation could aggregate consecutive identical logs.
        db_log = models.ActivityLog(
            user_id=user.id,
            start_time=log.timestamp,
            duration_seconds=5,
            category=category,
            details=details
        )
        db.add(db_log)

    db.commit()

    return {"status": "ok", "logs_processed": len(payload.logs)}
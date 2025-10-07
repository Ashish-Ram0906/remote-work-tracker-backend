# backend-server/app/api/v1/endpoints/users.py
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import models, session
from app.core import security
from app.schemas import user as user_schema

router = APIRouter()

class PasswordUpdate(BaseModel):
    current_password: str
    new_password: str

@router.get("/me", response_model=user_schema.User)
def read_user_me(current_user: models.User = Depends(security.get_current_user)):
    """
    Get the details for the currently logged-in user.
    """
    return current_user

@router.put("/me/password", status_code=status.HTTP_204_NO_CONTENT)
def update_user_password(
    passwords: PasswordUpdate,
    db: Session = Depends(session.get_db),
    current_user: models.User = Depends(security.get_current_user)
):
    """
    Allows a logged-in user to change their own password.
    """
    if not security.verify_password(passwords.current_password, current_user.hashed_password):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Incorrect current password")
    
    current_user.hashed_password = security.get_password_hash(passwords.new_password)
    db.commit()
    return
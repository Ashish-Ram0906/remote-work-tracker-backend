# backend-server/app/api/v1/endpoints/auth.py
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from app.db import session, models
from app.core import security
from app.schemas import token as token_schema

router = APIRouter()

@router.post("/token", response_model=token_schema.Token)
def login(db: Session = Depends(session.get_db), form_data: OAuth2PasswordRequestForm = Depends()):
    # Database logic is now here
    user = db.query(models.User).filter(models.User.email == form_data.username).first()
    if not user or not security.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect username or password")
    
    access_token = security.create_access_token(data={"sub": user.email})
    return {"access_token": access_token, "token_type": "bearer"}
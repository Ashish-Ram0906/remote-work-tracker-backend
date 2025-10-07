# backend-server/app/core/security.py
# Handles password hashing, JWTs, and all role-checking dependencies.
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from jose import JWTError, jwt
from passlib.context import CryptContext
from datetime import datetime, timedelta

from app.db import models, session
from app.core.config import settings
from app.schemas import token as token_schema

# --- Password Hashing ---
pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")
def verify_password(plain: str, hashed: str) -> bool: return pwd_context.verify(plain, hashed)
# Change this function back
def get_password_hash(pwd: str) -> str: return pwd_context.hash(pwd)

# --- JWT Creation ---
def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

# --- Role-Checking Dependencies ---
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(session.get_db)) -> models.User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
        token_data = token_schema.TokenData(email=email)
    except JWTError:
        raise credentials_exception
    
    user = db.query(models.User).filter(models.User.email == token_data.email).first()
    if user is None:
        raise credentials_exception
    return user

def get_current_admin_user(current_user: models.User = Depends(get_current_user)):
    if current_user.role not in ["hr", "ceo"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions for this resource")
    return current_user

def get_current_manager_user(current_user: models.User = Depends(get_current_user)):
    if current_user.role != "manager":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Requires manager role")
    return current_user

def get_current_ceo_user(current_user: models.User = Depends(get_current_user)):
    if current_user.role != "ceo":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Requires CEO role")
    return current_user
# backend-server/app/api/v1/endpoints/admin.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload
from pydantic import BaseModel
from typing import List
import uuid

from app.db import models, session
from app.core import security
from app.schemas import user as user_schema

router = APIRouter()

# --- Pydantic Schemas for this endpoint's specific needs ---

class UserUpdate(BaseModel):
    role: str | None = None
    manager_id: int | None = None
    title: str | None = None

class PasswordReset(BaseModel):
    new_password: str

class TeamMember(BaseModel):
    name: str | None
    email: str

class TeamDetail(BaseModel):
    manager_id: int
    manager_name: str | None
    member_count: int
    members: List[TeamMember]

    class Config:
        orm_mode = True

# --- API Endpoints ---

@router.post("/users", response_model=user_schema.User, status_code=status.HTTP_201_CREATED)
def create_user(
    user_in: user_schema.UserCreate,
    db: Session = Depends(session.get_db),
    admin: models.User = Depends(security.get_current_admin_user)
):
    """ Creates a new user profile. Accessible by HR Admins and CEOs. """
    if db.query(models.User).filter(models.User.email == user_in.email).first():
        raise HTTPException(status_code=409, detail="Email already registered")

    hashed_password = security.get_password_hash(user_in.password)
    db_user = models.User(
        email=user_in.email,
        full_name=user_in.full_name,
        hashed_password=hashed_password,
        role=user_in.role,
        manager_id=user_in.manager_id,
        employee_id=f"emp_{uuid.uuid4()}",
        title=user_in.title
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

@router.get("/users", response_model=List[user_schema.User])
def get_all_users(
    db: Session = Depends(session.get_db),
    admin: models.User = Depends(security.get_current_admin_user)
):
    """ Retrieves a list of all users. Accessible by HR Admins and CEOs. """
    return db.query(models.User).all()

@router.put("/users/{user_id}", response_model=user_schema.User)
def update_user_details(
    user_id: int,
    updates: UserUpdate,
    db: Session = Depends(session.get_db),
    admin: models.User = Depends(security.get_current_admin_user)
):
    """ Updates a user's role or assigned manager. """
    db_user = db.query(models.User).filter(models.User.id == user_id).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")

    update_data = updates.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_user, field, value)
    
    db.commit()
    db.refresh(db_user)
    return db_user

@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_user(
    user_id: int,
    db: Session = Depends(session.get_db),
    admin: models.User = Depends(security.get_current_admin_user)
):
    """ Removes a user's account from the system. """
    db_user = db.query(models.User).filter(models.User.id == user_id).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    db.delete(db_user)
    db.commit()
    return

@router.put("/users/{user_id}/password", status_code=status.HTTP_204_NO_CONTENT)
def reset_user_password(
    user_id: int,
    password_in: PasswordReset,
    db: Session = Depends(session.get_db),
    admin: models.User = Depends(security.get_current_admin_user)
):
    """ Resets any user's password. """
    db_user = db.query(models.User).filter(models.User.id == user_id).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    db_user.hashed_password = security.get_password_hash(password_in.new_password)
    db.commit()
    return

@router.get("/installers/{employee_id}")
def generate_installer(
    employee_id: str,
    admin: models.User = Depends(security.get_current_admin_user)
):
    """ Generates a pre-configured daemon installer for an employee. """
    # In a real application, this would package and return a file.
    # For now, it confirms the action is authorized and the employee exists.
    return {"status": "installer_generation_authorized", "for_employee": employee_id}

@router.get("/teams", response_model=List[TeamDetail])
def get_all_teams(
    db: Session = Depends(session.get_db),
    admin: models.User = Depends(security.get_current_admin_user) # Secured for CEO/HR
):
    """ Retrieves a list of all teams (and their managers) in the company. """
    managers = db.query(models.User).filter(models.User.role == 'manager').options(joinedload(models.User.logs)).all()
    
    teams_output = []
    for manager in managers:
        team_members = db.query(models.User).filter(models.User.manager_id == manager.id).all()
        
        team_detail = TeamDetail(
            manager_id=manager.id,
            manager_name=manager.full_name,
            member_count=len(team_members),
            members=[TeamMember(name=tm.full_name, email=tm.email) for tm in team_members]
        )
        teams_output.append(team_detail)
        
    return teams_output
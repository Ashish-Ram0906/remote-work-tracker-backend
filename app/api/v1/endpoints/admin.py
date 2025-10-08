import subprocess
import tempfile
import shutil
from pathlib import Path
from fastapi import APIRouter, Depends, Security, HTTPException, status
# --- ADD BackgroundTasks ---
from fastapi import BackgroundTasks
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session, joinedload
from pydantic import BaseModel
from typing import List
import uuid

from app.core.config import settings
from app.db import models, session
from app.core import security
from app.schemas import user as user_schema

router = APIRouter()

# --- Pydantic Schemas ---
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
        from_attributes = True

# --- API Endpoints ---

@router.post("/users", response_model=user_schema.User, status_code=status.HTTP_201_CREATED)
def create_user(
    user_in: user_schema.UserCreate,
    db: Session = Depends(session.get_db),
    admin: models.User = Depends(security.get_current_admin_user)
):
    """ Creates a new user profile. """
    if db.query(models.User).filter(models.User.email == user_in.email).first():
        raise HTTPException(status_code=409, detail="Email already registered")

    hashed_password = security.get_password_hash(user_in.password)
    db_user = models.User(
        email=user_in.email, full_name=user_in.full_name,
        hashed_password=hashed_password, role=user_in.role,
        manager_id=user_in.manager_id, employee_id=f"emp_{uuid.uuid4()}",
        title=user_in.title
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_user(
    user_id: int,
    db: Session = Depends(session.get_db),
    admin: models.User = Depends(security.get_current_admin_user)
):
    """
    Deletes a user, but only if they are not a manager with active direct reports.
    """
    db_user = db.query(models.User).filter(models.User.id == user_id).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")

    # --- THIS IS THE NEW, SAFER LOGIC ---
    if db_user.role == 'manager':
        # Check if any other users are managed by this person
        report_count = db.query(models.User).filter(models.User.manager_id == user_id).count()
        if report_count > 0:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Cannot delete manager. They still have {report_count} direct reports. Please reassign them first."
            )
    
    # If the check passes, proceed with deletion
    db.delete(db_user)
    db.commit()
    return

# ... (The rest of your admin endpoints like GET, PUT, etc. remain the same) ...

@router.get("/users", response_model=List[user_schema.User])
def get_all_users(
    db: Session = Depends(session.get_db),
    admin: models.User = Depends(security.get_current_admin_user)
):
    """ Retrieves a list of all users. """
    return db.query(models.User).all()

@router.put("/users/{user_id}", response_model=user_schema.User)
def update_user_details(
    user_id: int,
    updates: UserUpdate,
    db: Session = Depends(session.get_db),
    admin: models.User = Depends(security.get_current_admin_user)
):
    """ Updates a user's role, manager, or title. """
    db_user = db.query(models.User).filter(models.User.id == user_id).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    update_data = updates.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_user, field, value)
    
    db.commit()
    db.refresh(db_user)
    return db_user

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
async def generate_linux_installer(
    employee_id: str,
    # --- ADD BackgroundTasks ---
    background_tasks: BackgroundTasks,
    db: Session = Depends(session.get_db),
    admin: models.User = Depends(security.get_current_admin_user)
):
    """
    Generates a pre-configured, single-file Linux daemon installer for an employee.
    """
    user = db.query(models.User).filter(models.User.employee_id == employee_id).first()
    if not user:
        raise HTTPException(status_code=404, detail=f"Employee ID '{employee_id}' not found")

    daemon_src_path = Path("/home/ashish-ram/Desktop/Final_Year/project/remote-work-tracker/client-daemon/src")
    if not daemon_src_path.is_dir():
        raise HTTPException(status_code=500, detail=f"Daemon source directory not found at: {daemon_src_path}")
    
    # --- CHANGE: Manually create temp directory ---
    temp_dir = tempfile.mkdtemp()
    
    try:
        temp_path = Path(temp_dir)
        
        config_content = f"""
[settings]
employee_id = {user.employee_id}
backend_url = {settings.DAEMON_BACKEND_URL}
daemon_api_key = {settings.DAEMON_API_KEY}
idle_threshold_seconds = 300
"""
        (temp_path / "config.ini").write_text(config_content)
        
        shutil.copytree(daemon_src_path, temp_path, dirs_exist_ok=True)
        
        installer_name = f"tracker-{user.employee_id}"
        # In your backend's installer API endpoint

        pyinstaller_command = [
            "pyinstaller",
            "--name", installer_name,
            "--onefile",
            "--noconsole",
            # This bundles the config.ini file
            f"--add-data", f"{(temp_path / 'config.ini')}:.",
            
            # --- Final, Complete List of Hidden Imports ---
            "--hidden-import", "apscheduler",
            "--hidden-import", "pynput.keyboard._xorg",
            "--hidden-import", "pynput.mouse._xorg",
            "--hidden-import", "psutil",
            "--hidden-import", "gi.repository",
            "--hidden-import", "gi.repository.Atspi",
            
            # The entry point to your script
            str(temp_path / "__main__.py")
        ]
        
        subprocess.run(pyinstaller_command, check=True, cwd=temp_path, capture_output=True, text=True)

        final_executable_path = temp_path / "dist" / installer_name
        if not final_executable_path.exists():
            raise HTTPException(status_code=500, detail="Installer build succeeded, but output file not found.")

        # --- CHANGE: Add the cleanup task to run AFTER the response is sent ---
        background_tasks.add_task(shutil.rmtree, temp_dir)

        return FileResponse(
            path=final_executable_path,
            filename=installer_name,
            media_type='application/octet-stream'
        )
    except subprocess.CalledProcessError as e:
        # If something goes wrong, still clean up the directory
        shutil.rmtree(temp_dir)
        print("PyInstaller Error:", e.stderr)
        raise HTTPException(status_code=500, detail="Failed to build the installer.")
    except Exception as e:
        # Catch any other error and ensure cleanup
        shutil.rmtree(temp_dir)
        raise e


@router.get("/teams", response_model=List[TeamDetail])
def get_all_teams(
    db: Session = Depends(session.get_db),
    admin: models.User = Depends(security.get_current_admin_user)
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

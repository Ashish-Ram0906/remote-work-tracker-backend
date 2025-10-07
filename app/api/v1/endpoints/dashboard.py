from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from pydantic import BaseModel
from typing import List
from datetime import date, timedelta # <-- ADD timedelta HERE

from app.db import models, session
from app.core import security

router = APIRouter()

# --- Pydantic Schemas (No changes here) ---
class CategorySummary(BaseModel):
    Work: int = 0
    Private: int = 0
    Idle: int = 0

class WorkDetail(BaseModel):
    app: str
    duration: int

class EmployeeReport(BaseModel):
    summary: CategorySummary
    work_details: List[WorkDetail]

class TeamMemberSummary(BaseModel):
    employee_id: str
    name: str | None
    summary: CategorySummary

class TeamReport(BaseModel):
    team_summary: CategorySummary
    members: List[TeamMemberSummary]

class DepartmentSummary(BaseModel):
    department_manager_id: int
    department_manager_name: str | None
    summary: CategorySummary

class CompanyReport(BaseModel):
    company_summary: CategorySummary
    by_department: List[DepartmentSummary]


# --- Helper Function to build reports ---

def get_employee_report_data(db: Session, user_id: int, start_date: date, end_date: date) -> EmployeeReport:
    """Helper function to generate a productivity report for a single user."""
    # --- FIX: Use timedelta for correct date calculation ---
    inclusive_end_date = end_date + timedelta(days=1)

    # Summary of time spent in each category
    summary_query = db.query(
        models.ActivityLog.category,
        func.sum(models.ActivityLog.duration_seconds).label("total_duration")
    ).filter(
        models.ActivityLog.user_id == user_id,
        models.ActivityLog.start_time >= start_date,
        models.ActivityLog.start_time < inclusive_end_date # <-- Use corrected date
    ).group_by(models.ActivityLog.category).all()
    
    summary = CategorySummary(**{item.category: item.total_duration for item in summary_query})

    # Detailed breakdown of time spent on work applications
    work_details_query = db.query(
        models.ActivityLog.details,
        func.sum(models.ActivityLog.duration_seconds).label("total_duration")
    ).filter(
        models.ActivityLog.user_id == user_id,
        models.ActivityLog.category == 'Work',
        models.ActivityLog.start_time >= start_date,
        models.ActivityLog.start_time < inclusive_end_date # <-- Use corrected date
    ).group_by(models.ActivityLog.details).order_by(func.sum(models.ActivityLog.duration_seconds).desc()).all()

    work_details = [WorkDetail(app=item.details or "Unknown", duration=item.total_duration) for item in work_details_query]
    
    return EmployeeReport(summary=summary, work_details=work_details)


# --- API Endpoints ---

@router.get("/me", response_model=EmployeeReport)
def read_dashboard_me(
    start_date: date,
    end_date: date,
    db: Session = Depends(session.get_db),
    current_user: models.User = Depends(security.get_current_user)
):
    """ Returns the productivity report for the currently logged-in user. """
    return get_employee_report_data(db=db, user_id=current_user.id, start_date=start_date, end_date=end_date)


@router.get("/team", response_model=TeamReport)
def read_dashboard_team(
    start_date: date,
    end_date: date,
    db: Session = Depends(session.get_db),
    manager: models.User = Depends(security.get_current_manager_user)
):
    """ Returns an aggregated report for the manager's direct reports. """
    inclusive_end_date = end_date + timedelta(days=1)
    team_members = db.query(models.User).filter(models.User.manager_id == manager.id).all()
    if not team_members:
        return TeamReport(team_summary=CategorySummary(), members=[])

    team_member_ids = [member.id for member in team_members]
    
    team_summary_query = db.query(
        models.ActivityLog.category,
        func.sum(models.ActivityLog.duration_seconds).label("total_duration")
    ).filter(
        models.ActivityLog.user_id.in_(team_member_ids),
        models.ActivityLog.start_time >= start_date,
        models.ActivityLog.start_time < inclusive_end_date # <-- Use corrected date
    ).group_by(models.ActivityLog.category).all()

    team_summary = CategorySummary(**{item.category: item.total_duration for item in team_summary_query})

    member_summaries = []
    for member in team_members:
        report = get_employee_report_data(db=db, user_id=member.id, start_date=start_date, end_date=end_date)
        member_summaries.append(TeamMemberSummary(employee_id=member.employee_id, name=member.full_name, summary=report.summary))

    return TeamReport(team_summary=team_summary, members=member_summaries)

@router.get("/team/{employee_id}", response_model=EmployeeReport)
def read_team_member_dashboard(
    employee_id: str,
    start_date: date,
    end_date: date,
    db: Session = Depends(session.get_db),
    manager: models.User = Depends(security.get_current_manager_user)
):
    """ Drills down to the detailed report for a single employee who must be a direct report. """
    team_member = db.query(models.User).filter(models.User.employee_id == employee_id).first()
    if not team_member or team_member.manager_id != manager.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view reports for your direct reports."
        )
    return get_employee_report_data(db=db, user_id=team_member.id, start_date=start_date, end_date=end_date)


@router.get("/company", response_model=CompanyReport)
def read_dashboard_company(
    start_date: date,
    end_date: date,
    db: Session = Depends(session.get_db),
    ceo: models.User = Depends(security.get_current_ceo_user)
):
    """ Returns a high-level, aggregated report for the entire company. """
    inclusive_end_date = end_date + timedelta(days=1)

    # Overall company summary
    company_summary_query = db.query(
        models.ActivityLog.category,
        func.sum(models.ActivityLog.duration_seconds).label("total_duration")
    ).filter(
        models.ActivityLog.start_time >= start_date,
        models.ActivityLog.start_time < inclusive_end_date # <-- Use corrected date
    ).group_by(models.ActivityLog.category).all()
    company_summary = CategorySummary(**{item.category: item.total_duration for item in company_summary_query})

    # Breakdown by department (team)
    by_department = []
    managers = db.query(models.User).filter(models.User.role == 'manager').all()

    for manager in managers:
        team_member_ids_query = db.query(models.User.id).filter(models.User.manager_id == manager.id)
        team_member_ids = [id_tuple[0] for id_tuple in team_member_ids_query.all()]

        if not team_member_ids:
            continue

        dept_summary_query = db.query(
            models.ActivityLog.category,
            func.sum(models.ActivityLog.duration_seconds).label("total_duration")
        ).filter(
            models.ActivityLog.user_id.in_(team_member_ids),
            models.ActivityLog.start_time >= start_date,
            models.ActivityLog.start_time < inclusive_end_date # <-- Use corrected date
        ).group_by(models.ActivityLog.category).all()
        
        dept_summary = CategorySummary(**{item.category: item.total_duration for item in dept_summary_query})

        by_department.append(DepartmentSummary(
            department_manager_id=manager.id,
            department_manager_name=manager.full_name,
            summary=dept_summary
        ))

    return CompanyReport(company_summary=company_summary, by_department=by_department)


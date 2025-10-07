# backend-server/app/schemas/user.py
from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import date

class UserBase(BaseModel):
    email: EmailStr
    full_name: Optional[str] = None
    title: Optional[str] = None
    
class UserCreate(UserBase):
    password: str
    role: str
    manager_id: Optional[int] = None

class User(UserBase):
    id: int
    employee_id: str
    role: str
    manager_id: Optional[int] = None
    

    class Config:
        # This line is updated
        from_attributes = True

class HolidayBase(BaseModel):
    start_date: date
    end_date: date
    reason: Optional[str] = None

class HolidayCreate(HolidayBase):
    pass

class Holiday(HolidayBase):
    id: int
    user_id: int

    class Config:
        # This line is updated
        from_attributes = True
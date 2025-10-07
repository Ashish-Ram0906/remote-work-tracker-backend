# backend-server/app/db/models.py
from sqlalchemy import ( Column, Integer, String, ForeignKey, DateTime, Text, CheckConstraint )
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(String(50), unique=True, nullable=False, index=True)
    full_name = Column(String(100))
    title = Column(String(100), nullable=True)
    email = Column(String(100), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False)
    manager_id = Column(Integer, ForeignKey("users.id"))
    __table_args__ = ( CheckConstraint("role IN ('employee', 'manager', 'hr', 'ceo')"), )
    logs = relationship("ActivityLog", back_populates="owner")

class ActivityLog(Base):
    __tablename__ = "activity_logs"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    start_time = Column(DateTime(timezone=True), nullable=False)
    duration_seconds = Column(Integer, nullable=False)
    category = Column(String(20), nullable=False)
    details = Column(Text, nullable=True)
    __table_args__ = ( CheckConstraint("category IN ('Work', 'Private', 'Idle')"), )
    owner = relationship("User", back_populates="logs")
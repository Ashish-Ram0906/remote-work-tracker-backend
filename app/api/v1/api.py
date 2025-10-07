# backend-server/app/api/v1/api.py
from fastapi import APIRouter
# Add 'users' to this import
from app.api.v1.endpoints import admin, dashboard, activity, users

api_router = APIRouter()

# Add the new router here
api_router.include_router(users.router, prefix="/users", tags=["Users"])

api_router.include_router(admin.router, prefix="/admin", tags=["Admin"])
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["Dashboard"])
api_router.include_router(activity.router, tags=["Daemon"])
# backend-server/app/main.py
from fastapi import FastAPI
from app.api.v1.api import api_router

# Import the specific router from the auth endpoint file
from app.api.v1.endpoints import auth

app = FastAPI(title="Remote Work Tracker API")

# Include the main router for all routes prefixed with /api/v1
app.include_router(api_router, prefix="/api/v1")

# Include the auth router separately for the /auth prefix
app.include_router(auth.router, prefix="/auth")

@app.get("/")
def read_root():
    return {"message": "Welcome to the Remote Work Tracker API"}
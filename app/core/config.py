# backend-server/app/core/config.py
from pydantic_settings import BaseSettings; from dotenv import load_dotenv
load_dotenv()
class Settings(BaseSettings):
    DATABASE_URL: str; DAEMON_API_KEY: str; PERPLEXITY_AI_API_KEY: str; DAEMON_BACKEND_URL: str
    JWT_SECRET_KEY: str; JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24
settings = Settings()
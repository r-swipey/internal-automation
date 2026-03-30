from pathlib import Path
from pydantic_settings import BaseSettings

_ENV_FILE = Path(__file__).resolve().parent.parent.parent / ".env"


class Settings(BaseSettings):
    supabase_url: str
    supabase_key: str
    swipey_api_url: str = "https://api.swipey.app"
    swipey_api_key: str = "stub-local-dev"
    swipey_bp_api_key: str = ""
    swipey_company_uuid: str = ""
    secret_key: str = "change-me-in-production-32-chars!!"
    app_base_url: str = "http://localhost:8000"
    frontend_url: str = "http://localhost:3000"
    environment: str = "development"

    class Config:
        env_file = str(_ENV_FILE)
        env_file_encoding = "utf-8"


settings = Settings()

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "JANASEVA"
    database_url: str = "sqlite:///./janaseva.db"
    jwt_secret: str = "development-only-change-me"
    jwt_expire_minutes: int = 60
    frontend_origin: str = "http://localhost:5173"
    upload_dir: str = "./uploads"
    max_upload_mb: int = 5
    gemini_api_key: str = ""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()

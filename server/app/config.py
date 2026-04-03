from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    database_url: str
    database_url_sync: str
    redis_url: str = "redis://localhost:6379/0"
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 10080
    upload_dir: str = "uploads"
    debug: bool = False

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()

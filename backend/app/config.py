"""
config.py
---------
Centralized, type-safe application configuration.

Instead of scattering `os.environ.get(...)` calls across the codebase
(a common beginner mistake), every setting is declared once here using
pydantic-settings. This gives us validation, defaults, and autocomplete
everywhere the settings are used -- a standard production practice.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # ----- App -----
    environment: str = "development"
    app_name: str = "SentinelAI"
    api_prefix: str = "/api/v1"

    # ----- Database -----
    database_url: str = "sqlite:///./app/data/sentinelai.db"

    # ----- Security / JWT -----
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    # ----- File Encryption -----
    fernet_key: str

    # ----- Automated Backup -----
    backup_dir: str = "./backups"
    backup_interval_minutes: int = 30

    # ----- Log Monitoring -----
    log_watch_dir: str = "./logs"
    scan_interval_seconds: int = 15

    # ----- CORS -----
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # ----- Anthropic (Chatbot) -----
    anthropic_api_key: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    """
    Cached settings loader. Using a function (instead of a bare module-level
    instance) makes it trivial to override settings in tests via
    dependency-injection / monkeypatching.
    """
    return Settings()
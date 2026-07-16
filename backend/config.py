"""Settings, loaded from environment / .env — no secrets hardcoded."""
import os
from pathlib import Path

from dotenv import load_dotenv

# Load the repo-root .env explicitly so the app works from any working directory.
load_dotenv(Path(__file__).resolve().parent.parent / ".env")


class Settings:
    MONGODB_URI: str = os.getenv("MONGODB_URI", "")
    DB_NAME: str = os.getenv("DB_NAME", "aarambhini")
    APP_ENV: str = os.getenv("APP_ENV", "dev")
    SESSION_SECRET: str = os.getenv("SESSION_SECRET", "")
    SESSION_TTL_HOURS: int = int(os.getenv("SESSION_TTL_HOURS", "12"))

    @property
    def has_db(self) -> bool:
        return bool(self.MONGODB_URI)

    @property
    def is_dev(self) -> bool:
        return self.APP_ENV == "dev"


settings = Settings()

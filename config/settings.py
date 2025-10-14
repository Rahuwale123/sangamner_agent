from __future__ import annotations

import os
from functools import lru_cache
from typing import Optional

from dotenv import load_dotenv


load_dotenv()


class Settings:
    """Application settings loaded from environment variables.

    Keep all credentials and config centralized here.
    """

    app_env: str = os.getenv("APP_ENV", "development")
    google_api_key: Optional[str] = "AIzaSyBHrciebnphZXCmEbt0NyX7dm4VZgIPx6Y"
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
    temperature: float = float(os.getenv("MODEL_TEMPERATURE", "0.3"))
    top_p: float = float(os.getenv("MODEL_TOP_P", "0.9"))
    search_api_url: Optional[str] = os.getenv(
        "SEARCH_API_URL", "http://127.0.0.1:8000/data/search/nearby"
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()

"""
config.py
---------
Centralised configuration loaded from environment variables via python-dotenv.
"""

import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Application-wide configuration settings."""

    # OpenAI
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    # Telegram
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")

    # Backend URL (used by Telegram bot and CLI to reach FastAPI)
    BACKEND_URL: str = os.getenv("BACKEND_URL", "http://localhost:8000")

    # Session limits
    MAX_HISTORY_MESSAGES: int = 10   # trigger trim when this many messages exist
    KEEP_HISTORY_MESSAGES: int = 6   # keep this many recent messages after trim

    # Server
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))


config = Config()

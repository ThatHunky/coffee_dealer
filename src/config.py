"""Configuration management for the Coffee Dealer bot."""

import os

from dotenv import load_dotenv

load_dotenv()


class Config:
    """Application configuration."""

    # Telegram
    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
    ADMIN_IDS: list[int] = [
        int(x.strip()) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()
    ]

    # Google Gemini
    GOOGLE_API_KEY: str = os.getenv("GOOGLE_API_KEY", "")
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.0-flash-exp")

    # Application
    TZ: str = os.getenv("TZ", "Europe/Kyiv")
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./schedule.db")

    @classmethod
    def validate(cls) -> None:
        """Validate required configuration."""
        errors = []
        if not cls.BOT_TOKEN:
            errors.append("BOT_TOKEN is not set")
        if not cls.GOOGLE_API_KEY:
            errors.append("GOOGLE_API_KEY is not set")
        if not cls.ADMIN_IDS:
            errors.append("ADMIN_IDS is not set")

        if errors:
            raise ValueError(f"Configuration errors: {', '.join(errors)}")


config = Config()

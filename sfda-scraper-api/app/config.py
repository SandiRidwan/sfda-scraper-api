from functools import lru_cache
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    # Telegram
    telegram_bot_token: Optional[str] = None
    telegram_chat_id: Optional[str] = None

    # App
    app_env: str = "development"
    app_debug: bool = False
    database_url: str = "./data/sfda.db"

    # SFDA
    sfda_max_pages: int = 438
    sfda_timeout: int = 30
    sfda_retry_max: int = 5
    sfda_delay_min: float = 0.8
    sfda_delay_max: float = 2.0

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
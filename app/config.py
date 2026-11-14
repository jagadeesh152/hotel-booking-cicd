"""Environment-based configuration (12-factor). No secrets live in code."""

import os


class Settings:
    def __init__(self) -> None:
        self.database_url: str = os.environ.get(
            "DATABASE_URL",
            "postgresql+psycopg2://hotel:hotel@localhost:5432/hotel",
        )
        self.app_version: str = os.environ.get("APP_VERSION", "dev")
        self.log_level: str = os.environ.get("LOG_LEVEL", "INFO").upper()
        self.max_stay_nights: int = int(os.environ.get("MAX_STAY_NIGHTS", "30"))


settings = Settings()

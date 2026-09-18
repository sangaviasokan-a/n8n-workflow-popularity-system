from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    app_name: str = Field(
        default="n8n Workflow Popularity Intelligence System"
    )
    app_env: str = Field(default="development")
    debug: bool = Field(default=False)

    # Database
    postgres_user: str = Field(default="popularity_user")
    postgres_password: str = Field(default="change_this_password")
    postgres_db: str = Field(default="popularity_db")
    postgres_host: str = Field(default="localhost")
    postgres_port: int = Field(default=5432)

    database_url: str = Field(
        default="postgresql+psycopg://"
        "popularity_user:change_this_password"
        "@localhost:5432/popularity_db"
    )

    # External APIs
    youtube_api_key: str | None = Field(default=None)

    # API
    api_host: str = Field(default="0.0.0.0")
    api_port: int = Field(default=8000)

    # CORS
    cors_origins: str = Field(
        default="http://localhost:3000,http://localhost:8000"
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @property
    def cors_origins_list(self) -> list[str]:
        """Return CORS origins as a cleaned list."""
        return [
            origin.strip()
            for origin in self.cors_origins.split(",")
            if origin.strip()
        ]


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings."""
    return Settings()


settings = get_settings()
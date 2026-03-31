from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = Field(default="DKB Runtime", alias="APP_NAME")
    app_env: str = Field(default="local", alias="APP_ENV")
    api_v1_prefix: str = Field(default="/api/v1", alias="API_V1_PREFIX")
    database_url: str = Field(
        default="postgresql+psycopg://dkb:dkb@localhost:5432/dkb",
        alias="DATABASE_URL",
    )
    default_ts_config: str = Field(default="simple", alias="DEFAULT_TS_CONFIG")
    vector_dimensions: int = Field(default=1536, alias="VECTOR_DIMENSIONS")
    cors_origins: str = Field(default="", alias="CORS_ORIGINS")

    dkb_jwt_secret: str = Field(default="", alias="DKB_JWT_SECRET")
    dkb_jwt_algorithm: str = Field(default="HS256", alias="DKB_JWT_ALGORITHM")
    dkb_jwt_expire_minutes: int = Field(default=30, alias="DKB_JWT_EXPIRE_MINUTES")
    dkb_admin_user: str = Field(default="", alias="DKB_ADMIN_USER")
    dkb_admin_password: str = Field(default="", alias="DKB_ADMIN_PASSWORD")

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()

from __future__ import annotations

from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class APISettings(BaseModel):
    chaos_key: Optional[str] = Field(None, alias="CHAOS_API_KEY")
    github_token: Optional[str] = Field(None, alias="GITHUB_TOKEN")
    gitlab_token: Optional[str] = Field(None, alias="GITLAB_TOKEN")


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_nested_delimiter="__")

    data_dir: Path = Field(default=Path("/data"), env="WATCHMYSIX_DATA_DIR")
    max_concurrency: int = Field(default=4, env="WATCHMYSIX_MAX_CONCURRENCY")
    log_buffer_lines: int = Field(default=2000, env="WATCHMYSIX_LOG_BUFFER_LINES")
    api: APISettings = Field(default_factory=APISettings)

    @field_validator("data_dir", mode="before")
    def _expand_path(cls, value: Path | str) -> Path:
        path = Path(value).expanduser().resolve()
        path.mkdir(parents=True, exist_ok=True)
        return path

    @field_validator("max_concurrency")
    def _ensure_positive(cls, value: int) -> int:
        if value < 1:
            raise ValueError("max_concurrency must be greater than zero")
        return value


def get_settings() -> AppSettings:
    return AppSettings()


settings = get_settings()

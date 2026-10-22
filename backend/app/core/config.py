from functools import lru_cache
from pathlib import Path

from pydantic import AnyHttpUrl, Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[3] / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        hide_input_in_errors=True,
    )

    database_url: SecretStr = Field(min_length=1)
    jwt_secret_key: SecretStr = Field(min_length=1)
    jira_instance_url: AnyHttpUrl
    jira_user_email: str = Field(min_length=1)
    jira_api_token: SecretStr = Field(min_length=1)
    jira_project_key: str = "SOL"
    jira_webhook_secret: SecretStr = SecretStr("")
    allowed_origins: str = "http://localhost:5173"
    environment: str = "development"

    @field_validator("jira_project_key")
    @classmethod
    def validate_project_key(cls, value: str) -> str:
        if not value or not value.replace("_", "").isalnum():
            raise ValueError("JIRA_PROJECT_KEY debe ser una clave de proyecto válida.")
        return value

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.allowed_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()

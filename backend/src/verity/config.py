from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from pathlib import Path

class ApplicationSettings(BaseSettings):
    model_config = SettingsConfigDict(
        extra="ignore",
        hide_input_in_errors=True,
    )

    postgresHost: str = Field(
        validation_alias="POSTGRES_HOST",
        min_length=1,
    )
    postgresPort: int = Field(
        validation_alias="POSTGRES_HOST_PORT",
        ge=1,
        le=65535,
    )
    postgresDatabase: str = Field(
        validation_alias="POSTGRES_DB",
        min_length=1,
    )
    postgresUsername: str = Field(
        validation_alias="POSTGRES_USER",
        min_length=1,
    )
    postgresPassword: SecretStr = Field(
        validation_alias="POSTGRES_PASSWORD",
        min_length=1,
    )
    
    documentStorageRoot: Path = Path("storage/documents")

    maxDocumentSizeBytes: int = Field(
        default=10 * 1024 * 1024,
        gt=0,
    )
    
    groqApiKey: SecretStr | None = Field(
        default=None,
        validation_alias="GROQ_API_KEY",
    )

    groqModel: str = Field(
        default="openai/gpt-oss-20b",
        validation_alias="GROQ_MODEL",
        min_length=1,
    )
    
    maxAiInputCharacters: int = Field(
        default=40_000,
        validation_alias="MAX_AI_INPUT_CHARACTERS",
        ge=1,
    )
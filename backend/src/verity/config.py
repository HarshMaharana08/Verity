from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


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
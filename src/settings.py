from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

ENV_FILE: str = ".env"


class DBSettings(BaseSettings):
    HOST: str
    PORT: str
    USER: str
    NAME: str
    PASSWORD: str
    POOL_SIZE: int = 5
    MAX_OVERFLOW: int = 10
    POOL_RECYCLE: int = 3600
    POOL_PRE_PING: bool = True
    POOL_RESET_ON_RETURN: str | None = "rollback"

    @property
    def DATABASE_URL(self) -> str:
        return (
            f"postgresql+asyncpg://{self.USER}:{self.PASSWORD}@{self.HOST}:{self.PORT}/{self.NAME}"
        )

    model_config = SettingsConfigDict(env_file=ENV_FILE, env_prefix="DB_", extra="ignore")


class OpenAISettings(BaseSettings):
    API_KEY: str
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    EMBEDDING_DIMENSIONS: int = 1536
    EMBEDDING_INSTRUMENT: bool = True
    EMBEDDING_INSTRUMENT_INCLUDE_CONTENT: bool = False
    EMBEDDING_INSTRUMENT_INCLUDE_BINARY_CONTENT: bool = False
    CHAT_MODEL: str = "openai:gpt-4o-mini"

    model_config = SettingsConfigDict(env_file=ENV_FILE, env_prefix="OPENAI_", extra="ignore")


class S3Settings(BaseSettings):
    ENDPOINT_URL: str = ""
    ACCESS_KEY_ID: str = ""
    SECRET_ACCESS_KEY: str = ""
    BUCKET_NAME: str = ""
    REGION: str = "us-east-1"

    model_config = SettingsConfigDict(env_file=ENV_FILE, env_prefix="S3_", extra="ignore")


class Settings(BaseSettings):
    SERVICE_NAME: str = "Template project"
    ENV: Literal["prod", "demo", "test"] = "demo"
    LOGFIRE_TOKEN: str | None = None
    LOGFIRE_PYDANTIC_AI_INCLUDE_CONTENT: bool = True
    LOGFIRE_PYDANTIC_AI_INCLUDE_BINARY_CONTENT: bool = False
    LOGFIRE_PYDANTIC_AI_VERSION: Literal[1, 2, 3] = 2
    PROJECT_NAME: str = "Template project"

    database: DBSettings = DBSettings()
    s3: S3Settings = S3Settings()
    openai: OpenAISettings = OpenAISettings()

    model_config = SettingsConfigDict(env_file=ENV_FILE, extra="ignore")


settings = Settings()

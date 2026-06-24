from functools import lru_cache
from typing import Optional
from urllib.parse import quote_plus

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration loaded from environment variables or .env."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    aws_region: str = Field(default="us-east-1", alias="AWS_REGION")
    s3_bucket: Optional[str] = Field(default=None, alias="S3_BUCKET")
    s3_key: Optional[str] = Field(default=None, alias="S3_KEY")
    sqs_queue_url: Optional[str] = Field(default=None, alias="SQS_QUEUE_URL")
    sqs_wait_seconds: int = Field(default=20, alias="SQS_WAIT_SECONDS", ge=0, le=20)
    sqs_max_messages: int = Field(default=5, alias="SQS_MAX_MESSAGES", ge=1, le=10)

    database_url: Optional[str] = Field(default=None, alias="DATABASE_URL")
    db_host: Optional[str] = Field(default=None, alias="DB_HOST")
    db_port: int = Field(default=5432, alias="DB_PORT")
    db_name: Optional[str] = Field(default=None, alias="DB_NAME")
    db_user: Optional[str] = Field(default=None, alias="DB_USER")
    db_password: Optional[str] = Field(default=None, alias="DB_PASSWORD")
    db_sslmode: str = Field(default="require", alias="DB_SSLMODE")
    openai_api_key: str = Field(alias="OPENAI_API_KEY")
    embedding_model: str = Field(default="text-embedding-3-small", alias="EMBEDDING_MODEL")
    embedding_batch_size: int = Field(default=128, alias="EMBEDDING_BATCH_SIZE", ge=1, le=512)

    chunk_size: int = Field(default=1000, alias="CHUNK_SIZE", ge=100)
    chunk_overlap: int = Field(default=200, alias="CHUNK_OVERLAP", ge=0)

    @property
    def pg_connection_string(self) -> str:
        """Return a PostgreSQL connection string from DATABASE_URL or Aurora fields."""
        if self.database_url:
            return self.database_url

        missing = [
            name
            for name, value in {
                "DB_HOST": self.db_host,
                "DB_NAME": self.db_name,
                "DB_USER": self.db_user,
                "DB_PASSWORD": self.db_password,
            }.items()
            if not value
        ]
        if missing:
            missing_list = ", ".join(missing)
            raise ValueError(
                "Set DATABASE_URL or provide all Aurora fields. "
                f"Missing: {missing_list}."
            )

        user = quote_plus(self.db_user or "")
        password = quote_plus(self.db_password or "")
        return (
            f"postgresql+psycopg://{user}:{password}@{self.db_host}:{self.db_port}"
            f"/{self.db_name}?sslmode={self.db_sslmode}"
        )

    @property
    def psycopg_connection_string(self) -> str:
        """Return a psycopg-compatible PostgreSQL connection string."""
        connection_string = self.pg_connection_string
        if connection_string.startswith("postgresql+psycopg://"):
            return connection_string.replace("postgresql+psycopg://", "postgresql://", 1)
        return connection_string


@lru_cache
def get_settings() -> Settings:
    return Settings()

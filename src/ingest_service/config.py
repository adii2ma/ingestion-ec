from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration loaded from environment variables or .env."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    aws_region: str = Field(default="us-east-1", alias="AWS_REGION")
    s3_bucket: str | None = Field(default=None, alias="S3_BUCKET")
    s3_key: str | None = Field(default=None, alias="S3_KEY")

    database_url: str = Field(alias="DATABASE_URL")
    pgvector_collection: str = Field(default="documents", alias="PGVECTOR_COLLECTION")

    openai_api_key: str = Field(alias="OPENAI_API_KEY")
    embedding_model: str = Field(default="text-embedding-3-small", alias="EMBEDDING_MODEL")

    chunk_size: int = Field(default=1000, alias="CHUNK_SIZE", ge=100)
    chunk_overlap: int = Field(default=200, alias="CHUNK_OVERLAP", ge=0)


@lru_cache
def get_settings() -> Settings:
    return Settings()


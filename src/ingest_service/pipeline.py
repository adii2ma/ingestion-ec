import logging
from dataclasses import dataclass

from ingest_service.chunking import chunk_documents
from ingest_service.config import Settings
from ingest_service.document_loader import load_document_from_s3
from ingest_service.embeddings import build_embeddings_model
from ingest_service.repository import store_ingested_document
from ingest_service.s3_path import metadata_from_s3_key

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class IngestionResult:
    source: str
    parsed_documents: int
    chunks_stored: int
    ids: list[str]


def ingest_s3_document(settings: Settings, *, bucket: str, key: str) -> IngestionResult:
    """Run the full S3 -> parse -> chunk -> embed -> pgvector ingestion flow."""
    source = f"s3://{bucket}/{key}"
    logger.info("ingest.start source=%s", source)
    document_metadata = metadata_from_s3_key(key)
    documents = load_document_from_s3(bucket, key, region_name=settings.aws_region)
    logger.info("ingest.parsed source=%s documents=%s", source, len(documents))
    chunks = chunk_documents(
        documents,
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
    )
    logger.info("ingest.chunked source=%s chunks=%s", source, len(chunks))
    embeddings = build_embeddings_model(
        api_key=settings.openai_api_key,
        model=settings.embedding_model,
    )
    chunk_embeddings = (
        embeddings.embed_documents([chunk.page_content for chunk in chunks]) if chunks else []
    )
    logger.info("ingest.embedded source=%s embeddings=%s", source, len(chunk_embeddings))
    stored_document = store_ingested_document(
        connection_string=settings.psycopg_connection_string,
        bucket=bucket,
        key=key,
        document_metadata=document_metadata,
        chunks=chunks,
        embeddings=chunk_embeddings,
    )
    logger.info("ingest.stored source=%s chunks=%s", source, len(stored_document.chunk_ids))

    return IngestionResult(
        source=source,
        parsed_documents=len(documents),
        chunks_stored=len(chunks),
        ids=[str(chunk_id) for chunk_id in stored_document.chunk_ids],
    )

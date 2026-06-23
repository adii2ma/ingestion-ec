from dataclasses import dataclass

from ingest_service.chunking import chunk_documents
from ingest_service.config import Settings
from ingest_service.document_loader import load_document_from_s3
from ingest_service.embeddings import build_embeddings_model
from ingest_service.vector_store import build_vector_store, store_chunks


@dataclass(frozen=True)
class IngestionResult:
    source: str
    parsed_documents: int
    chunks_stored: int
    ids: list[str]


def ingest_s3_document(settings: Settings, *, bucket: str, key: str) -> IngestionResult:
    """Run the full S3 -> parse -> chunk -> embed -> pgvector ingestion flow."""
    documents = load_document_from_s3(bucket, key, region_name=settings.aws_region)
    chunks = chunk_documents(
        documents,
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
    )
    embeddings = build_embeddings_model(
        api_key=settings.openai_api_key,
        model=settings.embedding_model,
    )
    vector_store = build_vector_store(
        connection_string=settings.database_url,
        collection_name=settings.pgvector_collection,
        embeddings=embeddings,
    )
    ids = store_chunks(vector_store, chunks)

    return IngestionResult(
        source=f"s3://{bucket}/{key}",
        parsed_documents=len(documents),
        chunks_stored=len(chunks),
        ids=ids,
    )


from hashlib import sha256

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_postgres import PGVector


def build_vector_store(
    *,
    connection_string: str,
    collection_name: str,
    embeddings: Embeddings,
) -> PGVector:
    """Create a LangChain PGVector store backed by Aurora/PostgreSQL."""
    return PGVector(
        embeddings=embeddings,
        collection_name=collection_name,
        connection=connection_string,
        use_jsonb=True,
    )


def stable_chunk_id(document: Document) -> str:
    """Build deterministic IDs so re-ingesting the same object updates chunks."""
    source = document.metadata.get("source", "unknown-source")
    chunk_index = document.metadata.get("chunk_index", "unknown-chunk")
    text_hash = sha256(document.page_content.encode("utf-8")).hexdigest()[:16]
    return f"{source}#chunk={chunk_index}#sha256={text_hash}"


def store_chunks(vector_store: PGVector, chunks: list[Document]) -> list[str]:
    ids = [stable_chunk_id(chunk) for chunk in chunks]
    vector_store.add_documents(chunks, ids=ids)
    return ids


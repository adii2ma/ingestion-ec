import uuid
from dataclasses import dataclass
from typing import Sequence

import psycopg
from langchain_core.documents import Document
from psycopg.types.json import Jsonb

from ingest_service.s3_path import S3DocumentMetadata

INGEST_NAMESPACE = uuid.UUID("c62f8b1d-466c-4614-a608-d9df12b8d6c0")


@dataclass(frozen=True)
class StoredDocument:
    course_id: uuid.UUID
    document_id: uuid.UUID
    chunk_ids: list[uuid.UUID]


def deterministic_uuid(value: str) -> uuid.UUID:
    return uuid.uuid5(INGEST_NAMESPACE, value)


def store_ingested_document(
    *,
    connection_string: str,
    bucket: str,
    key: str,
    document_metadata: S3DocumentMetadata,
    chunks: Sequence[Document],
    embeddings: Sequence[Sequence[float]],
) -> StoredDocument:
    """Persist one parsed/chunked/embedded document into the custom pgvector schema."""
    if len(chunks) != len(embeddings):
        raise ValueError("chunks and embeddings must have the same length.")

    course_id = deterministic_uuid(
        "course:"
        f"{document_metadata.semester_id}/"
        f"{document_metadata.course_name}/"
        f"{document_metadata.professor or ''}"
    )
    document_id = deterministic_uuid(f"document:s3://{bucket}/{key}")
    chunk_ids = [
        deterministic_uuid(f"chunk:{document_id}:{chunk.metadata.get('chunk_index', index)}")
        for index, chunk in enumerate(chunks)
    ]

    with psycopg.connect(connection_string) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO courses (id, name, semester_id, professor)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE
                SET name = EXCLUDED.name,
                    semester_id = EXCLUDED.semester_id,
                    professor = EXCLUDED.professor
                """,
                (
                    course_id,
                    document_metadata.course_name,
                    document_metadata.semester_id,
                    document_metadata.professor,
                ),
            )

            cursor.execute("DELETE FROM chunks WHERE document_id = %s", (document_id,))

            cursor.execute(
                """
                INSERT INTO documents (id, course_id, filename, s3_key, uploaded_at)
                VALUES (%s, %s, %s, %s, NOW())
                ON CONFLICT (id) DO UPDATE
                SET course_id = EXCLUDED.course_id,
                    filename = EXCLUDED.filename,
                    s3_key = EXCLUDED.s3_key,
                    uploaded_at = NOW()
                """,
                (document_id, course_id, document_metadata.filename, key),
            )

            for chunk_id, chunk, embedding in zip(chunk_ids, chunks, embeddings):
                chunk_index = int(chunk.metadata.get("chunk_index", 0))
                metadata = {
                    **chunk.metadata,
                    "bucket": bucket,
                    "s3_key": key,
                    "source": f"s3://{bucket}/{key}",
                    "filename": document_metadata.filename,
                    "course_id": str(course_id),
                    "document_id": str(document_id),
                    "course_name": document_metadata.course_name,
                    "semester_id": document_metadata.semester_id,
                    "professor": document_metadata.professor,
                    "chunk_index": chunk_index,
                }

                cursor.execute(
                    """
                    INSERT INTO chunks (
                        id,
                        document_id,
                        course_id,
                        semester_id,
                        professor,
                        chunk_index,
                        content,
                        embedding,
                        metadata,
                        created_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s::vector, %s, NOW())
                    ON CONFLICT (id) DO UPDATE
                    SET document_id = EXCLUDED.document_id,
                        course_id = EXCLUDED.course_id,
                        semester_id = EXCLUDED.semester_id,
                        professor = EXCLUDED.professor,
                        chunk_index = EXCLUDED.chunk_index,
                        content = EXCLUDED.content,
                        embedding = EXCLUDED.embedding,
                        metadata = EXCLUDED.metadata,
                        created_at = NOW()
                    """,
                    (
                        chunk_id,
                        document_id,
                        course_id,
                        document_metadata.semester_id,
                        document_metadata.professor,
                        chunk_index,
                        chunk.page_content,
                        _vector_literal(embedding),
                        Jsonb(metadata),
                    ),
                )

    return StoredDocument(course_id=course_id, document_id=document_id, chunk_ids=chunk_ids)


def _vector_literal(embedding: Sequence[float]) -> str:
    return "[" + ",".join(str(value) for value in embedding) + "]"

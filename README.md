# Ingest Service

Base Python ingestion service for this flow:

```text
S3 document -> LangChain loader/parser -> chunks -> embeddings -> Aurora PostgreSQL pgvector
```

The service ingests one S3 object at a time, parses it into LangChain `Document` objects,
splits those documents into retrievable chunks, creates embeddings for each chunk, and stores
the chunks plus metadata in a pgvector collection.

## What LangChain Is Doing Here

LangChain gives us common interfaces for each step in the ingestion pipeline.

1. **Parsing/loading**
   `S3FileLoader` downloads an object from S3 and parses the file content into LangChain
   `Document` objects. A `Document` has two important fields:
   `page_content`, which is the text, and `metadata`, which tracks things like source path,
   S3 bucket, S3 key, page number, and chunk index.

2. **Chunking**
   Large documents are too big to embed and retrieve as one block. `RecursiveCharacterTextSplitter`
   breaks text into smaller pieces. It first tries to split on larger natural boundaries like
   paragraphs, then lines, then spaces, then characters. `CHUNK_OVERLAP` keeps some text repeated
   across adjacent chunks so useful context is not lost at chunk boundaries.

3. **Embedding**
   `OpenAIEmbeddings` sends each chunk's text to an embedding model. The model returns a vector:
   a list of numbers that captures semantic meaning. Similar chunks have nearby vectors.

4. **Storage in pgvector**
   `PGVector` stores chunk text, metadata, and embedding vectors in PostgreSQL using the `vector`
   extension. Aurora PostgreSQL can be used when the `vector` extension is enabled on the database.
   Later, retrieval uses vector similarity search to find chunks relevant to a question.

## Files

`pyproject.toml`
: Python package metadata and dependencies. The key LangChain packages are split by integration:
`langchain-community` for the S3 loader, `langchain-text-splitters` for chunking,
`langchain-openai` for embeddings, and `langchain-postgres` for PGVector.

`.env.example`
: Example runtime configuration. Copy it to `.env` locally and fill in S3, Aurora/Postgres, and
OpenAI settings.

`docker-compose.yml`
: Local development PostgreSQL with pgvector. This is for testing on your machine. For production,
point `DATABASE_URL` at Aurora PostgreSQL.

`scripts/init_pgvector.sql`
: Enables the PostgreSQL `vector` extension in the local database container.

`src/ingest_service/config.py`
: Reads settings from environment variables or `.env` using `pydantic-settings`.

`src/ingest_service/document_loader.py`
: Contains the S3 parsing step. `load_document_from_s3()` returns LangChain `Document` objects and
adds consistent source metadata.

`src/ingest_service/chunking.py`
: Contains the chunking step. `chunk_documents()` uses `RecursiveCharacterTextSplitter` and adds a
`chunk_index` to metadata.

`src/ingest_service/embeddings.py`
: Builds the embedding model. Right now it uses OpenAI's `text-embedding-3-small` by default.

`src/ingest_service/vector_store.py`
: Creates the LangChain `PGVector` store and writes chunks. IDs are deterministic, so re-ingesting
the same object updates the same chunk IDs instead of creating random IDs every time.

`src/ingest_service/pipeline.py`
: Orchestrates the full ingestion pipeline.

`src/ingest_service/cli.py`
: CLI entrypoint. Run this to ingest a document.

## Setup

Create and activate a virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate
```

Install the package:

```bash
pip install -e .
```

Create local config:

```bash
cp .env.example .env
```

For local database testing:

```bash
docker compose up -d
```

For Aurora, make sure pgvector is enabled in your database:

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

Then set `DATABASE_URL` in `.env` to your Aurora PostgreSQL connection string:

```text
postgresql+psycopg://USER:PASSWORD@AURORA-ENDPOINT:5432/DB_NAME
```

## Run

Using `.env` values:

```bash
ingest-service ingest
```

Or pass the S3 object explicitly:

```bash
ingest-service ingest --bucket your-bucket-name --key documents/example.pdf
```

You can also run the package directly:

```bash
python -m ingest_service ingest --bucket your-bucket-name --key documents/example.pdf
```

The command prints JSON with the S3 source, number of parsed documents, number of chunks stored,
and the chunk IDs written to pgvector.

## Tuning Chunking

Start with:

```text
CHUNK_SIZE=1000
CHUNK_OVERLAP=200
```

Smaller chunks improve precise retrieval but can lose context. Larger chunks preserve context but
can make retrieval less focused and increase embedding cost. Tune this by testing real queries
against your own documents.

## Next Steps

Good next additions are:

1. SQS or EventBridge trigger for automatic ingestion when S3 objects are uploaded.
2. Batch ingestion for S3 prefixes.
3. A retrieval API that searches pgvector by query text.
4. Ingestion status tables for retries, failures, and source version tracking.
5. Authentication and network hardening for Aurora access.


# Ingest Service

Base Python ingestion service for this flow:

```text
S3 ObjectCreated event -> SQS -> S3 document -> LangChain parser -> chunks -> embeddings -> Aurora PostgreSQL pgvector
```

The service can ingest one explicit S3 object, or poll SQS for S3 `ObjectCreated` events.
For the SQS path, the S3 event message provides the bucket and object key, so you do not need to
hardcode `S3_KEY` in `.env`.

## What LangChain Is Doing Here

LangChain gives us common interfaces for each step in the ingestion pipeline.

1. **Parsing/loading**
   The service downloads an object from S3 with `boto3`, then parses the file with a LangChain
   loader such as `PyPDFLoader`, `Docx2txtLoader`, or `TextLoader`. The output is LangChain
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
   The service writes directly into your `courses`, `documents`, and `chunks` tables using
   `psycopg`. The `chunks.embedding` column is a PostgreSQL `vector(1536)`, so later retrieval can
   use cosine similarity search against your own schema.

## S3 Folder Metadata

The ingestion code derives database metadata from the S3 object key.

```text
semester_id/course_name/professor/filename.pdf
semester_id/course_name/filename.pdf
```

Examples:

```text
semester-5/Operating Systems/Dr Sharma/scheduler.pdf
semester-5/Operating Systems/processes.pdf
```

For the first key, the stored metadata is:

```text
semester_id = semester-5
course_name = Operating Systems
professor = Dr Sharma
filename = scheduler.pdf
```

For the second key, `professor` is stored as `NULL` because there is no professor folder.

## Files

`pyproject.toml`
: Python package metadata and dependencies. The key LangChain packages are split by integration:
`langchain-community` for the S3 loader, `langchain-text-splitters` for chunking,
and `langchain-openai` for embeddings. PDF parsing uses `pypdf`, DOCX parsing uses `docx2txt`,
PPTX parsing uses `python-pptx`, and database writes use `psycopg`.

`.env.example`
: Example runtime configuration. Copy it to `.env` locally and fill in S3, Aurora/Postgres, and
OpenAI settings.

`docker-compose.yml`
: Local development PostgreSQL with pgvector. This is for testing on your machine. For production,
point `DATABASE_URL` at Aurora PostgreSQL.

`scripts/init_pgvector.sql`
: Enables the PostgreSQL `vector` extension and creates the same local `courses`, `documents`,
`chunks`, and indexes you created in Aurora.

`src/ingest_service/config.py`
: Reads settings from environment variables or `.env` using `pydantic-settings`.

`src/ingest_service/document_loader.py`
: Contains the S3 parsing step. It downloads the S3 object, chooses a lightweight parser by file
extension, returns LangChain `Document` objects, and adds consistent source metadata.
Supported types are `.pdf`, `.docx`, `.pptx`, `.txt`, `.md`, and `.csv`. Legacy `.ppt` is supported
with a best-effort text extraction fallback. Legacy `.doc` is also supported with best-effort text
extraction.

`src/ingest_service/chunking.py`
: Contains the chunking step. `chunk_documents()` uses `RecursiveCharacterTextSplitter` and adds a
`chunk_index` to metadata.

`src/ingest_service/embeddings.py`
: Builds the embedding model. Right now it uses OpenAI's `text-embedding-3-small` by default.

`src/ingest_service/s3_path.py`
: Parses the S3 key into `semester_id`, `course_name`, optional `professor`, and `filename`.

`src/ingest_service/repository.py`
: Writes to your custom tables. It upserts `courses`, upserts `documents`, deletes old chunks for
the document, and inserts the new chunk rows with `vector(1536)` embeddings and JSONB metadata.

`src/ingest_service/s3_events.py`
: Parses SQS message bodies that contain S3 object-created notifications and extracts the real
`bucket` and `key` for each uploaded object.

`src/ingest_service/sqs_worker.py`
: Polls SQS, ingests each S3 object referenced by the message, and deletes the message after
successful ingestion.

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

On EC2, attach an IAM role to the instance. The role should allow at least:

```text
s3:GetObject on the source bucket/prefix
sqs:ReceiveMessage, sqs:DeleteMessage, sqs:GetQueueAttributes on the queue
```

With that setup, you do not put AWS access keys in `.env`. Boto3 discovers credentials from the
EC2 instance role automatically.

For local database testing:

```bash
docker compose up -d
```

For Aurora, make sure pgvector is enabled in your database:

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

For Aurora, either set one full `DATABASE_URL`:

```text
postgresql+psycopg://USER:PASSWORD@AURORA-ENDPOINT:5432/DB_NAME
```

Or use the split fields in `.env`:

```text
DB_HOST=your-aurora-cluster.cluster-xxxxxxxxxxxx.us-east-1.rds.amazonaws.com
DB_PORT=5432
DB_NAME=ingest
DB_USER=postgres
DB_PASSWORD=your-password
DB_SSLMODE=require
```

The service builds the PostgreSQL connection string from those fields when `DATABASE_URL` is not set.

## Run

Poll SQS once:

```bash
ingest-service poll-sqs
```

Keep polling SQS:

```bash
ingest-service poll-sqs --forever
```

Manually ingest one object:

```bash
ingest-service ingest --bucket your-bucket-name --key "semester-5/Operating Systems/processes.pdf"
```

You can also set `S3_BUCKET` and `S3_KEY` in `.env` for local/manual testing, then run:

```bash
ingest-service ingest
```

You can also run the package directly:

```bash
python -m ingest_service poll-sqs --forever
```

The command prints JSON with the S3 source, number of parsed documents, number of chunks stored,
and the chunk IDs written to pgvector.

## Embedding Model

You usually do not need to change the embedding model. Leave this default:

```text
EMBEDDING_MODEL=text-embedding-3-small
```

Then put only your OpenAI API key in `.env`:

```text
OPENAI_API_KEY=sk-your-key
```

Change `EMBEDDING_MODEL` only when you have a specific reason, such as wanting larger vectors or a
different cost/quality tradeoff.

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

1. Batch ingestion for existing S3 prefixes.
2. A retrieval API that searches pgvector by query text.
3. Ingestion status tables for retries, failures, and source version tracking.
4. Dead-letter queue handling for failed documents.
5. Authentication and network hardening for Aurora access.

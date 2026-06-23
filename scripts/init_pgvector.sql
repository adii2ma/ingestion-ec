CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS courses (
    id UUID PRIMARY KEY,
    name TEXT NOT NULL,
    semester_id TEXT NOT NULL,
    professor TEXT
);

CREATE TABLE IF NOT EXISTS documents (
    id UUID PRIMARY KEY,
    course_id UUID REFERENCES courses(id),
    filename TEXT NOT NULL,
    s3_key TEXT NOT NULL,
    uploaded_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS chunks (
    id UUID PRIMARY KEY,
    document_id UUID REFERENCES documents(id),
    course_id UUID REFERENCES courses(id),
    semester_id TEXT,
    professor TEXT,
    chunk_index INTEGER,
    content TEXT NOT NULL,
    embedding VECTOR(1536),
    metadata JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS chunks_embedding_idx
ON chunks
USING hnsw (embedding vector_cosine_ops);

CREATE INDEX IF NOT EXISTS idx_chunks_course
ON chunks(course_id);

CREATE INDEX IF NOT EXISTS idx_chunks_semester
ON chunks(semester_id);

CREATE INDEX IF NOT EXISTS idx_documents_course
ON documents(course_id);

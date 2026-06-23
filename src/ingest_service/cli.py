import json

import click
from dotenv import load_dotenv

from ingest_service.config import get_settings
from ingest_service.pipeline import ingest_s3_document


@click.group()
def main() -> None:
    """Ingest documents from S3 into Aurora PostgreSQL pgvector."""
    load_dotenv()


@main.command()
@click.option("--bucket", help="S3 bucket containing the document.")
@click.option("--key", help="S3 object key to ingest.")
def ingest(bucket: str | None, key: str | None) -> None:
    """Ingest one S3 object."""
    settings = get_settings()
    bucket = bucket or settings.s3_bucket
    key = key or settings.s3_key

    if not bucket or not key:
        raise click.ClickException("Provide --bucket/--key or set S3_BUCKET/S3_KEY in .env.")

    result = ingest_s3_document(settings, bucket=bucket, key=key)
    click.echo(
        json.dumps(
            {
                "source": result.source,
                "parsed_documents": result.parsed_documents,
                "chunks_stored": result.chunks_stored,
                "ids": result.ids,
            },
            indent=2,
        )
    )


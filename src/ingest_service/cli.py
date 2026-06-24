import json
import logging
from typing import Optional

import click
from dotenv import load_dotenv

from ingest_service.config import get_settings
from ingest_service.pipeline import ingest_s3_document
from ingest_service.sqs_worker import poll_sqs_once


@click.group()
def main() -> None:
    """Ingest documents from S3 into Aurora PostgreSQL pgvector."""
    load_dotenv()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


@main.command()
@click.option("--bucket", help="S3 bucket containing the document.")
@click.option("--key", help="S3 object key to ingest.")
def ingest(bucket: Optional[str], key: Optional[str]) -> None:
    """Ingest one explicit S3 object."""
    settings = get_settings()
    bucket = bucket or settings.s3_bucket
    key = key or settings.s3_key

    if not bucket or not key:
        raise click.ClickException(
            "Provide --bucket/--key, set S3_BUCKET/S3_KEY, or use poll-sqs for S3 events."
        )

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


@main.command("poll-sqs")
@click.option("--forever", is_flag=True, help="Keep polling SQS until the process is stopped.")
def poll_sqs(forever: bool) -> None:
    """Poll SQS for S3 object-created events and ingest the new objects."""
    settings = get_settings()

    while True:
        results = poll_sqs_once(settings)
        for result in results:
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

        if not forever:
            break

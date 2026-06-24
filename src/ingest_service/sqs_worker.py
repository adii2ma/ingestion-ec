import logging
from typing import Optional

import boto3
from botocore.client import BaseClient

from ingest_service.config import Settings
from ingest_service.pipeline import IngestionResult, ingest_s3_document
from ingest_service.s3_events import parse_s3_object_events

logger = logging.getLogger(__name__)


def build_sqs_client(*, region_name: str) -> BaseClient:
    """Create an SQS client using the EC2 instance role or local AWS profile."""
    return boto3.client("sqs", region_name=region_name)


def poll_sqs_once(
    settings: Settings,
    *,
    sqs_client: Optional[BaseClient] = None,
) -> list[IngestionResult]:
    """Poll SQS once, ingest every S3 object-created event, then delete successful messages."""
    if not settings.sqs_queue_url:
        raise ValueError("Set SQS_QUEUE_URL before running the SQS worker.")

    client = sqs_client or build_sqs_client(region_name=settings.aws_region)
    response = client.receive_message(
        QueueUrl=settings.sqs_queue_url,
        MaxNumberOfMessages=settings.sqs_max_messages,
        WaitTimeSeconds=settings.sqs_wait_seconds,
    )

    results: list[IngestionResult] = []
    for message in response.get("Messages", []):
        receipt_handle = message["ReceiptHandle"]
        events = parse_s3_object_events(message["Body"])

        if not events:
            logger.info("Deleting SQS message with no supported S3 object-created records.")
            client.delete_message(QueueUrl=settings.sqs_queue_url, ReceiptHandle=receipt_handle)
            continue

        message_succeeded = True
        for event in events:
            source = f"s3://{event.bucket}/{event.key}"
            logger.info("sqs.event.start source=%s event=%s", source, event.event_name)
            try:
                result = ingest_s3_document(settings, bucket=event.bucket, key=event.key)
            except Exception:
                message_succeeded = False
                logger.exception("sqs.event.failed source=%s", source)
                continue

            results.append(result)
            logger.info(
                "sqs.event.done source=%s parsed_documents=%s chunks_stored=%s",
                source,
                result.parsed_documents,
                result.chunks_stored,
            )

        if message_succeeded:
            client.delete_message(QueueUrl=settings.sqs_queue_url, ReceiptHandle=receipt_handle)
            logger.info("sqs.message.deleted events=%s", len(events))
        else:
            logger.warning("sqs.message.kept_for_retry events=%s", len(events))

    return results

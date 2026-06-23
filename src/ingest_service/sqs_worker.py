import logging

import boto3
from botocore.client import BaseClient

from ingest_service.config import Settings
from ingest_service.pipeline import IngestionResult, ingest_s3_document
from ingest_service.s3_events import parse_s3_object_events

logger = logging.getLogger(__name__)


def build_sqs_client(*, region_name: str) -> BaseClient:
    """Create an SQS client using the EC2 instance role or local AWS profile."""
    return boto3.client("sqs", region_name=region_name)


def poll_sqs_once(settings: Settings, *, sqs_client: BaseClient | None = None) -> list[IngestionResult]:
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

        for event in events:
            logger.info("Ingesting s3://%s/%s from %s", event.bucket, event.key, event.event_name)
            results.append(ingest_s3_document(settings, bucket=event.bucket, key=event.key))

        client.delete_message(QueueUrl=settings.sqs_queue_url, ReceiptHandle=receipt_handle)

    return results


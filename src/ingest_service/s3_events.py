import json
from dataclasses import dataclass
from urllib.parse import unquote_plus


@dataclass(frozen=True)
class S3ObjectEvent:
    bucket: str
    key: str
    event_name: str


def parse_s3_object_events(message_body: str) -> list[S3ObjectEvent]:
    """Extract S3 object-created events from an SQS message body."""
    payload = json.loads(message_body)

    if "Message" in payload and isinstance(payload["Message"], str):
        payload = json.loads(payload["Message"])

    if "detail" in payload:
        return _parse_eventbridge_payload(payload)

    return _parse_s3_notification_payload(payload)


def _parse_s3_notification_payload(payload: dict) -> list[S3ObjectEvent]:
    events: list[S3ObjectEvent] = []
    for record in payload.get("Records", []):
        if record.get("eventSource") != "aws:s3":
            continue

        event_name = record.get("eventName", "")
        if not event_name.startswith("ObjectCreated:"):
            continue

        bucket = record["s3"]["bucket"]["name"]
        key = unquote_plus(record["s3"]["object"]["key"])
        events.append(S3ObjectEvent(bucket=bucket, key=key, event_name=event_name))

    return events


def _parse_eventbridge_payload(payload: dict) -> list[S3ObjectEvent]:
    detail = payload.get("detail", {})
    if payload.get("source") != "aws.s3" or payload.get("detail-type") != "Object Created":
        return []

    bucket = detail.get("bucket", {}).get("name")
    key = detail.get("object", {}).get("key")
    event_name = detail.get("reason", "ObjectCreated")

    if not bucket or not key:
        return []

    return [S3ObjectEvent(bucket=bucket, key=unquote_plus(key), event_name=event_name)]

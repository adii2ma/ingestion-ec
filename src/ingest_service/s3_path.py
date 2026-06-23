from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Optional
from urllib.parse import unquote_plus


@dataclass(frozen=True)
class S3DocumentMetadata:
    semester_id: str
    course_name: str
    professor: Optional[str]
    filename: str


def metadata_from_s3_key(key: str) -> S3DocumentMetadata:
    """Derive course metadata from an S3 key.

    Expected layouts:
    - semester/course/professor/file.pdf
    - semester/course/file.pdf
    """
    decoded_key = unquote_plus(key)
    parts = [part for part in PurePosixPath(decoded_key).parts if part not in {"", "/"}]

    if len(parts) < 3:
        raise ValueError(
            "S3 key must look like 'semester/course/file.pdf' or "
            f"'semester/course/professor/file.pdf'. Got: {key}"
        )

    semester_id = parts[0]
    course_name = parts[1]
    professor = parts[2] if len(parts) >= 4 else None
    filename = parts[-1]

    return S3DocumentMetadata(
        semester_id=semester_id,
        course_name=course_name,
        professor=professor,
        filename=filename,
    )

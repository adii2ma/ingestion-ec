from pathlib import Path
from tempfile import NamedTemporaryFile

import boto3
from langchain_community.document_loaders import Docx2txtLoader, PyPDFLoader, TextLoader
from langchain_core.documents import Document


def load_document_from_s3(bucket: str, key: str, *, region_name: str) -> list[Document]:
    """Parse one S3 object into LangChain Document objects.

    The object is downloaded through boto3, then parsed by a file-type-specific
    LangChain loader. This avoids the heavy OCR/layout dependency stack used by
    unstructured for normal text PDFs.
    """
    suffix = Path(key).suffix.lower()
    s3_client = boto3.client("s3", region_name=region_name)

    with NamedTemporaryFile(suffix=suffix, delete=False) as temp_file:
        temp_path = Path(temp_file.name)
        s3_client.download_fileobj(bucket, key, temp_file)

    try:
        loader = _loader_for_path(temp_path, suffix)
        documents = loader.load()
    finally:
        temp_path.unlink(missing_ok=True)

    for document in documents:
        document.metadata.update(
            {
                "s3_bucket": bucket,
                "s3_key": key,
                "source": f"s3://{bucket}/{key}",
            }
        )

    return documents


def _loader_for_path(path: Path, suffix: str):
    if suffix == ".pdf":
        return PyPDFLoader(str(path))
    if suffix == ".docx":
        return Docx2txtLoader(str(path))
    if suffix in {".txt", ".md", ".csv"}:
        return TextLoader(str(path), encoding="utf-8")

    raise ValueError(f"Unsupported document type '{suffix}' for {path.name}.")

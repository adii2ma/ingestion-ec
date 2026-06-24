from pathlib import Path
from subprocess import run
from tempfile import NamedTemporaryFile, TemporaryDirectory

import boto3
from langchain_community.document_loaders import Docx2txtLoader, PyPDFLoader, TextLoader
from langchain_core.documents import Document
from pptx import Presentation


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
    if suffix == ".pptx":
        return PowerPointLoader(path)
    if suffix == ".ppt":
        return LegacyPowerPointLoader(path)
    if suffix in {".txt", ".md", ".csv"}:
        return TextLoader(str(path), encoding="utf-8")

    raise ValueError(f"Unsupported document type '{suffix}' for {path.name}.")


class PowerPointLoader:
    """Extract text from a PPTX file, one LangChain document per slide."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> list[Document]:
        presentation = Presentation(str(self.path))
        documents: list[Document] = []

        for slide_index, slide in enumerate(presentation.slides, start=1):
            text_parts: list[str] = []
            for shape in slide.shapes:
                if hasattr(shape, "text") and shape.text:
                    text_parts.append(shape.text)

                if getattr(shape, "has_table", False):
                    for row in shape.table.rows:
                        cells = [cell.text for cell in row.cells if cell.text]
                        if cells:
                            text_parts.append(" | ".join(cells))

            content = "\n".join(part.strip() for part in text_parts if part.strip())
            if content:
                documents.append(
                    Document(
                        page_content=content,
                        metadata={"slide": slide_index, "total_slides": len(presentation.slides)},
                    )
                )

        return documents


class LegacyPowerPointLoader:
    """Convert legacy PPT to PPTX with LibreOffice, then extract text."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> list[Document]:
        with TemporaryDirectory() as temp_dir:
            result = run(
                [
                    "soffice",
                    "--headless",
                    "--convert-to",
                    "pptx",
                    "--outdir",
                    temp_dir,
                    str(self.path),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            converted_path = Path(temp_dir) / f"{self.path.stem}.pptx"
            if result.returncode != 0 or not converted_path.exists():
                raise RuntimeError(
                    "Unable to parse legacy .ppt file. Install LibreOffice on the worker "
                    "or upload .pptx files. "
                    f"LibreOffice output: {result.stderr or result.stdout}"
                )

            return PowerPointLoader(converted_path).load()

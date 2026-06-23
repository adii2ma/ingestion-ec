from langchain_community.document_loaders import S3FileLoader
from langchain_core.documents import Document


def load_document_from_s3(bucket: str, key: str, *, region_name: str) -> list[Document]:
    """Parse one S3 object into LangChain Document objects.

    S3FileLoader downloads the object through boto3, then delegates file parsing to
    LangChain/unstructured loaders based on the file type.
    """
    loader = S3FileLoader(bucket, key, region_name=region_name)
    documents = loader.load()

    for document in documents:
        document.metadata.update(
            {
                "s3_bucket": bucket,
                "s3_key": key,
                "source": f"s3://{bucket}/{key}",
            }
        )

    return documents

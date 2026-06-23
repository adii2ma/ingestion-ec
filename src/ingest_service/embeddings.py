from langchain_openai import OpenAIEmbeddings


def build_embeddings_model(*, api_key: str, model: str) -> OpenAIEmbeddings:
    """Create the embedding model LangChain will call for each chunk."""
    return OpenAIEmbeddings(api_key=api_key, model=model)


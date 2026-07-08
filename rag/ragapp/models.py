"""Factories for the Cohere models and the Pinecone-backed index."""
from __future__ import annotations

import time

from llama_index.core import VectorStoreIndex
from llama_index.embeddings.cohere import CohereEmbedding
from llama_index.llms.cohere import Cohere
from llama_index.vector_stores.pinecone import PineconeVectorStore
from pinecone import Pinecone, ServerlessSpec

from . import config


def get_embed_model(input_type: str = "search_document") -> CohereEmbedding:
    return CohereEmbedding(
        api_key=config.COHERE_API_KEY,
        model_name=config.EMBED_MODEL,
        input_type=input_type,
    )


def get_llm(temperature: float = 0.2) -> Cohere:
    return Cohere(
        api_key=config.COHERE_API_KEY,
        model=config.LLM_MODEL,
        temperature=temperature,
    )


def get_pinecone_index(create_if_missing: bool = False):
    pc = Pinecone(api_key=config.PINECONE_API_KEY)
    if create_if_missing and not pc.has_index(config.PINECONE_INDEX_NAME):
        pc.create_index(
            name=config.PINECONE_INDEX_NAME,
            dimension=config.EMBED_DIM,
            metric="cosine",
            spec=ServerlessSpec(cloud=config.PINECONE_CLOUD, region=config.PINECONE_REGION),
        )
        while not pc.describe_index(config.PINECONE_INDEX_NAME).status["ready"]:
            time.sleep(1)
    return pc.Index(config.PINECONE_INDEX_NAME)


def get_vector_store(create_if_missing: bool = False) -> PineconeVectorStore:
    return PineconeVectorStore(
        pinecone_index=get_pinecone_index(create_if_missing),
        namespace=config.PINECONE_NAMESPACE,
    )


def clear_namespace() -> None:
    """Wipe the namespace so re-ingestion doesn't leave stale vectors behind."""
    try:
        get_pinecone_index().delete(delete_all=True, namespace=config.PINECONE_NAMESPACE)
    except Exception:
        pass  # namespace may not exist yet — nothing to clear


def get_query_index() -> VectorStoreIndex:
    """Index handle for query time (embeddings use the search_query input type)."""
    return VectorStoreIndex.from_vector_store(
        vector_store=get_vector_store(),
        embed_model=get_embed_model(input_type="search_query"),
    )

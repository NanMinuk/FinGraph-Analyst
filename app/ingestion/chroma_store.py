from pathlib import Path
from typing import List

from dotenv import load_dotenv
from langchain_core.documents import Document
from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings
from langchain_classic.embeddings import CacheBackedEmbeddings
from langchain_classic.storage import LocalFileStore

load_dotenv()

CHROMA_PATH = Path("data/chroma_langchain")
EMBED_CACHE_PATH = Path("data/embedding_cache")
RAW_COLLECTION_NAME = "raw_news"
CHUNK_COLLECTION_NAME = "news_chunks"


def get_embeddings():
    underlying_embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
    EMBED_CACHE_PATH.mkdir(parents=True, exist_ok=True)
    store = LocalFileStore(str(EMBED_CACHE_PATH))
    return CacheBackedEmbeddings.from_bytes_store(
        underlying_embeddings=underlying_embeddings,
        document_embedding_cache=store,
        namespace="text-embedding-3-small",
    )


def get_vectorstore(collection_name: str):
    CHROMA_PATH.mkdir(parents=True, exist_ok=True)
    return Chroma(
        collection_name=collection_name,
        embedding_function=get_embeddings(),
        persist_directory=str(CHROMA_PATH),
    )

def exists_by_doc_id(doc_id: str) -> bool:
    vectorstore = get_raw_news_vectorstore()
    result = vectorstore.get(ids=[doc_id])
    ids = result.get("ids", [])
    return bool(ids)


def exists_by_content_hash(content_hash: str) -> bool:
    vectorstore = get_raw_news_vectorstore()
    result = vectorstore.get(where={"content_hash": content_hash})
    ids = result.get("ids", [])
    return bool(ids)

def get_raw_news_vectorstore():
    return get_vectorstore(RAW_COLLECTION_NAME)


def get_chunk_vectorstore():
    return get_vectorstore(CHUNK_COLLECTION_NAME)


def upsert_raw_documents(documents: List[Document]):
    vectorstore = get_raw_news_vectorstore()
    ids = [doc.metadata.get("doc_id", f"doc_{i}") for i, doc in enumerate(documents)]
    vectorstore.add_documents(documents=documents, ids=ids)


def upsert_chunk_documents(documents: List[Document]):
    vectorstore = get_chunk_vectorstore()
    ids = [doc.metadata.get("chunk_id", f"chunk_{i}") for i, doc in enumerate(documents)]
    vectorstore.add_documents(documents=documents, ids=ids)

def search_chunk_documents(
    query: str,
    k: int = 5,
    company: str | None = None,
):
    vectorstore = get_chunk_vectorstore()

    if company:
        return vectorstore.similarity_search(
            query=query,
            k=k,
            filter={"company": company},
        )

    return vectorstore.similarity_search(
        query=query,
        k=k,
    )

def get_raw_retriever(k: int = 3):
    return get_raw_news_vectorstore().as_retriever(search_kwargs={"k": k})


def get_chunk_retriever(k: int = 5):
    return get_chunk_vectorstore().as_retriever(search_kwargs={"k": k})
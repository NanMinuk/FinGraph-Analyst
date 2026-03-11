import hashlib
from typing import Dict, List, Any
from langchain_core.documents import Document


def compute_content_hash(text: str) -> str:
    normalized = " ".join(text.split()).strip()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def build_langchain_document_from_news(news_doc: Dict[str, Any]) -> Document:
    url = news_doc.get("url", "")
    title = news_doc.get("title", "")
    source = news_doc.get("source", "")
    date = news_doc.get("date", "")
    text = news_doc.get("text", "")
    company = news_doc.get("company", None)

    doc_id = url if url else title
    content_hash = compute_content_hash(text)

    return Document(
        page_content=text,
        metadata={
            "doc_id": doc_id,
            "title": title,
            "source": source,
            "date": date,
            "url": url,
            "company": company,
            "content_hash": content_hash,
        },
    )

def build_langchain_documents_from_chunks(chunked_docs: List[Dict[str, Any]]) -> List[Document]:
    docs: List[Document] = []

    for chunk in chunked_docs:
        docs.append(
            Document(
                page_content=chunk["text"],
                metadata={
                    "chunk_id": chunk["chunk_id"],
                    "doc_id": chunk.get("doc_id"),
                    "title": chunk.get("title"),
                    "source": chunk.get("source"),
                    "date": chunk.get("date"),
                    "company": chunk.get("company"),
                    "url": chunk.get("url"),
                },
            )
        )

    return docs
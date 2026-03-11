from typing import List, Dict, Any

from app.ingestion.news_fetcher import fetch_news_from_url
from app.ingestion.document_builder import (
    build_langchain_document_from_news,
    build_langchain_documents_from_chunks,
)
from app.ingestion.chroma_store import (
    upsert_raw_documents,
    upsert_chunk_documents,
    exists_by_doc_id,
    exists_by_content_hash,
)
from app.retrieval.chunker import split_documents_to_chunks


def ingest_news_urls(urls: List[str]) -> Dict[str, Any]:
    results = []
    langchain_docs = []
    new_documents = []

    for url in urls:
        try:
            if exists_by_doc_id(url):
                results.append({
                    "url": url,
                    "status": "skipped_existing_doc_id",
                })
                continue

            news_doc = fetch_news_from_url(url)
            lc_doc = build_langchain_document_from_news(news_doc)

            content_hash = lc_doc.metadata.get("content_hash")
            if content_hash and exists_by_content_hash(content_hash):
                results.append({
                    "url": url,
                    "title": news_doc.get("title"),
                    "status": "skipped_existing_content_hash",
                })
                continue

            ingested_doc = {
                "doc_id": lc_doc.metadata.get("doc_id"),
                "title": lc_doc.metadata.get("title"),
                "source": lc_doc.metadata.get("source"),
                "date": lc_doc.metadata.get("date"),
                "company": lc_doc.metadata.get("company"),
                "url": lc_doc.metadata.get("url"),
                "text": lc_doc.page_content,
                "status": "ingested",
            }

            results.append(ingested_doc)
            langchain_docs.append(lc_doc)
            new_documents.append(ingested_doc)

        except Exception as e:
            results.append({
                "url": url,
                "status": "error",
                "error": str(e),
            })

    if langchain_docs:
        # 1) raw 뉴스 저장
        upsert_raw_documents(langchain_docs)

        # 2) chunk 생성 후 chunk 컬렉션 저장
        chunked = split_documents_to_chunks(
            new_documents,
            chunk_size=500,
            chunk_overlap=100,
        )
        chunk_docs = build_langchain_documents_from_chunks(chunked)

        if chunk_docs:
            upsert_chunk_documents(chunk_docs)

    summary = {
        "total": len(urls),
        "ingested": sum(1 for r in results if r["status"] == "ingested"),
        "skipped_existing_doc_id": sum(1 for r in results if r["status"] == "skipped_existing_doc_id"),
        "skipped_existing_content_hash": sum(1 for r in results if r["status"] == "skipped_existing_content_hash"),
        "error": sum(1 for r in results if r["status"] == "error"),
    }

    return {
        "summary": summary,
        "results": results,
        "new_documents": new_documents,
    }
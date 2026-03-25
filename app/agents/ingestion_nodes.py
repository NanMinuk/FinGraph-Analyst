"""
ingestion_nodes.py

ingest_news_urls() 파이프라인을 독립적인 LangGraph 노드로 분리한 파일.

노드 실행 순서:
  validate_urls_node
    → [urls 없음] → END
    → [urls 있음] → fetch_node
  fetch_node          : URL fetch + 중복 체크 → raw_news_docs / ingestion_results
  store_raw_node      : raw 뉴스 문서를 Chroma에 upsert
  chunk_node          : 문서를 청크로 분할
  store_chunks_node   : 청크를 Chroma에 upsert
  summarize_node      : ingestion_summary 집계
"""

from typing import Any, Dict, List

from app.agents.state import AppState
from app.ingestion.chroma_store import (
    exists_by_content_hash,
    exists_by_doc_id,
    upsert_chunk_documents,
    upsert_raw_documents,
)
from app.ingestion.document_builder import (
    build_langchain_document_from_news,
    build_langchain_documents_from_chunks,
)
from app.ingestion.news_fetcher import fetch_news_from_url
from app.retrieval.chunker import split_documents_to_chunks


# ---------------------------------------------------------------------------
# 노드 0: validate_urls_node  —  URL 목록 유효성 확인
# ---------------------------------------------------------------------------

def validate_urls_node(state: AppState) -> AppState:
    urls = state.get("urls", [])
    logs = state.get("logs", [])

    if not urls:
        logs.append("validate_urls_node: no urls provided, pipeline will be skipped")
    else:
        logs.append(f"validate_urls_node: {len(urls)} url(s) to process")

    return {**state, "logs": logs}


# ---------------------------------------------------------------------------
# 노드 1: fetch_node  —  URL별 뉴스 fetch + 중복 체크
#
#   출력 state 필드:
#     raw_news_docs     : 신규 문서의 LangChain Document (직렬화된 dict 리스트)
#     new_documents     : 저장/청크용 plain dict 리스트
#     ingestion_results : URL별 처리 결과 (status 포함)
# ---------------------------------------------------------------------------

def fetch_node(state: AppState) -> AppState:
    urls = state.get("urls", [])
    logs = state.get("logs", [])

    results: List[Dict[str, Any]] = []
    raw_news_docs = []   # LangChain Document objects (upsert_raw_documents 용)
    new_documents: List[Dict[str, Any]] = []

    for url in urls:
        try:
            # 1-1) doc_id(URL) 중복 체크
            if exists_by_doc_id(url):
                results.append({"url": url, "status": "skipped_existing_doc_id"})
                logs.append(f"fetch_node: skipped (doc_id exists) url={url}")
                continue

            # 1-2) fetch + document 빌드
            news_doc = fetch_news_from_url(url)
            lc_doc = build_langchain_document_from_news(news_doc)

            # 1-3) content_hash 중복 체크
            content_hash = lc_doc.metadata.get("content_hash")
            if content_hash and exists_by_content_hash(content_hash):
                results.append({
                    "url": url,
                    "title": news_doc.get("title"),
                    "status": "skipped_existing_content_hash",
                })
                logs.append(f"fetch_node: skipped (content_hash exists) url={url}")
                continue

            # 1-4) 신규 문서 등록
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
            raw_news_docs.append(lc_doc)
            new_documents.append(ingested_doc)
            logs.append(f"fetch_node: fetched url={url}, title={ingested_doc['title']!r}")

        except Exception as e:
            results.append({"url": url, "status": "error", "error": str(e)})
            logs.append(f"fetch_node: error url={url} error={e}")

    logs.append(
        f"fetch_node: done "
        f"(total={len(urls)}, new={len(new_documents)}, "
        f"skipped={len(urls) - len(new_documents) - sum(1 for r in results if r['status'] == 'error')}, "
        f"error={sum(1 for r in results if r['status'] == 'error')})"
    )

    return {
        **state,
        "raw_news_docs": raw_news_docs,   # LangChain Document list
        "new_documents": new_documents,
        "ingestion_results": results,
        "logs": logs,
    }


# ---------------------------------------------------------------------------
# 노드 2: store_raw_node  —  신규 raw 뉴스 문서를 Chroma에 upsert
# ---------------------------------------------------------------------------

def store_raw_node(state: AppState) -> AppState:
    raw_news_docs = state.get("raw_news_docs", [])
    logs = state.get("logs", [])

    if not raw_news_docs:
        logs.append("store_raw_node: skipped (no new documents)")
        return {**state, "logs": logs}

    upsert_raw_documents(raw_news_docs)
    logs.append(f"store_raw_node: upserted {len(raw_news_docs)} raw document(s)")

    return {**state, "logs": logs}


# ---------------------------------------------------------------------------
# 노드 3: chunk_node  —  신규 문서를 청크로 분할
# ---------------------------------------------------------------------------

def chunk_node(state: AppState) -> AppState:
    new_documents = state.get("new_documents", [])
    logs = state.get("logs", [])

    if not new_documents:
        logs.append("chunk_node: skipped (no new documents)")
        return {**state, "chunked_documents": [], "logs": logs}

    chunked = split_documents_to_chunks(
        new_documents,
        chunk_size=500,
        chunk_overlap=100,
    )
    logs.append(f"chunk_node: {len(new_documents)} doc(s) → {len(chunked)} chunk(s)")

    return {
        **state,
        "chunked_documents": chunked,
        "logs": logs,
    }


# ---------------------------------------------------------------------------
# 노드 4: store_chunks_node  —  청크를 Chroma에 upsert
# ---------------------------------------------------------------------------

def store_chunks_node(state: AppState) -> AppState:
    chunked_documents = state.get("chunked_documents", [])
    logs = state.get("logs", [])

    if not chunked_documents:
        logs.append("store_chunks_node: skipped (no chunks)")
        return {**state, "logs": logs}

    chunk_docs = build_langchain_documents_from_chunks(chunked_documents)
    if chunk_docs:
        upsert_chunk_documents(chunk_docs)
        logs.append(f"store_chunks_node: upserted {len(chunk_docs)} chunk(s)")
    else:
        logs.append("store_chunks_node: no chunk docs to upsert")

    return {**state, "logs": logs}


# ---------------------------------------------------------------------------
# 노드 5: summarize_ingestion_node  —  ingestion_summary 집계
# ---------------------------------------------------------------------------

def summarize_ingestion_node(state: AppState) -> AppState:
    urls = state.get("urls", [])
    results = state.get("ingestion_results", [])
    logs = state.get("logs", [])

    summary = {
        "total": len(urls),
        "ingested": sum(1 for r in results if r.get("status") == "ingested"),
        "skipped_existing_doc_id": sum(
            1 for r in results if r.get("status") == "skipped_existing_doc_id"
        ),
        "skipped_existing_content_hash": sum(
            1 for r in results if r.get("status") == "skipped_existing_content_hash"
        ),
        "error": sum(1 for r in results if r.get("status") == "error"),
    }
    logs.append(
        f"summarize_ingestion_node: "
        f"total={summary['total']}, ingested={summary['ingested']}, "
        f"skipped_doc_id={summary['skipped_existing_doc_id']}, "
        f"skipped_hash={summary['skipped_existing_content_hash']}, "
        f"error={summary['error']}"
    )

    return {
        **state,
        "ingestion_summary": summary,
        "logs": logs,
    }

from typing import List, Dict, Any, Optional
from app.ingestion.chroma_store import search_chunk_documents


def diversify_documents(docs: List[Dict[str, Any]], k: int = 5) -> List[Dict[str, Any]]:
    diversified = []
    used_doc_ids = set()

    for d in docs:
        doc_id = d.get("doc_id")
        if doc_id not in used_doc_ids:
            diversified.append(d)
            used_doc_ids.add(doc_id)
        if len(diversified) >= k:
            return diversified

    for d in docs:
        if d not in diversified:
            diversified.append(d)
        if len(diversified) >= k:
            break

    return diversified


def _convert_results(results) -> List[Dict[str, Any]]:
    docs = []
    for doc in results:
        meta = doc.metadata or {}
        docs.append({
            "doc_id": meta.get("doc_id"),
            "chunk_id": meta.get("chunk_id"),
            "title": meta.get("title"),
            "source": meta.get("source"),
            "date": meta.get("date"),
            "company": meta.get("company"),
            "url": meta.get("url"),
            "text": doc.page_content,
        })
    return docs


def retrieve_documents(query: str, company: Optional[str] = None, k: int = 5) -> List[Dict[str, Any]]:
    search_query = f"{company} {query}" if company else query

    # 1차: company metadata filter 검색
    results = search_chunk_documents(
        query=search_query,
        k=max(k * 2, 10),
        company=company,
    )
    docs = _convert_results(results)

    if company:
        filtered_docs = []
        for d in docs:
            title = (d.get("title") or "")
            text = (d.get("text") or "")
            company_meta = d.get("company")

            if company_meta == company or company in title or company in text:
                filtered_docs.append(d)

        if filtered_docs:
            return filtered_docs[:k]

        # 2차 fallback: company filter 없이 semantic retrieval
        fallback_results = search_chunk_documents(
            query=search_query,
            k=max(k * 2, 10),
            company=None,
        )
        fallback_docs = _convert_results(fallback_results)

        company_fallback_docs = []
        for d in fallback_docs:
            title = (d.get("title") or "")
            text = (d.get("text") or "")
            if company in title or company in text:
                company_fallback_docs.append(d)

        if company_fallback_docs:
            return company_fallback_docs[:k]

        # 3차 fallback: 정말 없으면 그냥 semantic top-k라도 반환
        if fallback_docs:
            return diversify_documents(fallback_docs, k=k)

        return []

    return diversify_documents(docs, k=k)
from typing import Optional, Dict, Any, List

from app.retrieval.retriever import retrieve_documents


def retrieve_relevant_chunks_tool(
    query: str,
    company: Optional[str] = None,
    k: int = 5,
) -> Dict[str, Any]:
    docs = retrieve_documents(
        query=query,
        company=company,
        k=k,
    )

    summary = {
        "query": query,
        "company": company,
        "requested_k": k,
        "retrieved_count": len(docs),
    }

    return {
        "summary": summary,
        "documents": docs,
    }
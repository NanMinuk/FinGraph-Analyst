import json
from pathlib import Path
from typing import List, Dict, Any, Optional

DATA_PATH = Path("data/sample_docs.json")

QUERY_EXPANSION = {
    "2차전지": ["배터리", "LG에너지솔루션", "투자", "공급망", "북미"],
    "반도체": ["HBM", "SK하이닉스", "삼성전자", "AI 반도체"],
}


def load_docs() -> List[Dict[str, Any]]:
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def expand_query_terms(query: str) -> List[str]:
    terms = query.split()
    expanded = list(terms)

    for key, related_terms in QUERY_EXPANSION.items():
        if key in query:
            expanded.extend(related_terms)

    # 중복 제거
    return list(dict.fromkeys(expanded))


def retrieve_documents(query: str, company: Optional[str] = None) -> List[Dict[str, Any]]:
    docs = load_docs()
    results = []

    query_terms = expand_query_terms(query)

    for doc in docs:
        title = doc.get("title", "")
        text = doc.get("text", "")
        full_text = f"{title} {text}"

        if company and company in full_text:
            results.append(doc)
            continue

        if any(term in full_text for term in query_terms):
            results.append(doc)

    return results[:5]
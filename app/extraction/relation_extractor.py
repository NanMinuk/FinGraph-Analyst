from typing import List, Dict, Any, Tuple

EVENT_KEYWORDS = {
    "투자": "invests_in",
    "공급": "supplies",
    "수혜": "benefits_from",
    "실적": "reports",
    "계약": "announces_contract",
    "규제": "regulatory_risk"
}


def extract_entities_and_relations(
    docs: List[Dict[str, Any]]
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    entities = []
    relations = []

    for doc in docs:
        company = (doc.get("company") or "Unknown").strip()
        title = doc.get("title", "")
        text = doc.get("text", "")
        full_text = f"{title} {text}"

        entities.append({
            "name": company,
            "type": "Company"
        })

        for keyword, relation in EVENT_KEYWORDS.items():
            if keyword in full_text:
                event_name = keyword.strip()
                entities.append({
                    "name": event_name,
                    "type": "Event"
                })

                relations.append({
                    "head": company,
                    "head_type": "Company",
                    "relation": relation,
                    "tail": event_name,
                    "tail_type": "Event",
                    "evidence": title,
                    "document_id": doc["doc_id"],
                    "confidence": 0.7,
                })

    return entities, relations
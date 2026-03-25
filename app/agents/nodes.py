from app.agents.state import AppState
from app.agents.intent_classifier import classify_intent_llm, classify_intent_rule_based

# ingest_news_node는 ingestion_nodes.py의 개별 노드들로 대체됨
# validate_urls_node → fetch_node → store_raw_node → chunk_node → store_chunks_node → summarize_ingestion_node


def route_node(state: AppState) -> AppState:
    query = state.get("query", "")
    logs = state.get("logs", [])

    try:
        intent = classify_intent_llm(query)
        logs.append(f"route_node: intent={intent} (llm)")
    except Exception as e:
        intent = classify_intent_rule_based(query)
        logs.append(f"route_node: intent={intent} (rule_fallback, error={str(e)})")

    return {
        **state,
        "intent": intent,
        "logs": logs,
    }

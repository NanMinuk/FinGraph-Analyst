from app.agents.state import AppState
from app.ingestion.pipeline import ingest_news_urls
from app.agents.analysis_agent import run_analysis_agent
from app.agents.intent_classifier import classify_intent_llm, classify_intent_rule_based

def ingest_news_node(state: AppState) -> AppState:
    urls = state.get("urls", [])
    logs = state.get("logs", [])

    if not urls:
        logs.append("ingest_news_node: skipped (no urls)")
        return {
            **state,
            "ingestion_summary": {
                "total": 0,
                "ingested": 0,
                "skipped_existing_doc_id": 0,
                "skipped_existing_content_hash": 0,
                "error": 0,
            },
            "ingestion_results": [],
            "logs": logs,
        }

    out = ingest_news_urls(urls)

    logs.append(
        f"ingest_news_node: total={out['summary']['total']}, ingested={out['summary']['ingested']}, skipped_doc_id={out['summary']['skipped_existing_doc_id']}, skipped_hash={out['summary']['skipped_existing_content_hash']}, error={out['summary']['error']}"
    )

    return {
        **state,
        "ingestion_summary": out["summary"],
        "ingestion_results": out["results"],
        "logs": logs,
    }

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

def analysis_agent_node(state:AppState) -> AppState:
    return run_analysis_agent(state)

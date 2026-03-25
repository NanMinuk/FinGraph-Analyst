from app.agents.state import AppState
from app.agents.intent_classifier import classify_intent_llm, classify_intent_rule_based

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

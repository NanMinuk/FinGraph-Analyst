from langgraph.graph import StateGraph, END
from app.agents.state import AppState
from app.agents.nodes import ingest_news_node


def build_ingestion_workflow():
    graph = StateGraph(AppState)

    graph.add_node("ingest_news", ingest_news_node)
    graph.set_entry_point("ingest_news")
    graph.add_edge("ingest_news", END)

    return graph.compile()
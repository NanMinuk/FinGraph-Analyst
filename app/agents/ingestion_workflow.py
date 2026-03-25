from langgraph.graph import StateGraph, END

from app.agents.state import AppState
from app.agents.ingestion_nodes import (
    validate_urls_node,
    fetch_node,
    store_raw_node,
    chunk_node,
    store_chunks_node,
    summarize_ingestion_node,
)


def route_after_validate(state: AppState) -> str:
    """URL이 없으면 바로 summarize로."""
    urls = state.get("urls", [])
    return "fetch" if urls else "summarize_ingestion"


def route_after_fetch(state: AppState) -> str:
    """신규 문서가 없으면 바로 summarize로 (store/chunk 스킵)."""
    new_documents = state.get("new_documents", [])
    return "store_raw" if new_documents else "summarize_ingestion"



def build_ingestion_workflow():
    graph = StateGraph(AppState)

    graph.add_node("validate_urls", validate_urls_node)
    graph.add_node("fetch", fetch_node)
    graph.add_node("store_raw", store_raw_node)
    graph.add_node("chunk", chunk_node)
    graph.add_node("store_chunks", store_chunks_node)
    graph.add_node("summarize_ingestion", summarize_ingestion_node)


    graph.set_entry_point("validate_urls")
    graph.add_conditional_edges(
        "validate_urls",
        route_after_validate,
        {
            "fetch": "fetch",
            "summarize_ingestion": "summarize_ingestion",
        },
    )
    graph.add_conditional_edges(
        "fetch",
        route_after_fetch,
        {
            "store_raw": "store_raw",
            "summarize_ingestion": "summarize_ingestion",
        },
    )

    graph.add_edge("store_raw", "chunk")
    graph.add_edge("chunk", "store_chunks")
    graph.add_edge("store_chunks", "summarize_ingestion")
    graph.add_edge("summarize_ingestion", END)

    return graph.compile()

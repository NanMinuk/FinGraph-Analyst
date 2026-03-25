from langgraph.graph import StateGraph, END

from app.agents.state import AppState
from app.agents.nodes import route_node
from app.agents.analysis_nodes import (
    plan_node,
    retrieval_node,
    replan_retrieval_node,
    extraction_node,
    replan_extraction_node,
    upsert_node,
    graph_node,
    brief_node,
    structured_node,
)


def route_after_retrieval(state: AppState) -> str:
    """검색 결과가 없고 아직 replan 기회가 남아있으면 replan, 아니면 extraction으로."""
    documents = state.get("documents", [])
    replan_count = state.get("replan_count", 0)

    if len(documents) == 0 and replan_count < 1:
        return "replan_retrieval"
    return "extraction"


def route_after_extraction(state: AppState) -> str:
    """relation이 없고 아직 replan 기회가 남아있으면 replan, 아니면 upsert으로."""
    relations = state.get("relations", [])
    extraction_replan_count = state.get("extraction_replan_count", 0)

    if len(relations) == 0 and extraction_replan_count < 1:
        return "replan_extraction"
    return "upsert"


def build_workflow():
    graph = StateGraph(AppState)

    # ── 노드 등록 
    graph.add_node("route", route_node)
    graph.add_node("plan", plan_node)
    graph.add_node("retrieval", retrieval_node)
    graph.add_node("replan_retrieval", replan_retrieval_node)
    graph.add_node("extraction", extraction_node)
    graph.add_node("replan_extraction", replan_extraction_node)
    graph.add_node("upsert", upsert_node)
    graph.add_node("graph_builder", graph_node)
    graph.add_node("brief", brief_node)
    graph.add_node("structured", structured_node)

    # ── 엣지 연결
    graph.set_entry_point("route")

    graph.add_edge("route", "plan")
    graph.add_edge("plan", "retrieval")

    # retrieval → (replan_retrieval | extraction)
    graph.add_conditional_edges(
        "retrieval",
        route_after_retrieval,
        {
            "replan_retrieval": "replan_retrieval",
            "extraction": "extraction",
        },
    )

    # replan 후 다시 retrieval
    graph.add_edge("replan_retrieval", "retrieval")

    # extraction → (replan_extraction | upsert)
    graph.add_conditional_edges(
        "extraction",
        route_after_extraction,
        {
            "replan_extraction": "replan_extraction",
            "upsert": "upsert",
        },
    )

    # replan 후 다시 retrieval → extraction
    graph.add_edge("replan_extraction", "retrieval")

    graph.add_edge("upsert", "graph_builder")
    graph.add_edge("graph_builder", "brief")
    graph.add_edge("brief", "structured")
    graph.add_edge("structured", END)

    return graph.compile()

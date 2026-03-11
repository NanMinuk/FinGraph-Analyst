from langgraph.graph import StateGraph, END
from app.agents.state import AppState
from app.agents.nodes import (
    route_node,
    analysis_agent_node,
)


def build_workflow():
    graph = StateGraph(AppState)

    graph.add_node("route", route_node)
    graph.add_node("analysis_agent", analysis_agent_node)

    graph.set_entry_point("route")

    graph.add_edge("route", "analysis_agent")
    graph.add_edge("analysis_agent", END)

    return graph.compile()
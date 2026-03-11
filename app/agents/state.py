from typing import TypedDict, List, Dict, Any, Optional


class AppState(TypedDict, total=False):
    query: str
    company: Optional[str]
    intent: str

    urls : List[str]

    documents: List[Dict[str, Any]]
    entities: List[Dict[str, Any]]
    relations: List[Dict[str, Any]]
    document_relation_map : Dict[str, List[Dict[str, Any]]]
    selected_graph_relations : List[Dict[str, Any]]
    persistent_graph_relations : List[Dict[str, Any]]
    hybrid_graph_relations : List[Dict[str, Any]]
    graph_relations: List[Dict[str, Any]]

    supervisor_explanation : Dict[str,Any]
    
    key_points : List[str]
    risk_points : List[str]
    relation_points : List[str]

    ingestion_summary: Dict[str, Any]
    ingestion_results: List[Dict[str, Any]]

    report: str
    raw_report : str
    graph_upsert_result: Dict[str, Any]
    logs: List[str]
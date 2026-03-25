from typing import TypedDict, List, Dict, Any, Optional
from langchain_core.documents import Document


class AppState(TypedDict, total=False):
    query: str
    company: Optional[str]
    intent: str

    urls: List[str]

    # supervisor plan
    plan: Dict[str, Any]
    replan_count: int           # retrieval replan 횟수 (최대 1회)
    extraction_replan_count: int  # extraction replan 횟수 (최대 1회)

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

    # ingestion 중간 상태
    raw_news_docs: List[Document]              # fetch_node 결과 (LangChain Document 객체)
    new_documents: List[Dict[str, Any]]        # 중복 제외된 신규 문서
    chunked_documents: List[Dict[str, Any]]    # chunk 생성 결과

    ingestion_summary: Dict[str, Any]
    ingestion_results: List[Dict[str, Any]]

    report: str
    raw_report : str
    graph_upsert_result: Dict[str, Any]
    logs: List[str]
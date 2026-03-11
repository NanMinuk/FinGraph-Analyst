from typing import Optional, List, Dict, Any
from langchain.tools import tool

from app.tools.retrieval_tools import retrieve_relevant_chunks_tool
from app.tools.extraction_tools import extract_relations_from_chunks_tool
from app.tools.graph_tools import (
    build_hybrid_graph_context_tool,
    selective_upsert_graph_tool,
)
from app.tools.reporting_tools import generate_investment_brief_tool


@tool
def retrieve_relevant_chunks(
    query: str,
    company: Optional[str] = None,
    k: int = 5,
) -> Dict[str, Any]:
    """질문과 관련된 뉴스 chunk를 검색한다. 특정 기업이 있으면 해당 기업 중심으로 우선 검색한다."""
    return retrieve_relevant_chunks_tool(query=query, company=company, k=k)


@tool
def extract_relations_from_chunks(
    documents: List[Dict[str, Any]],
    confidence_threshold: float = 0.65,
) -> Dict[str, Any]:
    """검색된 뉴스 chunk들에서 회사-이벤트 관계를 추출한다."""
    return extract_relations_from_chunks_tool(
        documents=documents,
        confidence_threshold=confidence_threshold,
    )


@tool
def build_hybrid_graph_context(
    current_relations: List[Dict[str, Any]],
    company: Optional[str] = None,
) -> Dict[str, Any]:
    """현재 질문에서 추출한 relation과 Neo4j의 persistent relation을 결합해 hybrid graph context를 만든다."""
    return build_hybrid_graph_context_tool(
        current_relations=current_relations,
        company=company,
    )


@tool
def selective_upsert_graph(
    relations: List[Dict[str, Any]],
    min_confidence: float = 0.8,
) -> Dict[str, Any]:
    """고신뢰 relation만 Neo4j에 선택적으로 저장한다."""
    return selective_upsert_graph_tool(
        relations=relations,
        min_confidence=min_confidence,
    )


@tool
def generate_investment_brief(
    query: str,
    intent: str,
    documents: List[Dict[str, Any]],
    entities: List[Dict[str, Any]],
    relations: List[Dict[str, Any]],
    document_relation_map: Dict[str, List[Dict[str, Any]]],
    hybrid_graph_relations: List[Dict[str, Any]],
    persistent_graph_relations: List[Dict[str, Any]],
    supervisor_explanation: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """검색, 관계 추출, 그래프 결합 결과를 바탕으로 최종 투자 브리프를 생성한다."""
    return generate_investment_brief_tool(
        query=query,
        intent=intent,
        documents=documents,
        entities=entities,
        relations=relations,
        document_relation_map=document_relation_map,
        hybrid_graph_relations=hybrid_graph_relations,
        persistent_graph_relations=persistent_graph_relations,
        supervisor_explanation=supervisor_explanation,
    )


ALL_ANALYSIS_TOOLS = [
    retrieve_relevant_chunks,
    extract_relations_from_chunks,
    build_hybrid_graph_context,
    selective_upsert_graph,
    generate_investment_brief,
]
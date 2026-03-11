from typing import Optional, List, Dict, Any

from pydantic import BaseModel, Field
from langchain_core.tools import StructuredTool

from app.tools.retrieval_tools import retrieve_relevant_chunks_tool
from app.tools.extraction_tools import extract_relations_from_chunks_tool
from app.tools.graph_tools import build_hybrid_graph_context_tool
from app.tools.reporting_tools import generate_investment_brief_tool


class RetrievalInput(BaseModel):
    query: str = Field(..., description="사용자 질문")
    company: Optional[str] = Field(default=None, description="분석 대상 기업명")
    k: int = Field(default=5, description="가져올 chunk 개수")


class ExtractionInput(BaseModel):
    documents: List[Dict[str, Any]] = Field(..., description="retrieval로 가져온 chunk 목록")
    confidence_threshold: float = Field(default=0.65, description="relation confidence threshold")


class HybridGraphInput(BaseModel):
    current_relations: List[Dict[str, Any]] = Field(..., description="현재 질문에서 추출한 relation 목록")
    company: Optional[str] = Field(default=None, description="관련 기업명")


class BriefInput(BaseModel):
    query: str
    intent: str
    documents: List[Dict[str, Any]]
    entities: List[Dict[str, Any]]
    relations: List[Dict[str, Any]]
    document_relation_map: Dict[str, List[Dict[str, Any]]]
    hybrid_graph_relations: List[Dict[str, Any]]
    persistent_graph_relations: List[Dict[str, Any]]


retrieve_relevant_chunks_lc_tool = StructuredTool.from_function(
    func=retrieve_relevant_chunks_tool,
    name="retrieve_relevant_chunks",
    description="질문과 관련된 뉴스 chunk를 검색한다. company가 있으면 해당 기업 중심으로 우선 검색한다.",
    args_schema=RetrievalInput,
)

extract_relations_from_chunks_lc_tool = StructuredTool.from_function(
    func=extract_relations_from_chunks_tool,
    name="extract_relations_from_chunks",
    description="검색된 뉴스 chunk들에서 회사-이벤트 관계를 추출한다.",
    args_schema=ExtractionInput,
)

build_hybrid_graph_context_lc_tool = StructuredTool.from_function(
    func=build_hybrid_graph_context_tool,
    name="build_hybrid_graph_context",
    description="현재 relation과 Neo4j의 누적 relation을 결합해 hybrid graph context를 만든다.",
    args_schema=HybridGraphInput,
)

generate_investment_brief_lc_tool = StructuredTool.from_function(
    func=generate_investment_brief_tool,
    name="generate_investment_brief",
    description="검색, 추출, 그래프 결합 결과를 바탕으로 최종 투자 브리프를 생성한다.",
    args_schema=BriefInput,
)


ALL_ANALYSIS_TOOLS = [
    retrieve_relevant_chunks_lc_tool,
    extract_relations_from_chunks_lc_tool,
    build_hybrid_graph_context_lc_tool,
    generate_investment_brief_lc_tool,
]
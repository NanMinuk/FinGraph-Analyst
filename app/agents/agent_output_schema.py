from typing import List, Literal
from pydantic import BaseModel, Field


class AnalysisAgentOutput(BaseModel):
    intent: Literal["company_analysis", "risk_analysis", "relation_query"] = Field(...)
    summary: str = Field(..., description="한두 문장의 핵심 요약")
    key_points: List[str] = Field(default_factory=list)
    risk_points: List[str] = Field(default_factory=list)
    relation_points: List[str] = Field(default_factory=list)
    final_answer: str = Field(..., description="사용자에게 보여줄 최종 답변")
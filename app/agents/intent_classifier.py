from typing import Literal

from dotenv import load_dotenv
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI

load_dotenv()


class IntentClassification(BaseModel):
    intent: Literal["company_analysis", "risk_analysis", "relation_query"] = Field(
        ...,
        description="사용자 질문의 분석 의도"
    )


def classify_intent_llm(query: str) -> str:
    llm = ChatOpenAI(model="gpt-5-nano", temperature=0)

    structured_llm = llm.with_structured_output(
        IntentClassification,
        method="json_schema",
    )

    prompt = f"""
다음 사용자 질문의 intent를 아래 3개 중 하나로 분류하라.

- company_analysis: 특정 기업의 투자 포인트, 모멘텀, 최근 이슈, 핵심 이벤트를 분석하려는 질문
- risk_analysis: 특정 기업의 리스크, 악재, 위험 요인을 분석하려는 질문
- relation_query: 특정 기업 하나보다 섹터/테마/복수 종목 간 연결관계를 보려는 질문

질문:
{query}
""".strip()

    result = structured_llm.invoke(prompt)
    return result.intent

def classify_intent_rule_based(query: str) -> str:
    q = (query or "").lower()

    risk_keywords = ["리스크", "악재", "위험", "부담", "문제"]
    relation_keywords = ["연결", "관련 종목", "엮인", "수혜주", "테마", "관련주"]

    if any(k in q for k in risk_keywords):
        return "risk_analysis"

    if any(k in q for k in relation_keywords):
        return "relation_query"

    return "company_analysis"
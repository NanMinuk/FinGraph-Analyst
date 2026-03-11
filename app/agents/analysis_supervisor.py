from typing import Literal, Optional
from pydantic import BaseModel, Field
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

load_dotenv()


class AnalysisPlan(BaseModel):
    intent: Literal["company_analysis", "risk_analysis", "relation_query"] = Field(...)
    retrieval_k: int = Field(..., ge=1, le=10)
    retrieval_company: Optional[str] = Field(default=None)
    use_retrieval: bool = Field(default=True)
    use_extraction: bool = Field(default=True)
    use_hybrid_graph: bool = Field(default=True)
    use_brief_generation: bool = Field(default=True)
    use_selective_upsert : bool = Field(default=True)
    reason: str = Field(...)


def make_analysis_plan_llm(state):
    query = state.get("query", "")
    company = state.get("company")
    intent = state.get("intent", "company_analysis")

    llm = ChatOpenAI(model="gpt-5-nano", temperature=0)
    planner = llm.with_structured_output(AnalysisPlan)

    prompt = f"""
    너는 금융 GraphRAG 분석 계획을 세우는 supervisor다.

    질문:
    {query}

    company:
    {company}

    intent:
    {intent}

    아래를 결정하라:
    - retrieval_k: 1~10
    - retrieval_company: 특정 기업 중심이면 company 사용, 아니면 null
    - use_retrieval/use_extraction/use_hybrid_graph/use_brief_generation/use_selective_upsert
    - reason: 한 문장 설명

    판단 기준:
    - company_analysis: 특정 기업 중심 분석이면 보통 use_selective_upsert=true
    - risk_analysis: 의미 있는 기업 리스크 relation이 추출될 가능성이 높으면 use_selective_upsert=true
    - relation_query: 단순 탐색/연결 조회면 보통 use_selective_upsert=false
    - 검색/추출 결과가 일회성 탐색에 가깝다면 use_selective_upsert=false
    - 축적 가치가 있는 고신뢰 기업-이벤트 관계를 얻을 가능성이 높다면 use_selective_upsert=true
    """.strip()

    result = planner.invoke(prompt)
    return result.model_dump()


def make_analysis_plan_rule_based(state):
    intent = state.get("intent", "company_analysis")
    company = state.get("company")
    query = state.get("query", "")

    plan = {
        "intent": intent,
        "query": query,
        "company": company,
        "use_retrieval": True,
        "use_extraction": True,
        "use_hybrid_graph": True,
        "use_brief_generation": True,
        "use_selective_upsert" : True,
        "retrieval_k": 5,
        "retrieval_company": company,
        "reason": "",
    }

    if intent == "company_analysis":
        plan["retrieval_k"] = 5
        plan["retrieval_company"] = company
        plan["use_selective_upsert"] = True
        plan["reason"] = "특정 기업 중심 분석이므로 company-aware retrieval을 우선 사용합니다."
    elif intent == "risk_analysis":
        plan["retrieval_k"] = 6
        plan["retrieval_company"] = company
        plan["use_selective_upsert"] = True
        plan["reason"] = "리스크 분석이므로 기업 중심 retrieval 후 리스크 관련 relation 추출을 수행합니다."
    elif intent == "relation_query":
        plan["retrieval_k"] = 8
        plan["retrieval_company"] = None
        plan["use_selective_upsert"] = False
        plan["reason"] = "연결관계 질의이므로 특정 기업 필터 없이 넓게 retrieval합니다."
    else:
        plan["use_selective_upsert"] = False
        plan["reason"] = "기본 분석 흐름을 사용하며 저장은 생략합니다."

    return plan


def make_analysis_plan(state):
    try:
        return make_analysis_plan_llm(state)
    except Exception:
        return make_analysis_plan_rule_based(state)


def replan_after_retrieval(state, previous_plan, retrieved_count: int):
    query = state.get("query", "")
    company = state.get("company")
    intent = state.get("intent", "company_analysis")

    try:
        llm = ChatOpenAI(model="gpt-4.1-mini", temperature=0)
        planner = llm.with_structured_output(AnalysisPlan)

        prompt = f"""
너는 금융 GraphRAG supervisor다.

기존 계획:
{previous_plan}

실행 결과:
- retrieved_count = {retrieved_count}

질문:
{query}

company:
{company}

intent:
{intent}

검색 결과가 부족하다.
기존 계획을 수정하라.

원칙:
- retrieved_count가 0이면 retrieval_company를 null로 완화하는 것을 우선 고려
- retrieval_k는 필요 시 늘릴 수 있음
- use_extraction/use_hybrid_graph/use_brief_generation는 일반적으로 유지
- use_selective_upsert는 일회성 탐색이면 false, 고신뢰 기업 분석으로 이어질 가능성이 높으면 true
- reason은 수정 이유를 한 문장으로 설명
""".strip()

        result = planner.invoke(prompt)
        return result.model_dump()

    except Exception:
        replanned = dict(previous_plan)

        if retrieved_count == 0:
            replanned["retrieval_company"] = None
            replanned["retrieval_k"] = min(int(replanned.get("retrieval_k", 5)) + 2, 10)
            
            if replanned.get("intent") == "relation_query":
                replanned["use_selective_upsert"] = False

            replanned["reason"] = "검색 결과가 없어 company 필터를 완화하고 retrieval 범위를 넓혔습니다."
        else:
            replanned["retrieval_k"] = min(int(replanned.get("retrieval_k", 5)) + 2, 10)
            replanned["reason"] = "검색 결과가 적어 retrieval 범위를 넓혔습니다."

        return replanned
    
def replan_after_extraction(state, previous_plan, relation_count: int):
    query = state.get("query", "")
    company = state.get("company")
    intent = state.get("intent", "company_analysis")

    try:
        llm = ChatOpenAI(model="gpt-4.1-mini", temperature=0)
        planner = llm.with_structured_output(AnalysisPlan)

        prompt = f"""
너는 금융 GraphRAG supervisor다.

기존 계획:
{previous_plan}

실행 결과:
- relation_count = {relation_count}

질문:
{query}

company:
{company}

intent:
{intent}

검색은 되었지만 relation이 충분히 추출되지 않았다.
기존 계획을 수정하라.

원칙:
- relation_count가 0이면 retrieval_k를 늘리거나 retrieval_company를 완화할 수 있다
- use_extraction/use_hybrid_graph/use_brief_generation는 일반적으로 유지
- use_selective_upsert는 relation이 거의 없거나 일회성 탐색이면 false로 둘 수 있다
- reason은 수정 이유를 한 문장으로 설명
""".strip()

        result = planner.invoke(prompt)
        return result.model_dump()

    except Exception:
        replanned = dict(previous_plan)
        replanned["retrieval_k"] = min(int(replanned.get("retrieval_k", 5)) + 2, 10)

        if relation_count == 0 and replanned.get("retrieval_company") is not None:
            replanned["retrieval_company"] = None

        replanned["use_selective_upsert"] = False

        if relation_count == 0:
            replanned["reason"] = "관계 추출 결과가 없어 retrieval 범위를 넓히고 company 필터를 완화했습니다."
        else:
            replanned["reason"] = "관계 추출 결과가 부족해 retrieval 범위를 넓혔습니다."

        return replanned
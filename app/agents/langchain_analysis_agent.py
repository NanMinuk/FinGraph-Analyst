from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain_openai import ChatOpenAI

from app.tools.langchain_tools import ALL_ANALYSIS_TOOLS
from app.agents.agent_output_schema import AnalysisAgentOutput

load_dotenv()


def get_langchain_analysis_agent():
    model = ChatOpenAI(model="gpt-5-nano", temperature=0)

    agent = create_agent(
        model=model,
        tools=ALL_ANALYSIS_TOOLS,
        system_prompt=(
            "너는 금융 뉴스 기반 분석 에이전트다. "
            "질문을 받으면 필요한 경우 retrieval, relation extraction, hybrid graph construction, "
            "brief generation tool을 순서에 맞게 사용하라. "
            "특정 기업 분석이면 해당 company를 retrieval에 반영하고, "
            "relation_query이면 다양한 종목과 문서를 고려하라."
        ),
    )
    return agent

def get_structured_response_model():
    llm = ChatOpenAI(model="gpt-5-nano", temperature=0)
    return llm.with_structured_output(AnalysisAgentOutput)

def run_structured_analysis(query: str, company: str | None = None):
    agent = get_langchain_analysis_agent()

    company_hint = f" company는 {company}." if company else ""
    agent_result = agent.invoke(
        {
            "messages": [
                {
                    "role": "user",
                    "content": f"{query}.{company_hint}"
                }
            ]
        }
    )

    final_text = agent_result["messages"][-1].content

    structured_model = get_structured_response_model()
    structured = structured_model.invoke(
        f"""
다음 분석 답변을 구조화하라.

질문: {query}
company: {company}
답변:
{final_text}
"""
    )

    return {
        "raw_agent_result": agent_result,
        "structured_output": structured.model_dump(),
    }

from app.agents.agent_output_schema import AnalysisAgentOutput
from langchain_openai import ChatOpenAI


def build_structured_brief_from_report(
    query: str,
    company: str | None,
    intent: str,
    report: str,
):
    llm = ChatOpenAI(model="gpt-5-nano", temperature=0)

    structured_llm = llm.with_structured_output(AnalysisAgentOutput)

    prompt = f"""
다음 금융 분석 리포트를 구조화하라.

조건:
- intent는 반드시 아래 중 하나:
  - company_analysis
  - risk_analysis
  - relation_query
- summary는 2문장 이하
- key_points는 최대 3개, 각 항목은 1문장
- risk_points는 최대 2개, 각 항목은 1문장
- relation_points는 최대 3개, 각 항목은 1문장
- final_answer는 8문장 이하
- "구조화한 요약", "출처:", "필요하시면", "추가로" 같은 메타 표현 금지

질문:
{query}

company:
{company}

intent:
{intent}

리포트:
{report}
""".strip()

    result = structured_llm.invoke(prompt)
    return result.model_dump()
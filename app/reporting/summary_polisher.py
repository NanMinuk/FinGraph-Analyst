from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

load_dotenv()


def polish_brief_summary(
    query: str,
    intent: str,
    relations_text: str,
    max_sentences: int = 2,
) -> str:
    llm = ChatOpenAI(model="gpt-4.1-mini", temperature=0.2)

    prompt = f"""
사용자 질문과 추출된 핵심 관계를 바탕으로 금융 리서치 브리프의 '한 줄 요약'을 작성하라.

조건:
- 한국어로 작성
- {max_sentences}문장 이내
- 과장 없이, 분석 보조 도구의 톤으로 작성
- 투자 권유 표현 금지
- relation label 영어는 자연스러운 한국어 표현으로 바꿔서 쓸 것
- 핵심 이벤트/포인트만 요약할 것

질문:
{query}

질문 유형:
{intent}

핵심 관계:
{relations_text}
""".strip()

    messages = [
        SystemMessage(content="너는 금융 뉴스 기반 리서치 브리프를 간결하게 작성하는 분석 보조 AI다."),
        HumanMessage(content=prompt),
    ]

    try:
        response = llm.invoke(messages)
        return response.content.strip()
    except Exception:
        return ""
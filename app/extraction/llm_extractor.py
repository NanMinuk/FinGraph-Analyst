import json
from typing import Dict, Any, List

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from app.extraction.relation_normalizer import normalize_relations

load_dotenv()


def build_batch_extraction_prompt(docs: List[Dict[str, Any]]) -> str:
    doc_blocks = []

    for i, doc in enumerate(docs):
        title = doc.get("title", "")
        text = doc.get("text", "")
        doc_id = doc.get("doc_id", f"doc_{i}")

        doc_blocks.append(
            f"""[문서 {i+1}]
doc_id: {doc_id}
title: {title}
text: {text}
"""
        )

    joined_docs = "\n\n".join(doc_blocks)

    return f"""
다음 금융 뉴스 chunk들에서 회사/이벤트 관계를 추출하라.

반드시 아래 JSON 형식으로만 답하라.
설명 문장, 코드블록, 추가 텍스트는 절대 쓰지 마라.

JSON 형식:
{{
  "entities": [
    {{"name": "...", "type": "Company or Event"}}
  ],
  "relations": [
    {{
      "head": "...",
      "head_type": "Company",
      "relation": "benefits_from | reports | supplies | invests_in | regulatory_risk",
      "tail": "...",
      "tail_type": "Event",
      "evidence": "...",
      "confidence": 0.0,
      "document_id": "..."
    }}
  ]
}}

규칙:
- head는 회사명이어야 한다.
- tail은 가능한 한 구체적인 이벤트명이어야 한다.
- evidence는 문서 안의 근거 문장 또는 핵심 구절이어야 한다.
- confidence는 0~1 사이 숫자여야 한다.
- 관계가 없으면 빈 리스트를 반환하라.
- 각 relation에는 반드시 해당 relation이 나온 문서의 document_id를 넣어라.

문서들:
{joined_docs}
""".strip()


def extract_entities_and_relations_llm_batch(docs: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not docs:
        return {"entities": [], "relations": []}

    llm = ChatOpenAI(model="gpt-4.1-mini", temperature=0)

    messages = [
        SystemMessage(content="너는 금융 뉴스에서 회사와 이벤트 관계를 구조화하는 정보추출기다."),
        HumanMessage(content=build_batch_extraction_prompt(docs)),
    ]

    try:
        response = llm.invoke(messages)
        content = response.content.strip()
        parsed = json.loads(content)

        entities = parsed.get("entities", [])
        relations = parsed.get("relations", [])
        relations = normalize_relations(relations)

        return {
            "entities": entities,
            "relations": relations,
        }

    except Exception as e:
        return {
            "entities": [],
            "relations": [],
            "error": str(e),
        }
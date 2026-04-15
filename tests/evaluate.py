"""
FinGraph Analyst — 성능 평가 스크립트
=====================================
두 가지를 측정합니다:

  1. 관계 추출 정확도 (Precision)
     LLM-as-Judge 또는 수동으로 각 관계가 사실인지 평가합니다.

  2. Retrieval Hit Rate
     검색된 문서가 질문과 관련 있는지 평가합니다.

사용법:
  # 자동 평가 (LLM-as-Judge) — 기본값
  python -m tests.evaluate --query "삼성전자 최근 투자포인트" --company 삼성전자

  # 수동 평가
  python -m tests.evaluate --query "삼성전자 최근 투자포인트" --company 삼성전자 --mode manual
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

import requests
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from pydantic import BaseModel, Field

load_dotenv()

API_BASE = os.getenv("API_URL", "http://localhost:8000")
JUDGE_MODEL = os.getenv("JUDGE_MODEL", "gpt-4.1-mini")
RESULTS_DIR = Path("tests/results")
RESULTS_DIR.mkdir(parents=True, exist_ok=True)


# ─────────────────────────────────────────────
# 유틸
# ─────────────────────────────────────────────

def call_analyze(query: str, company: str | None) -> dict:
    resp = requests.post(
        f"{API_BASE}/analyze",
        json={"query": query, "company": company},
        timeout=180,
    )
    resp.raise_for_status()
    return resp.json()


def relation_label(rel: dict) -> str:
    return f"{rel.get('head')} --[{rel.get('relation')}]--> {rel.get('tail')}"


def ask_yn(prompt: str) -> bool:
    while True:
        ans = input(f"{prompt} [y/n]: ").strip().lower()
        if ans in ("y", "n"):
            return ans == "y"


# ─────────────────────────────────────────────
# LLM-as-Judge
# ─────────────────────────────────────────────

class JudgeResult(BaseModel):
    is_correct: bool = Field(..., description="관계가 근거 문장에 비추어 사실이면 true")
    reason: str = Field(..., description="판단 근거 한 문장")


def judge_relation(rel: dict) -> JudgeResult:
    llm = ChatOpenAI(model=JUDGE_MODEL, temperature=0)
    structured = llm.with_structured_output(JudgeResult)

    prompt = f"""
다음은 금융 뉴스에서 추출한 기업-이벤트 관계다.
근거 문장을 바탕으로 이 관계가 사실인지 판단하라.

관계:
  head(기업): {rel.get('head')}
  relation:   {rel.get('relation')}
  tail(이벤트): {rel.get('tail')}

근거 문장:
  {rel.get('evidence', '없음')}

판단 기준:
- 근거 문장이 head 기업과 tail 이벤트 사이의 해당 관계를 실제로 뒷받침하면 true
- 근거 문장이 모호하거나, 관계와 무관하거나, tail이 너무 추상적이면 false
- head 기업이 근거 문장에 명시적으로 등장하지 않으면 false
""".strip()

    try:
        return structured.invoke([
            SystemMessage(content="너는 금융 뉴스 관계 추출 결과를 검증하는 평가자다."),
            HumanMessage(content=prompt),
        ])
    except Exception as e:
        return JudgeResult(is_correct=False, reason=f"판단 실패: {e}")


def judge_document(doc: dict, query: str) -> JudgeResult:
    llm = ChatOpenAI(model=JUDGE_MODEL, temperature=0)
    structured = llm.with_structured_output(JudgeResult)

    title = doc.get("metadata", {}).get("title") or doc.get("title", "")
    snippet = (doc.get("page_content") or doc.get("text", ""))[:400]

    prompt = f"""
다음 뉴스 문서가 아래 질문에 답하는 데 관련이 있는지 판단하라.

질문: {query}

문서 제목: {title}
문서 내용 (일부):
{snippet}

판단 기준:
- 문서가 질문의 기업/주제와 직접 관련된 정보를 포함하면 true
- 질문과 무관한 일반 뉴스이거나 기업명만 언급되는 수준이면 false
""".strip()

    try:
        return structured.invoke([
            SystemMessage(content="너는 검색 결과의 관련성을 평가하는 평가자다."),
            HumanMessage(content=prompt),
        ])
    except Exception as e:
        return JudgeResult(is_correct=False, reason=f"판단 실패: {e}")


# ─────────────────────────────────────────────
# 1. 관계 추출 정확도 평가
# ─────────────────────────────────────────────

def evaluate_extraction(relations: list[dict], mode: str) -> dict:
    if not relations:
        print("\n[관계 추출 결과 없음 — 평가 건너뜀]")
        return {"total": 0, "correct": 0, "precision": None, "details": []}

    print("\n" + "=" * 60)
    print(f"  [1] 관계 추출 정확도 평가  (mode={mode})")
    print("=" * 60)

    correct = 0
    total = len(relations)
    details = []

    for i, rel in enumerate(relations, 1):
        label = relation_label(rel)
        evidence = rel.get("evidence", "없음")[:120]
        confidence = rel.get("confidence", "?")

        print(f"\n[{i}/{total}] {label}")
        print(f"  근거: {evidence}")
        print(f"  신뢰도: {confidence}")

        if mode == "auto":
            result = judge_relation(rel)
            verdict = result.is_correct
            print(f"  Judge: {'✓ 정확' if verdict else '✗ 부정확'} — {result.reason}")
        else:
            verdict = ask_yn("  → 이 관계가 맞나요?")

        if verdict:
            correct += 1

        details.append({
            "relation": label,
            "evidence": evidence,
            "confidence": confidence,
            "correct": verdict,
        })

    precision = correct / total if total > 0 else 0.0
    print(f"\n▶ 관계 추출 Precision: {correct}/{total} = {precision:.1%}")
    return {"total": total, "correct": correct, "precision": round(precision, 4), "details": details}


# ─────────────────────────────────────────────
# 2. Retrieval Hit Rate 평가
# ─────────────────────────────────────────────

def evaluate_retrieval(documents: list[dict], query: str, mode: str) -> dict:
    if not documents:
        print("\n[검색된 문서 없음 — 평가 건너뜀]")
        return {"total": 0, "relevant": 0, "hit_rate": None, "details": []}

    print("\n" + "=" * 60)
    print(f"  [2] Retrieval Hit Rate 평가  (mode={mode})")
    print(f"  질문: {query}")
    print("=" * 60)

    relevant = 0
    total = len(documents)
    details = []

    for i, doc in enumerate(documents, 1):
        title = doc.get("metadata", {}).get("title") or doc.get("title", "제목 없음")
        snippet = (doc.get("page_content") or doc.get("text", ""))[:200]

        print(f"\n[{i}/{total}] {title}")
        print(f"  {snippet}...")

        if mode == "auto":
            result = judge_document(doc, query)
            verdict = result.is_correct
            print(f"  Judge: {'✓ 관련' if verdict else '✗ 무관'} — {result.reason}")
        else:
            verdict = ask_yn("  → 이 문서가 질문과 관련 있나요?")

        if verdict:
            relevant += 1

        details.append({"title": title, "relevant": verdict})

    hit_rate = relevant / total if total > 0 else 0.0
    print(f"\n▶ Retrieval Hit Rate: {relevant}/{total} = {hit_rate:.1%}")
    return {"total": total, "relevant": relevant, "hit_rate": round(hit_rate, 4), "details": details}


# ─────────────────────────────────────────────
# 결과 저장 + 출력
# ─────────────────────────────────────────────

def save_results(results: dict, query: str, company: str | None, mode: str):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    company_slug = (company or "unknown").replace(" ", "_")
    path = RESULTS_DIR / f"eval_{company_slug}_{timestamp}.json"

    payload = {
        "timestamp": timestamp,
        "mode": mode,
        "query": query,
        "company": company,
        **results,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n결과 저장: {path}")
    return payload


def print_summary(results: dict):
    print("\n" + "=" * 60)
    print("  최종 평가 요약")
    print("=" * 60)

    ext = results.get("extraction", {})
    ret = results.get("retrieval", {})

    if ext.get("precision") is not None:
        print(f"  관계 추출 Precision : {ext['correct']}/{ext['total']} = {ext['precision']:.1%}")
    else:
        print("  관계 추출 Precision : 평가 없음")

    if ret.get("hit_rate") is not None:
        print(f"  Retrieval Hit Rate  : {ret['relevant']}/{ret['total']} = {ret['hit_rate']:.1%}")
    else:
        print("  Retrieval Hit Rate  : 평가 없음")

    print("=" * 60)


# ─────────────────────────────────────────────
# main
# ─────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="FinGraph Analyst 성능 평가")
    parser.add_argument("--query",   required=True, help="분석 질문 (예: '삼성전자 최근 투자포인트')")
    parser.add_argument("--company", default=None,  help="기업명 (예: 삼성전자)")
    parser.add_argument("--mode",    default="auto", choices=["auto", "manual"],
                        help="auto: LLM-as-Judge (기본값) / manual: 직접 평가")
    parser.add_argument("--skip-extraction", action="store_true", help="관계 추출 평가 건너뜀")
    parser.add_argument("--skip-retrieval",  action="store_true", help="Retrieval 평가 건너뜀")
    args = parser.parse_args()

    print(f"\n분석 요청 중... (query={args.query}, company={args.company}, mode={args.mode})")

    try:
        data = call_analyze(args.query, args.company)
    except Exception as e:
        print(f"API 호출 실패: {e}")
        sys.exit(1)

    relations = data.get("relations", [])
    documents = data.get("documents", [])

    print(f"추출된 관계 수: {len(relations)}")
    print(f"검색된 문서 수: {len(documents)}")

    results = {}

    if not args.skip_extraction:
        results["extraction"] = evaluate_extraction(relations, args.mode)

    if not args.skip_retrieval:
        results["retrieval"] = evaluate_retrieval(documents, args.query, args.mode)

    print_summary(results)
    save_results(results, args.query, args.company, args.mode)


if __name__ == "__main__":
    main()

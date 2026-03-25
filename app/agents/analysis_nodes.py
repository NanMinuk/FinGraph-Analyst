from typing import Any, Dict

from app.agents.analysis_supervisor import (
    make_analysis_plan,
    replan_after_retrieval,
    replan_after_extraction,
)
from app.agents.langchain_analysis_agent import build_structured_brief_from_report
from app.agents.state import AppState
from app.tools.extraction_tools import extract_relations_from_chunks_tool
from app.tools.graph_tools import build_hybrid_graph_context_tool, selective_upsert_graph_tool
from app.tools.reporting_tools import generate_investment_brief_tool
from app.tools.retrieval_tools import retrieve_relevant_chunks_tool


def _default_supervisor_explanation() -> Dict[str, Any]:
    return {
        "initial_plan_reason": "",
        "replan_reason": "",
        "extraction_replan_reason": "",
        "final_upsert_decision": "",
        "final_brief_mode": "",
    }


def _default_retrieval_out() -> Dict[str, Any]:
    return {"summary": {"retrieved_count": 0}, "documents": []}


def _default_extraction_out() -> Dict[str, Any]:
    return {
        "summary": {
            "entities": 0,
            "relations": 0,
            "document_groups": 0,
            "llm_used": False,
            "fallback_used": False,
        },
        "entities": [],
        "relations": [],
        "document_relation_map": {},
    }


def _default_graph_out(company) -> Dict[str, Any]:
    return {
        "summary": {
            "company": company,
            "current_count": 0,
            "persistent_count": 0,
            "hybrid_count": 0,
        },
        "persistent_graph_relations": [],
        "hybrid_graph_relations": [],
    }


def _default_brief_out(intent) -> Dict[str, Any]:
    return {
        "summary": {
            "intent": intent,
            "documents": 0,
            "relations": 0,
            "hybrid_relations": 0,
            "key_points": 0,
            "risk_points": 0,
            "relation_points": 0,
        },
        "key_points": [],
        "risk_points": [],
        "relation_points": [],
        "report": "",
    }


def _default_upsert_out() -> Dict[str, Any]:
    return {
        "summary": {
            "selected_relations": 0,
            "inserted_relations": 0,
            "skipped": True,
        },
        "selected_graph_relations": [],
    }


# ---------------------------------------------------------------------------
# 노드 0: plan_node  —  supervisor가 실행 계획을 수립
# ---------------------------------------------------------------------------

def plan_node(state: AppState) -> AppState:
    logs = state.get("logs", [])
    supervisor_explanation = state.get("supervisor_explanation") or _default_supervisor_explanation()

    plan = make_analysis_plan(state)
    supervisor_explanation["initial_plan_reason"] = plan["reason"]

    logs.append(
        f"plan_node: plan created "
        f"(intent={plan['intent']}, retrieval_k={plan['retrieval_k']}, "
        f"retrieval_company={plan['retrieval_company']}, "
        f"use_selective_upsert={plan['use_selective_upsert']})"
    )
    logs.append(f"plan_node: reason = {plan['reason']}")

    return {
        **state,
        "plan": plan,
        "replan_count": 0,
        "extraction_replan_count": 0,
        "supervisor_explanation": supervisor_explanation,
        "logs": logs,
    }


# ---------------------------------------------------------------------------
# 노드 1: retrieval_node  —  청크 검색
# ---------------------------------------------------------------------------

def retrieval_node(state: AppState) -> AppState:
    query = state.get("query", "")
    intent = state.get("intent", "company_analysis")
    plan = state.get("plan", {})
    logs = state.get("logs", [])

    if not plan.get("use_retrieval", True):
        logs.append("retrieval_node: skipped by plan")
        return {**state, "documents": [], "logs": logs}

    retrieval_query = query
    if intent == "risk_analysis":
        retrieval_query = f"{query} 리스크 위험 악재 부담"

    retrieval_out = retrieve_relevant_chunks_tool(
        query=retrieval_query,
        company=plan.get("retrieval_company"),
        k=plan.get("retrieval_k", 5),
    )

    logs.append(
        f"retrieval_node: done "
        f"(retrieved_count={retrieval_out['summary']['retrieved_count']}, "
        f"company={plan.get('retrieval_company')})"
    )

    return {
        **state,
        "documents": retrieval_out["documents"],
        "logs": logs,
    }


# ---------------------------------------------------------------------------
# 노드 1-R: replan_retrieval_node  —  검색 결과 0일 때 plan 재수립
# ---------------------------------------------------------------------------

def replan_retrieval_node(state: AppState) -> AppState:
    logs = state.get("logs", [])
    supervisor_explanation = state.get("supervisor_explanation") or _default_supervisor_explanation()
    plan = state.get("plan", {})
    replan_count = state.get("replan_count", 0)

    new_plan = replan_after_retrieval(
        state=state,
        previous_plan=plan,
        retrieved_count=0,
    )
    supervisor_explanation["replan_reason"] = new_plan["reason"]

    logs.append(
        f"replan_retrieval_node: replanned "
        f"(retrieval_k={new_plan['retrieval_k']}, "
        f"retrieval_company={new_plan['retrieval_company']}, "
        f"use_selective_upsert={new_plan['use_selective_upsert']})"
    )
    logs.append(f"replan_retrieval_node: reason = {new_plan['reason']}")

    return {
        **state,
        "plan": new_plan,
        "replan_count": replan_count + 1,
        "supervisor_explanation": supervisor_explanation,
        "logs": logs,
    }


# ---------------------------------------------------------------------------
# 노드 2: extraction_node  —  relation / entity 추출
# ---------------------------------------------------------------------------

def extraction_node(state: AppState) -> AppState:
    plan = state.get("plan", {})
    documents = state.get("documents", [])
    extraction_replan_count = state.get("extraction_replan_count", 0)
    logs = state.get("logs", [])

    if not plan.get("use_extraction", True) or not documents:
        logs.append("extraction_node: skipped (plan flag or no documents)")
        extraction_out = _default_extraction_out()
        return {
            **state,
            "entities": extraction_out["entities"],
            "relations": extraction_out["relations"],
            "document_relation_map": extraction_out["document_relation_map"],
            "logs": logs,
        }

    # extraction replan 이후에는 confidence_threshold를 낮춤
    threshold = 0.5 if extraction_replan_count > 0 else 0.65

    extraction_out = extract_relations_from_chunks_tool(
        documents=documents,
        confidence_threshold=threshold,
    )

    suffix = f", threshold={threshold}" if extraction_replan_count > 0 else ""
    logs.append(
        f"extraction_node: done "
        f"(entities={extraction_out['summary']['entities']}, "
        f"relations={extraction_out['summary']['relations']}{suffix})"
    )

    return {
        **state,
        "entities": extraction_out["entities"],
        "relations": extraction_out["relations"],
        "document_relation_map": extraction_out["document_relation_map"],
        "logs": logs,
    }


# ---------------------------------------------------------------------------
# 노드 2-R: replan_extraction_node  —  relation 0일 때 plan 재수립
# ---------------------------------------------------------------------------

def replan_extraction_node(state: AppState) -> AppState:
    logs = state.get("logs", [])
    supervisor_explanation = state.get("supervisor_explanation") or _default_supervisor_explanation()
    plan = state.get("plan", {})
    extraction_replan_count = state.get("extraction_replan_count", 0)

    new_plan = replan_after_extraction(
        state=state,
        previous_plan=plan,
        relation_count=0,
    )
    supervisor_explanation["extraction_replan_reason"] = new_plan["reason"]

    logs.append(
        f"replan_extraction_node: replanned "
        f"(retrieval_k={new_plan['retrieval_k']}, "
        f"retrieval_company={new_plan['retrieval_company']}, "
        f"use_selective_upsert={new_plan['use_selective_upsert']})"
    )
    logs.append(f"replan_extraction_node: reason = {new_plan['reason']}")

    return {
        **state,
        "plan": new_plan,
        "extraction_replan_count": extraction_replan_count + 1,
        "supervisor_explanation": supervisor_explanation,
        "logs": logs,
    }


# ---------------------------------------------------------------------------
# 노드 3: upsert_node  —  고신뢰 relation을 그래프 DB에 selective upsert
# ---------------------------------------------------------------------------

def upsert_node(state: AppState) -> AppState:
    plan = state.get("plan", {})
    relations = state.get("relations", [])
    logs = state.get("logs", [])
    supervisor_explanation = state.get("supervisor_explanation") or _default_supervisor_explanation()

    if not plan.get("use_selective_upsert", True) or not relations:
        supervisor_explanation["final_upsert_decision"] = (
            f"use_selective_upsert={plan.get('use_selective_upsert', True)}, skipped"
        )
        logs.append("upsert_node: skipped by plan or empty relations")
        upsert_out = _default_upsert_out()
    else:
        upsert_out = selective_upsert_graph_tool(
            relations=relations,
            min_confidence=0.8,
        )
        supervisor_explanation["final_upsert_decision"] = (
            f"use_selective_upsert=True, "
            f"selected={upsert_out['summary']['selected_relations']}, "
            f"inserted={upsert_out['summary']['inserted_relations']}"
        )
        logs.append(
            f"upsert_node: done "
            f"(selected={upsert_out['summary']['selected_relations']}, "
            f"inserted={upsert_out['summary']['inserted_relations']}, "
            f"skipped={upsert_out['summary']['skipped']})"
        )

    return {
        **state,
        "selected_graph_relations": upsert_out["selected_graph_relations"],
        "graph_upsert_result": upsert_out["summary"],
        "supervisor_explanation": supervisor_explanation,
        "logs": logs,
    }


# ---------------------------------------------------------------------------
# 노드 4: graph_node  —  hybrid graph context 구성
# ---------------------------------------------------------------------------

def graph_node(state: AppState) -> AppState:
    plan = state.get("plan", {})
    company = state.get("company")
    relations = state.get("relations", [])
    logs = state.get("logs", [])

    if not plan.get("use_hybrid_graph", True) or not relations:
        logs.append("graph_node: skipped by plan or empty relations")
        graph_out = _default_graph_out(company)
    else:
        graph_out = build_hybrid_graph_context_tool(
            current_relations=relations,
            company=company,
        )
        logs.append(
            f"graph_node: hybrid graph built "
            f"(current={graph_out['summary']['current_count']}, "
            f"persistent={graph_out['summary']['persistent_count']}, "
            f"hybrid={graph_out['summary']['hybrid_count']})"
        )

    return {
        **state,
        "persistent_graph_relations": graph_out["persistent_graph_relations"],
        "hybrid_graph_relations": graph_out["hybrid_graph_relations"],
        "logs": logs,
    }


# ---------------------------------------------------------------------------
# 노드 5: brief_node  —  투자 brief 생성
# ---------------------------------------------------------------------------

def brief_node(state: AppState) -> AppState:
    plan = state.get("plan", {})
    query = state.get("query", "")
    intent = state.get("intent", "company_analysis")
    documents = state.get("documents", [])
    entities = state.get("entities", [])
    relations = state.get("relations", [])
    document_relation_map = state.get("document_relation_map", {})
    hybrid_graph_relations = state.get("hybrid_graph_relations", [])
    persistent_graph_relations = state.get("persistent_graph_relations", [])
    supervisor_explanation = state.get("supervisor_explanation") or _default_supervisor_explanation()
    logs = state.get("logs", [])

    if not plan.get("use_brief_generation", True) or not documents:
        logs.append("brief_node: skipped by plan or empty documents")
        brief_out = _default_brief_out(intent)
    else:
        brief_out = generate_investment_brief_tool(
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
        supervisor_explanation["final_brief_mode"] = brief_out["summary"].get("brief_mode", "")
        logs.append(
            f"brief_node: generated "
            f"(mode={brief_out['summary']['brief_mode']}, "
            f"key_points={brief_out['summary']['key_points']}, "
            f"risk_points={brief_out['summary']['risk_points']}, "
            f"relation_points={brief_out['summary']['relation_points']})"
        )

    return {
        **state,
        "raw_report": brief_out["report"],
        "supervisor_explanation": supervisor_explanation,
        "logs": logs,
    }


# ---------------------------------------------------------------------------
# 노드 6: structured_node  —  최종 structured output 생성
# ---------------------------------------------------------------------------

def structured_node(state: AppState) -> AppState:
    query = state.get("query", "")
    company = state.get("company")
    intent = state.get("intent", "company_analysis")
    raw_report = state.get("raw_report", "")
    logs = state.get("logs", [])

    structured_out = build_structured_brief_from_report(
        query=query,
        company=company,
        intent=intent,
        report=raw_report,
    )
    logs.append("structured_node: done")

    return {
        **state,
        "intent": structured_out["intent"],
        "key_points": structured_out["key_points"],
        "risk_points": structured_out["risk_points"],
        "relation_points": structured_out["relation_points"],
        "report": structured_out["final_answer"],
        "logs": logs,
    }

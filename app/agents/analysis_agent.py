from typing import Dict, Any

from app.tools.retrieval_tools import retrieve_relevant_chunks_tool
from app.tools.extraction_tools import extract_relations_from_chunks_tool
from app.tools.graph_tools import build_hybrid_graph_context_tool, selective_upsert_graph_tool
from app.tools.reporting_tools import generate_investment_brief_tool
from app.agents.langchain_analysis_agent import build_structured_brief_from_report
from app.agents.analysis_supervisor import make_analysis_plan, replan_after_retrieval, replan_after_extraction

def run_analysis_agent(state: Dict[str, Any]) -> Dict[str, Any]:
    query = state.get("query", "")
    company = state.get("company")
    intent = state.get("intent", "company_analysis")
    logs = state.get("logs", [])
    upsert_out = {
        "summary": {
            "selected_relations": 0,
            "inserted_relations": 0,
            "skipped": True,
        },
        "selected_graph_relations": [],
    }
    supervisor_explanation = {
        "initial_plan_reason": "",
        "replan_reason": "",
        "extraction_replan_reason": "",
        "final_upsert_decision": "",
        "final_brief_mode": "",
    }

    # 0) supervisor plan
    plan = make_analysis_plan(state)
    supervisor_explanation["initial_plan_reason"] = plan["reason"]

    logs.append(
        f"analysis_agent: plan created "
        f"(intent={plan['intent']}, retrieval_k={plan['retrieval_k']}, "
        f"retrieval_company={plan['retrieval_company']}, "
        f"use_selective_upsert={plan['use_selective_upsert']})"
    )
    logs.append(f"analysis_agent: plan reason = {plan['reason']}")

    retrieval_out = {"summary": {"retrieved_count": 0}, "documents": []}
    extraction_out = {
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
    graph_out = {
        "summary": {
            "company": company,
            "current_count": 0,
            "persistent_count": 0,
            "hybrid_count": 0,
        },
        "persistent_graph_relations": [],
        "hybrid_graph_relations": [],
    }
    brief_out = {
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

    # -------------------------------------------------
    # 1) retrieval
    # -------------------------------------------------

    if plan["use_retrieval"]:
        retrieval_query = query
        if intent == "risk_analysis":
            retrieval_query = f"{query} 리스크 위험 악재 부담"

        retrieval_out = retrieve_relevant_chunks_tool(
            query=retrieval_query,
            company=plan["retrieval_company"],
            k=plan["retrieval_k"],
        )
        logs.append(
            f"analysis_agent: retrieval done "
            f"(retrieved_count={retrieval_out['summary']['retrieved_count']}, "
            f"company={plan['retrieval_company']})"
        )

        # re-plan retrieval
        if retrieval_out["summary"]["retrieved_count"] == 0:
            new_plan = replan_after_retrieval(
                state=state,
                previous_plan=plan,
                retrieved_count=retrieval_out["summary"]["retrieved_count"],
            )
            supervisor_explanation["replan_reason"] = new_plan["reason"]
            logs.append(
                f"analysis_agent: replanned "
                f"(retrieval_k={new_plan['retrieval_k']}, "
                f"retrieval_company={new_plan['retrieval_company']}, "
                f"use_selective_upsert={new_plan['use_selective_upsert']})"
            )
            logs.append(f"analysis_agent: replan reason = {new_plan['reason']}")

            retrieval_out = retrieve_relevant_chunks_tool(
                query=retrieval_query,
                company=new_plan["retrieval_company"],
                k=new_plan["retrieval_k"],
            )
            logs.append(
                f"analysis_agent: retrieval after replan "
                f"(retrieved_count={retrieval_out['summary']['retrieved_count']}, "
                f"company={new_plan['retrieval_company']})"
            )

            plan = new_plan
    # -------------------------------------------------
    # 2) extraction
    # -------------------------------------------------
    if plan["use_extraction"] and retrieval_out["documents"]:
        extraction_out = extract_relations_from_chunks_tool(
            documents=retrieval_out["documents"],
            confidence_threshold=0.65,
        )
        logs.append(
            f"analysis_agent: extraction done "
            f"(entities={extraction_out['summary']['entities']}, "
            f"relations={extraction_out['summary']['relations']})"
        )

        # relation 0이면 supervisor re-plan
        if extraction_out["summary"]["relations"] == 0:
            new_plan = replan_after_extraction(
                state=state,
                previous_plan=plan,
                relation_count=extraction_out["summary"]["relations"],
            )
            supervisor_explanation["extraction_replan_reason"] = new_plan["reason"]
            logs.append(
                f"analysis_agent: replanned after extraction "
                f"(retrieval_k={new_plan['retrieval_k']}, "
                f"retrieval_company={new_plan['retrieval_company']}, "
                f"use_selective_upsert={new_plan['use_selective_upsert']})"
            )
            logs.append(f"analysis_agent: extraction replan reason = {new_plan['reason']}")

            retrieval_out = retrieve_relevant_chunks_tool(
                query=retrieval_query,
                company=new_plan["retrieval_company"],
                k=new_plan["retrieval_k"],
            )
            logs.append(
                f"analysis_agent: retrieval after extraction replan "
                f"(retrieved_count={retrieval_out['summary']['retrieved_count']}, "
                f"company={new_plan['retrieval_company']})"
            )

            extraction_out = extract_relations_from_chunks_tool(
                documents=retrieval_out["documents"],
                confidence_threshold=0.5,
            )
            logs.append(
                f"analysis_agent: extraction after replan "
                f"(entities={extraction_out['summary']['entities']}, "
                f"relations={extraction_out['summary']['relations']}, threshold=0.5)"
            )

            plan = new_plan

        # -------------------------------------------------
        # 2.5) selective upsert
        # -------------------------------------------------
        if plan.get("use_selective_upsert", True) and extraction_out["relations"]:
            upsert_out = selective_upsert_graph_tool(
                relations=extraction_out["relations"],
                min_confidence=0.8,
            )
            logs.append(
                f"analysis_agent: selective upsert done "
                f"(selected={upsert_out['summary']['selected_relations']}, "
                f"inserted={upsert_out['summary']['inserted_relations']}, "
                f"skipped={upsert_out['summary']['skipped']})"
            )
            supervisor_explanation["final_upsert_decision"] = (
                f"use_selective_upsert={plan.get('use_selective_upsert', True)}, "
                f"selected={upsert_out['summary']['selected_relations']}, "
                f"inserted={upsert_out['summary']['inserted_relations']}"
            )
        else:
            supervisor_explanation["final_upsert_decision"] = (
                f"use_selective_upsert={plan.get('use_selective_upsert', True)}, skipped"
            )
            logs.append("analysis_agent: selective upsert skipped by plan or empty relations")
        # -------------------------------------------------
        # 3) hybrid graph
        # -------------------------------------------------
        if plan["use_hybrid_graph"]:
            graph_out = build_hybrid_graph_context_tool(
                current_relations=extraction_out["relations"],
                company=company,
            )
            logs.append(
                f"analysis_agent: hybrid graph built "
                f"(current={graph_out['summary']['current_count']}, "
                f"persistent={graph_out['summary']['persistent_count']}, "
                f"hybrid={graph_out['summary']['hybrid_count']})"
            )

        # -------------------------------------------------
        # 4) brief generation
        # -------------------------------------------------
        if plan["use_brief_generation"]:
            brief_out = generate_investment_brief_tool(
                query=query,
                intent=intent,
                documents=retrieval_out["documents"],
                entities=extraction_out["entities"],
                relations=extraction_out["relations"],
                document_relation_map=extraction_out["document_relation_map"],
                hybrid_graph_relations=graph_out["hybrid_graph_relations"],
                persistent_graph_relations=graph_out["persistent_graph_relations"],
                supervisor_explanation= supervisor_explanation
            )
            supervisor_explanation["final_brief_mode"] = brief_out["summary"].get("brief_mode", "")
            logs.append(
                f"analysis_agent: brief generated "
                f"(mode={brief_out['summary']['brief_mode']}), "
                f"(key_points={brief_out['summary']['key_points']}, "
                f"risk_points={brief_out['summary']['risk_points']}, "
                f"relation_points={brief_out['summary']['relation_points']})"
            )

    # -------------------------------------------------
    # 5) structured output
    # -------------------------------------------------
    structured_out = build_structured_brief_from_report(
        query=query,
        company=company,
        intent=intent,
        report=brief_out["report"],
    )
    logs.append("analysis_agent: structured output generated")

    return {
        **state,
        "intent": structured_out["intent"],
        "documents": retrieval_out["documents"],
        "entities": extraction_out["entities"],
        "relations": extraction_out["relations"],
        "document_relation_map": extraction_out["document_relation_map"],
        "selected_graph_relations": upsert_out["selected_graph_relations"],
        "graph_upsert_result": upsert_out["summary"],
        "persistent_graph_relations": graph_out["persistent_graph_relations"],
        "hybrid_graph_relations": graph_out["hybrid_graph_relations"],
        "key_points": structured_out["key_points"],
        "risk_points": structured_out["risk_points"],
        "relation_points": structured_out["relation_points"],
        "report": structured_out["final_answer"],
        "raw_report": brief_out["report"],
        "supervisor_explanation": supervisor_explanation, 
        "logs": logs,
    }
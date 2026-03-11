from typing import Dict, Any, List
from app.services.point_generators import(
    generate_key_points_from_graph_relations,
    generate_relation_points_from_graph_relations,
    generate_risk_points_from_graph_relations
)

from app.services.report_service import (
    build_report,
    deduplicate_relations_for_report,
)
from app.reporting.summary_polisher import polish_brief_summary
from app.services.report_service import build_relation_summary_text


def generate_investment_brief_tool(
    query: str,
    intent: str,
    documents: List[Dict[str, Any]],
    entities: List[Dict[str, Any]],
    relations: List[Dict[str, Any]],
    document_relation_map: Dict[str, List[Dict[str, Any]]],
    hybrid_graph_relations: List[Dict[str, Any]],
    persistent_graph_relations: List[Dict[str, Any]],
    supervisor_explanation : Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    
    supervisor_explanation = supervisor_explanation or {}
    brief_mode = "hybrid"

    if relations:
        source_relations = hybrid_graph_relations or relations
        brief_mode = "hybrid"
    elif persistent_graph_relations:
        source_relations = persistent_graph_relations
        brief_mode = "persistent_only"
    else:
        source_relations = []
        brief_mode = "empty"

    key_points = generate_key_points_from_graph_relations(source_relations)
    risk_points = generate_risk_points_from_graph_relations(source_relations)
    relation_points = generate_relation_points_from_graph_relations(source_relations)

    report = build_report(
        user_query=query,
        docs=documents,
        entities=entities,
        relations=relations,
        intent=intent,
        document_relation_map=document_relation_map,
        persistent_graph_relations=persistent_graph_relations,
    )
    if brief_mode == "persistent_only":
        report = report.replace(
            "[한 줄 요약]\n관련 문서는 있으나 구조화 가능한 핵심 관계는 제한적입니다.",
            "[한 줄 요약]\n이번 질문에서 새로 포착된 관계는 제한적이지만, 기존 그래프에 축적된 관계를 바탕으로 핵심 포인트를 보완했습니다."
        )
        report = report.replace(
            "[이번 질문에서 포착된 관계]\n- 이번 질문에서 새로 포착된 관계가 없습니다.",
            "[이번 질문에서 포착된 관계]\n- 이번 질문에서는 새로 포착된 관계가 제한적이었습니다."
        )
    if brief_mode == "empty":
        report = report.replace(
            "[한 줄 요약]\n관련 문서는 있으나 구조화 가능한 핵심 관계는 제한적입니다.",
            "[한 줄 요약]\n현재 검색 및 그래프 기준으로 유의미한 관계를 충분히 확보하지 못했습니다."
        )
    filtered_relations = deduplicate_relations_for_report(relations)
    relations_text = build_relation_summary_text(filtered_relations)

    polished_summary = polish_brief_summary(
        query=query,
        intent=intent,
        relations_text=relations_text,
    )

    if polished_summary:
        default_summaries = [
            "최근 문서 기반으로 기업과 이벤트 간 핵심 연결관계를 정리했습니다.",
            "최근 문서와 관계 추출 결과를 바탕으로 잠재적 리스크 요인을 점검했습니다.",
            "관련 종목과 이벤트 간 연결관계를 중심으로 요약했습니다.",
            "관련 문서는 있으나 구조화 가능한 핵심 관계는 제한적입니다.",
            "관련 문서는 있으나 구조화 가능한 리스크 신호는 제한적입니다.",
            "관련 문서는 있으나 연결관계를 충분히 식별하지 못했습니다.",
        ]
        for s in default_summaries:
            report = report.replace(f"[한 줄 요약]\n{s}", f"[한 줄 요약]\n{polished_summary}")

    # 그래프 결과 섹션 추가
    graph_relations = deduplicate_relations_for_report(source_relations)[:5]
    if graph_relations:
        extra_lines = []
        extra_lines.append("")
        extra_lines.append("[그래프 조회 결과]")
        for rel in graph_relations:
            extra_lines.append(
                f"- {rel.get('head', 'Unknown')} --{rel.get('relation', 'related_to')}--> {rel.get('tail', 'Unknown')}"
            )
            extra_lines.append(f"  · confidence: {rel.get('confidence', 'N/A')}")
            extra_lines.append(f"  · source_type: {rel.get('source_type', 'current')}")
            extra_lines.append(f"  · document_id: {rel.get('document_id', 'N/A')}")
            evidence = rel.get("evidence", "")
            if evidence:
                extra_lines.append(f"  · evidence: {evidence}")

        report += "\n" + "\n".join(extra_lines)

    if intent == "company_analysis" and key_points:
        report += "\n\n[핵심 투자 포인트]\n" + "\n".join(f"- {p}" for p in key_points)

    if intent == "risk_analysis" and risk_points:
        report += "\n\n[리스크 포인트]\n" + "\n".join(f"- {p}" for p in risk_points)

    if intent == "relation_query" and relation_points:
        report += "\n\n[연결 종목 요약]\n" + "\n".join(f"- {p}" for p in relation_points)

    report += "\n\n[분석 경로]"

    initial_reason = supervisor_explanation.get("initial_plan_reason", "")
    replan_reason = supervisor_explanation.get("replan_reason", "")
    extraction_replan_reason = supervisor_explanation.get("extraction_replan_reason", "")
    upsert_decision = supervisor_explanation.get("final_upsert_decision", "")
    brief_mode = supervisor_explanation.get("final_brief_mode", "")

    if initial_reason:
        report += f"\n- 초기 계획: {initial_reason}"
    if replan_reason:
        report += f"\n- 재계획(검색): {replan_reason}"
    if extraction_replan_reason:
        report += f"\n- 재계획(추출): {extraction_replan_reason}"
    if upsert_decision:
        report += f"\n- 저장 결정: {upsert_decision}"
    if brief_mode:
        report += f"\n- 브리프 모드: {brief_mode}"

    if not any([initial_reason, replan_reason, extraction_replan_reason, upsert_decision, brief_mode]):
        report += "\n- 별도 기록된 분석 경로가 없습니다."

    summary = {
        "intent": intent,
        "documents": len(documents),
        "relations": len(relations),
        "hybrid_relations": len(hybrid_graph_relations),
        "key_points": len(key_points),
        "risk_points": len(risk_points),
        "relation_points": len(relation_points),
        "brief_mode" : brief_mode,
    }

    return {
        "summary": summary,
        "key_points": key_points,
        "risk_points": risk_points,
        "relation_points": relation_points,
        "report": report,
    }
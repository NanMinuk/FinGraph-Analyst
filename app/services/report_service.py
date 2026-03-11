from typing import List, Dict, Any


def deduplicate_docs_for_report(docs):
    seen = set()
    unique_docs = []

    for doc in docs:
        key = (
            doc.get("title"),
            doc.get("date"),
        )
        if key not in seen:
            seen.add(key)
            unique_docs.append(doc)

    return unique_docs


def deduplicate_relations_for_report(relations):
    seen = set()
    unique_relations = []

    for rel in relations:
        key = (
            rel.get("head"),
            rel.get("relation"),
            rel.get("tail"),
        )
        if key not in seen:
            seen.add(key)
            unique_relations.append(rel)

    return unique_relations


def build_report(
    user_query: str,
    docs: List[Dict[str, Any]],
    entities: List[Dict[str, Any]],
    relations: List[Dict[str, Any]],
    intent: str | None = None,
    document_relation_map : Dict[str,List[Dict[str,Any]]] | None = None,
    persistent_graph_relations: List[Dict[str, Any]] | None = None,
) -> str:
    persistent_graph_relations = persistent_graph_relations or []

    filtered_docs = deduplicate_docs_for_report(docs)
    filtered_relations = deduplicate_relations_for_report(relations)
    document_relation_map = document_relation_map or {}

    lines = []
    lines.append("FinGraph Analyst Brief")
    lines.append("=" * 30)
    lines.append(f"질문: {user_query}")
    lines.append("")

    # 1. 한 줄 요약
    lines.append("[한 줄 요약]")
    if intent == "risk_analysis":
        if filtered_relations:
            lines.append("최근 문서와 관계 추출 결과를 바탕으로 잠재적 리스크 요인을 점검했습니다.")
        else:
            lines.append("관련 문서는 있으나 구조화 가능한 리스크 신호는 제한적입니다.")
    elif intent == "relation_query":
        if filtered_relations:
            lines.append("관련 종목과 이벤트 간 연결관계를 중심으로 요약했습니다.")
        else:
            lines.append("관련 문서는 있으나 연결관계를 충분히 식별하지 못했습니다.")
    else:
        if filtered_relations:
            lines.append("최근 문서 기반으로 기업과 이벤트 간 핵심 연결관계를 정리했습니다.")
        else:
            lines.append("관련 문서는 있으나 구조화 가능한 핵심 관계는 제한적입니다.")

    # 2. 핵심 관계 요약
    lines.append("")
    lines.append("[핵심 관계]")
    if filtered_relations:
        for rel in filtered_relations[:5]:
            label_ko = relation_label_ko(rel["relation"])
            lines.append(
                f"- {rel['head']} → {label_ko} → {rel['tail']}"
            )
    else:
        lines.append("- 식별된 핵심 관계가 없습니다.")
    
    current_relations = deduplicate_relations_for_report(relations)
    reused_relations = deduplicate_relations_for_report(persistent_graph_relations)

    lines.append("")
    lines.append("[이번 질문에서 포착된 관계]")
    if current_relations:
        for rel in current_relations[:5]:
            label_ko = relation_label_ko(rel["relation"])
            lines.append(
                f"-{rel['head']} -> {label_ko} -> {rel['tail']}"
            )
    else:
        lines.append("- 이번 질문에서 새로 포착된 관계가 없습니다.")
    lines.append("")
    lines.append("[기존 그래프에서 재사용된 관계]")

    if reused_relations:
        for rel in reused_relations[:5]:
            label_ko = relation_label_ko(rel["relation"])
            lines.append(
                f"-{rel['head']} -> {label_ko} -> {rel['tail']}"
            )
    else:
        lines.append("- 기존 그래프에서 재사용된 관계가 없습니다.")

    # 3. 참고 문서
    lines.append("")
    lines.append("[참고 문서]")
    if filtered_docs:
        for doc in filtered_docs[:5]:
            lines.append(f"- {doc['title']} ({doc['date']})")
    else:
        lines.append("- 참고 문서가 없습니다.")

    lines.append("")
    lines.append("[문서별 근거]")

    if filtered_docs and document_relation_map:
        for doc in filtered_docs[:5]:
            doc_id = doc.get("doc_id")
            title = doc.get("title", "Untitled")
            doc_rels = document_relation_map.get(doc_id, [])

            if not doc_rels:
                continue

            lines.append(f"- {title}")
            for rel in doc_rels[:5]:
                label_ko = relation_label_ko(rel.get("relation", ""))
                evidence = rel.get("evidence", "").strip()
                lines.append(
                    f"  · {rel.get('head', 'Unknown')} → {label_ko} → {rel.get('tail', 'Unknown')}"
                )
                if evidence:
                    lines.append(f"    - 근거: {evidence}")
    else:
        lines.append("- 문서별 근거가 없습니다.")

    return "\n".join(lines)

def relation_label_ko(relation: str) -> str:
    mapping = {
        "benefits_from": "수혜 가능성",
        "reports": "실적/공시 관련",
        "supplies": "공급 관련",
        "invests_in": "투자 확대",
        "regulatory_risk": "규제 리스크",
    }
    return mapping.get(relation, relation)

def build_relation_summary_text(relations):
    lines = []
    for rel in relations[:5]:
        label_ko = relation_label_ko(rel.get("relation", ""))
        lines.append(
            f"{rel.get('head', 'Unknown')} → {label_ko} → {rel.get('tail', 'Unknown')}"
        )
    return "\n".join(lines)
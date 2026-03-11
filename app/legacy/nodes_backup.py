from app.agents.state import AppState
from app.ingestion.pipeline import ingest_news_urls
from app.retrieval.retriever import retrieve_documents
from app.extraction.relation_extractor import extract_entities_and_relations
from app.services.report_service import build_report, build_relation_summary_text
from app.reporting.summary_polisher import polish_brief_summary
from app.graph.neo4j_client import Neo4jClient
from app.graph.queries import UPSERT_RELATION_QUERY, GET_COMPANY_RELATIONS_QUERY, GET_RELEVANT_GRAPH_RELATIONS_QUERY
from app.retrieval.chunker import split_documents_to_chunks
from app.extraction.llm_extractor import (
    extract_entities_and_relations_llm_batch, 
)
from app.extraction.relation_postprocessor import postprocess_relations, select_relations_for_graph_upsert, filter_persistent_relations_for_hybrid
from app.agents.analysis_agent import run_analysis_agent
from app.agents.intent_classifier import classify_intent_llm, classify_intent_rule_based

def aggregate_relations_by_company(relations):
    company_map = {}

    for rel in relations:
        head = rel.get("head", "Unknown")
        company_map.setdefault(head, []).append(rel)

    aggregated = {}

    for company, rels in company_map.items():
        seen = set()
        unique_rels = []

        # confidence 높은 순으로 정렬
        sorted_rels = sorted(
            rels,
            key=lambda x: float(x.get("confidence", 0.0)),
            reverse=True,
        )

        for rel in sorted_rels:
            key = (
                rel.get("relation"),
                rel.get("tail"),
            )
            if key not in seen:
                seen.add(key)
                unique_rels.append(rel)

        aggregated[company] = unique_rels[:3]

    return aggregated


def rerank_hybrid_relations(current_relations, persistent_relations):
    merged = {}

    def relation_key(rel):
        return (
            rel.get("head"),
            rel.get("relation"),
            rel.get("tail"),
        )

    # 1) current 먼저 적재
    for rel in current_relations:
        key = relation_key(rel)
        c_conf = float(rel.get("confidence", 0.0))

        if key not in merged:
            merged[key] = {
                **rel,
                "current_confidence": c_conf,
                "persistent_confidence": 0.0,
                "hybrid_score": c_conf,
                "source_type": "current",
            }
        else:
            merged[key]["current_confidence"] = max(
                merged[key].get("current_confidence", 0.0),
                c_conf,
            )
            merged[key]["hybrid_score"] = max(
                merged[key].get("hybrid_score", 0.0),
                merged[key]["current_confidence"],
            )

    # 2) persistent 추가
    for rel in persistent_relations:
        key = relation_key(rel)
        p_conf = float(rel.get("confidence", 0.0))

        if key not in merged:
            merged[key] = {
                **rel,
                "current_confidence": 0.0,
                "persistent_confidence": p_conf,
                "hybrid_score": p_conf,
                "source_type": "persistent",
            }
        else:
            # 이미 current가 있거나, persistent 중복일 수 있음
            merged[key]["persistent_confidence"] = max(
                merged[key].get("persistent_confidence", 0.0),
                p_conf,
            )

            c_conf = merged[key].get("current_confidence", 0.0)
            p_conf = merged[key].get("persistent_confidence", 0.0)

            if c_conf > 0.0:
                # current + persistent 둘 다 존재할 때만 hybrid
                merged[key]["hybrid_score"] = c_conf * 0.7 + p_conf * 0.3 + 0.1
                merged[key]["source_type"] = "hybrid"
            else:
                # persistent 내부 중복이면 그냥 persistent 유지
                merged[key]["hybrid_score"] = p_conf
                merged[key]["source_type"] = "persistent"

    ranked = sorted(
        merged.values(),
        key=lambda x: x.get("hybrid_score", 0.0),
        reverse=True,
    )
    return ranked

def deduplicate_relation_records(relations):
    seen = set()
    unique = []

    for rel in relations :
        key = (
            rel.get("head"),
            rel.get("relation"),
            rel.get("tail"),
            rel.get("document_id"),
        )
        if key not in seen:
            seen.add(key)
            unique.append(rel)
        return unique

def ingest_news_node(state: AppState) -> AppState:
    urls = state.get("urls", [])
    logs = state.get("logs", [])

    if not urls:
        logs.append("ingest_news_node: skipped (no urls)")
        return {
            **state,
            "ingestion_summary": {
                "total": 0,
                "ingested": 0,
                "skipped_existing_doc_id": 0,
                "skipped_existing_content_hash": 0,
                "error": 0,
            },
            "ingestion_results": [],
            "logs": logs,
        }

    out = ingest_news_urls(urls)

    logs.append(
        f"ingest_news_node: total={out['summary']['total']}, ingested={out['summary']['ingested']}, skipped_doc_id={out['summary']['skipped_existing_doc_id']}, skipped_hash={out['summary']['skipped_existing_content_hash']}, error={out['summary']['error']}"
    )

    return {
        **state,
        "ingestion_summary": out["summary"],
        "ingestion_results": out["results"],
        "logs": logs,
    }

def generate_key_points_from_graph_relations(graph_relations):
    key_points = []

    for rel in graph_relations:
        head = rel.get("head", "해당 기업")
        relation = rel.get("relation", "")
        tail = rel.get("tail", "이벤트")

        if relation == "benefits_from":
            key_points.append(
                f"{head}는 {tail} 이벤트와 연결되어 긍정적 모멘텀 가능성이 있습니다."
            )
        elif relation == "reports":
            key_points.append(
                f"{head}는 {tail} 관련 이벤트와 연결되어 실적 흐름을 점검할 필요가 있습니다."
            )
        elif relation == "supplies":
            key_points.append(
                f"{head}는 {tail} 관련 공급 이슈와 연결되어 공급 확대 흐름을 확인할 필요가 있습니다."
            )
        elif relation == "invests_in":
            key_points.append(
                f"{head}는 {tail} 관련 투자 움직임과 연결되어 중장기 성장 포인트로 볼 수 있습니다."
            )
        else:
            key_points.append(
                f"{head}는 {tail} 이벤트와 연결되어 추가 확인이 필요한 상태입니다."
            )

    # 중복 제거
    unique_key_points = list(dict.fromkeys(key_points))
    return unique_key_points[:3]

def generate_key_points_node(state: AppState) -> AppState:
    # graph_relations = sort_relations_by_confidence(
    #     deduplicate_relations_for_report(state.get("graph_relations", []))
    # )
    source_relations = state.get("hybrid_graph_relations", []) or state.get("relations", [])

    #key_points = generate_key_points_from_graph_relations(graph_relations)
    key_points = generate_key_points_from_graph_relations(
        sort_relations_by_confidence(
            deduplicate_relations_for_report(source_relations)
        )
    )
    logs = state.get("logs", [])
    logs.append(f"generate_key_points_node: {len(key_points)} key points generated")

    return {
        **state,
        "key_points": key_points,
        "logs": logs
    }

def generate_risk_points_from_graph_relations(graph_relations):
    risk_points = []

    for rel in graph_relations:
        head = rel.get("head", "해당 기업")
        relation = rel.get("relation", "")
        tail = rel.get("tail", "이벤트")

        if relation == "regulatory_risk":
            risk_points.append(
                f"{head}는 {tail}와 관련된 규제 리스크를 점검할 필요가 있습니다."
            )
        elif relation == "reports":
            risk_points.append(
                f"{head}는 {tail} 관련 이벤트와 연결되어 실적 변동 가능성을 확인할 필요가 있습니다."
            )
        elif relation == "supplies":
            risk_points.append(
                f"{head}는 {tail} 관련 공급 이슈와 연결되어 공급 차질 또는 변동성을 점검할 필요가 있습니다."
            )
        elif relation == "benefits_from":
            risk_points.append(
                f"{head}는 {tail} 이벤트와 연결되어 있으나 기대가 과도하게 반영되었는지 점검할 필요가 있습니다."
            )
        elif relation == "invests_in":
            risk_points.append(
                f"{head}는 {tail} 관련 투자 확대와 연결되어 있으므로 투자 집행 부담과 성과 가시성을 함께 확인할 필요가 있습니다."
            )
        else:
            risk_points.append(
                f"{head}는 {tail} 이벤트와 연결되어 있어 추가적인 리스크 점검이 필요합니다."
            )

    unique_risk_points = list(dict.fromkeys(risk_points))
    return unique_risk_points[:3]

def generate_relation_points_from_graph_relations(graph_relations):
    relation_points = []

    for rel in graph_relations:
        head = rel.get("head", "해당 종목")
        relation = rel.get("relation", "")
        tail = rel.get("tail", "이벤트")

        if relation == "invests_in":
            relation_points.append(
                f"{head}는 {tail} 관련 투자 확대와 연결된 종목으로 식별되었습니다."
            )
        elif relation == "supplies":
            relation_points.append(
                f"{head}는 {tail} 관련 공급 확대 흐름과 연결된 종목으로 식별되었습니다."
            )
        elif relation == "benefits_from":
            relation_points.append(
                f"{head}는 {tail} 이벤트 수혜 가능성과 연결된 종목으로 식별되었습니다."
            )
        elif relation == "reports":
            relation_points.append(
                f"{head}는 {tail} 관련 실적 흐름과 연결된 종목으로 식별되었습니다."
            )
        else:
            relation_points.append(
                f"{head}는 {tail} 이벤트와 연결된 종목으로 확인되었습니다."
            )

    unique_relation_points = list(dict.fromkeys(relation_points))
    return unique_relation_points[:5]

def generate_risk_points_node(state: AppState) -> AppState:
    # graph_relations = sort_relations_by_confidence(
    #     deduplicate_relations_for_report(state.get("graph_relations", []))
    # )
    source_relations = state.get("hybrid_graph_relations", []) or state.get("relations", [])
    # risk_points = generate_risk_points_from_graph_relations(graph_relations)
    risk_points = generate_risk_points_from_graph_relations(
        sort_relations_by_confidence(
            deduplicate_relations_for_report(source_relations)
        )
    )
    logs = state.get("logs", [])
    logs.append(f"generate_risk_points_node: {len(risk_points)} risk points generated")

    return {
        **state,
        "risk_points": risk_points,
        "logs": logs
    }

def deduplicate_relations(relations):
    seen = set()
    unique_relations = []

    for rel in relations:
        key = (
            rel.get("head"),
            rel.get("relation"),
            rel.get("tail"),
            rel.get("document_id"),
        )
        if key not in seen:
            seen.add(key)
            unique_relations.append(rel)

    return unique_relations

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

def sort_relations_by_confidence(relations):
    return sorted(
        relations,
        key=lambda x: x.get("confidence", 0.0),
        reverse=True
    )

def retrieve_node(state: AppState) -> AppState:
    docs = retrieve_documents(
        query=state["query"],
        company=state.get("company")
    )
    return {
        **state,
        "documents": docs,
        "logs": state.get("logs", []) + [f"retrieve_node: {len(docs)} chunks retrieved"]
    }

def extract_node(state: AppState) -> AppState:
    documents = state.get("documents", [])
    logs = state.get("logs", [])

    llm_out = extract_entities_and_relations_llm_batch(documents)

    entities = llm_out.get("entities", [])
    relations = llm_out.get("relations", [])

    fallback_used = 0

    if not entities and not relations:
        entities, relations = extract_entities_and_relations(documents)
        fallback_used = 1

    relations = postprocess_relations(relations, confidence_threshold=0.65)
    document_relation_map = group_relations_by_document(relations)

    logs.append(
        f"extract_node: {len(documents)} retrieved chunks, {len(entities)} entities, {len(relations)} relations extracted (batch_llm={'success' if not fallback_used else 'failed'}, fallback={fallback_used})"
    )

    return {
        **state,
        "entities": entities,
        "relations": relations,
        "document_relation_map" : document_relation_map, 
        "logs": logs,
    }

def report_node(state: AppState) -> AppState:
    report = build_report(
        state["query"],
        state.get("documents", []),
        state.get("entities", []),
        state.get("relations", []),
        state.get("intent"),
        state.get("document_relation_map", {}),
        state.get("persistent_graph_relations", []),
    )

    filtered_relations_for_summary = deduplicate_relations_for_report(state.get("relations", []))
    relations_text = build_relation_summary_text(filtered_relations_for_summary)

    polished_summary = polish_brief_summary(
        query=state["query"],
        intent=state.get("intent", ""),
        relations_text=relations_text,
    )

    if polished_summary:
        report = report.replace(
            "[한 줄 요약]\n최근 문서 기반으로 기업과 이벤트 간 핵심 연결관계를 정리했습니다.",
            f"[한 줄 요약]\n{polished_summary}"
        )
        report = report.replace(
            "[한 줄 요약]\n최근 문서와 관계 추출 결과를 바탕으로 잠재적 리스크 요인을 점검했습니다.",
            f"[한 줄 요약]\n{polished_summary}"
        )
        report = report.replace(
            "[한 줄 요약]\n관련 종목과 이벤트 간 연결관계를 중심으로 요약했습니다.",
            f"[한 줄 요약]\n{polished_summary}"
        )

    key_points = state.get("key_points", [])
    if key_points:
        key_lines = []
        key_lines.append("")
        key_lines.append("[핵심 투자 포인트]")
        for point in key_points:
            key_lines.append(f"- {point}")
        report += "\n" + "\n".join(key_lines)

    # graph_relations = sort_relations_by_confidence(
    #     deduplicate_relations_for_report(state.get("graph_relations", []))
    # )
    graph_relations = sort_relations_by_confidence(
        deduplicate_relations_for_report(state.get("relations", []))
    )

    top_k = 3
    graph_relations = graph_relations[:top_k]

    if graph_relations:
        extra_lines = []
        extra_lines.append("")
        extra_lines.append("[그래프 조회 결과]")
        for rel in graph_relations:
            extra_lines.append(f"- {rel['head']} --{rel['relation']}--> {rel['tail']}")
            extra_lines.append(f"  · confidence: {rel['confidence']}")
            extra_lines.append(f"  · document_id: {rel.get('document_id', 'N/A')}")
            extra_lines.append(f"  · evidence: {rel['evidence']}")
        report += "\n" + "\n".join(extra_lines)
    
    logs = state.get("logs", [])
    logs.append(
        f"report_node: report generated ({len(state.get('graph_relations', []))} raw, {len(graph_relations)} top-k report relations)"
    )
    return {
        **state,
        "report": report,
        "logs": logs
    }

def route_node(state: AppState) -> AppState:
    query = state.get("query", "")
    logs = state.get("logs", [])

    try:
        intent = classify_intent_llm(query)
        logs.append(f"route_node: intent={intent} (llm)")
    except Exception as e:
        intent = classify_intent_rule_based(query)
        logs.append(f"route_node: intent={intent} (rule_fallback, error={str(e)})")

    return {
        **state,
        "intent": intent,
        "logs": logs,
    }

def risk_report_node(state: AppState) -> AppState:
    docs = state.get("documents", [])
    relations = state.get("relations", [])
    graph_relations = sort_relations_by_confidence(
        deduplicate_relations_for_report(state.get("graph_relations", []))
    )

    top_k = 3
    graph_relations = graph_relations[:top_k]
    risk_points = state.get("risk_points", [])

    lines = []
    lines.append(f"질문: {state['query']}")
    lines.append("")

    lines.append("[리스크 분석 문서]")
    if docs:
        for doc in docs:
            lines.append(f"- {doc['title']} ({doc['date']})")
    else:
        lines.append("- 관련 문서를 찾지 못했습니다.")

    filtered_relations = deduplicate_relations_for_report(relations)

    lines.append("")
    lines.append("[리스크 관련 관계]")
    if filtered_relations:
        for rel in filtered_relations:
            lines.append(
                f"- {rel['head']} --{rel['relation']}--> {rel['tail']} "
                f"(evidence: {rel['evidence']})"
            )
    else:
        lines.append("- 리스크 관련 관계를 찾지 못했습니다.")

    lines.append("")
    lines.append("[리스크 포인트]")
    if risk_points:
        for point in risk_points:
            lines.append(f"- {point}")
    else:
        lines.append("- 현재 식별된 주요 리스크 포인트가 없습니다.")

    lines.append("")
    lines.append("[그래프 조회 결과]")
    if graph_relations:
        for rel in graph_relations:
            lines.append(f"- {rel['head']} --{rel['relation']}--> {rel['tail']}")
            lines.append(f"  · confidence: {rel['confidence']}")
            lines.append(f"  · document_id: {rel.get('document_id', 'N/A')}")
            lines.append(f"  · evidence: {rel['evidence']}")
    else:
        lines.append("- 그래프에서 조회된 관계가 없습니다.")

    lines.append("")
    lines.append("[리스크 요약]")
    if filtered_relations:
        lines.append("검색된 문서와 그래프 관계를 바탕으로 잠재적 리스크 포인트를 정리했습니다.")
    else:
        lines.append("명시적인 리스크 관계는 없지만, 후속 문서 확인이 필요합니다.")

    logs = state.get("logs", [])
    logs.append(
        f"risk_report_node: risk report generated ({len(state.get('graph_relations', []))} raw, {len(graph_relations)} top-k report relations)"
    )

    return {
        **state,
        "report": "\n".join(lines),
        "logs": logs
    }

def relation_report_node(state: AppState) -> AppState:
    docs = state.get("documents", [])
    relations = state.get("relations", [])
    relation_points = state.get("relation_points", [])

    source_relations = state.get("graph_relations", [])
    if not source_relations:
        source_relations = state.get("relations", [])

    graph_relations = sort_relations_by_confidence(
        deduplicate_relations_for_report(source_relations)
    )
    top_k = 5
    graph_relations = graph_relations[:top_k]

    company_map = aggregate_relations_by_company(graph_relations)

    lines = []
    lines.append(f"질문: {state['query']}")
    lines.append("")

    lines.append("[연결관계 문서]")
    if docs:
        seen_docs = set()
        for doc in docs:
            key = (doc.get("title"), doc.get("date"))
            if key not in seen_docs:
                seen_docs.add(key)
                lines.append(f"- {doc['title']} ({doc['date']})")
    else:
        lines.append("- 관련 문서를 찾지 못했습니다.")

    filtered_relations = deduplicate_relations_for_report(relations)

    lines.append("")
    lines.append("[연결관계]")
    if filtered_relations:
        for rel in filtered_relations:
            lines.append(
                f"- {rel['head']} --{rel['relation']}--> {rel['tail']} "
                f"(evidence: {rel['evidence']})"
            )
    else:
        lines.append("- 식별된 연결관계가 없습니다.")

    lines.append("")
    lines.append("[연결 종목 요약]")
    if relation_points:
        for point in relation_points:
            lines.append(f"- {point}")
    else:
        lines.append("- 연결 종목 요약을 생성하지 못했습니다.")

    lines.append("")
    lines.append("[종목별 연결관계]")
    if company_map:
        for company, rels in company_map.items():
            lines.append(f"- {company}")
            for rel in rels:
                lines.append(
                    f"  · {rel['relation']} -> {rel['tail']} "
                    f"(confidence: {rel['confidence']}, document_id: {rel.get('document_id', 'N/A')})"
                )
    else:
        lines.append("- 식별된 연결관계가 없습니다.")

    lines.append("")
    lines.append("[관계 요약]")
    if company_map:
        lines.append(f"총 {len(company_map)}개 종목에서 연결관계를 식별했습니다.")
    else:
        lines.append("관련 문서는 찾았지만 연결관계를 충분히 식별하지 못했습니다.")

    logs = state.get("logs", []) + [
        f"relation_report_node: relation report generated ({len(state.get('graph_relations', []))} raw, {len(graph_relations)} top-k report relations)"
    ]

    return {
        **state,
        "report": "\n".join(lines),
        "logs": logs
    }

def upsert_graph_node(state: AppState) -> AppState:
    relations = state.get("relations", [])
    inserted = 0
    logs = state.get("logs", [])

    try:
        client = Neo4jClient()
        try:
            for rel in relations:
                client.run_query(UPSERT_RELATION_QUERY, rel)
                inserted += 1
        finally:
            client.close()

        logs.append(f"upsert_graph_node: {inserted} relations inserted")

        return {
            **state,
            "graph_upsert_result": {"inserted_relations": inserted},
            "logs": logs
        }

    except Exception as e:
        logs.append(f"upsert_graph_node error: {str(e)}")
        return {
            **state,
            "graph_upsert_result": {
                "inserted_relations": inserted,
                "error": str(e)
            },
            "logs": logs
        }
    
def selective_upsert_graph_node(state: AppState) -> AppState:
    relations = state.get("relations", [])
    logs = state.get("logs", [])

    selected_relations = select_relations_for_graph_upsert(
        relations,
        min_confidence=0.8,
    )

    inserted = 0

    if not selected_relations:
        logs.append("selective_upsert_graph_node: skipped (no eligible relations)")
        return {
            **state,
            "selected_graph_relations": [],
            "graph_upsert_result": {
                "inserted_relations": 0,
                "selected_relations": 0,
            },
            "logs": logs,
        }

    try:
        client = Neo4jClient()
        try:
            for rel in selected_relations:
                client.run_query(UPSERT_RELATION_QUERY, rel)
                inserted += 1
        finally:
            client.close()

        logs.append(
            f"selective_upsert_graph_node: selected={len(selected_relations)}, inserted={inserted}"
        )

        return {
            **state,
            "selected_graph_relations": selected_relations,
            "graph_upsert_result": {
                "inserted_relations": inserted,
                "selected_relations": len(selected_relations),
            },
            "logs": logs,
        }

    except Exception as e:
        logs.append(f"selective_upsert_graph_node error: {str(e)}")
        return {
            **state,
            "selected_graph_relations": selected_relations,
            "graph_upsert_result": {
                "inserted_relations": inserted,
                "selected_relations": len(selected_relations),
                "error": str(e),
            },
            "logs": logs,
        }

def build_hybrid_graph_context_node(state: AppState) -> AppState:
    company = state.get("company")
    current_relations = state.get("relations", [])
    logs = state.get("logs", [])

    persistent_relations = []

    if company:
        try:
            client = Neo4jClient()
            try:
                persistent_relations = client.run_query(
                    GET_RELEVANT_GRAPH_RELATIONS_QUERY,
                    {"company": company}
                )
            finally:
                client.close()
        except Exception as e:
            logs.append(f"build_hybrid_graph_context_node error: {str(e)}")

    persistent_relations = filter_persistent_relations_for_hybrid(
        persistent_relations,
        min_confidence=0.75,
    )
    hybrid_relations = rerank_hybrid_relations(
        current_relations,persistent_relations
    )

    logs.append(
        f"build_hybrid_graph_context_node: current={len(current_relations)}, persistent={len(persistent_relations)}, hybrid={len(hybrid_relations)}"
    )

    return {
        **state,
        "persistent_graph_relations": persistent_relations,
        "hybrid_graph_relations": hybrid_relations,
        "logs": logs,
    }

def fetch_graph_relations_node(state: AppState) -> AppState:
    company = state.get("company")
    logs = state.get("logs", [])

    if not company:
        logs.append("fetch_graph_relations_node: skipped (no company)")
        return {
            **state,
            "graph_relations": [],
            "logs": logs
        }

    try:
        client = Neo4jClient()
        try:
            graph_relations = client.run_query(
                GET_COMPANY_RELATIONS_QUERY,
                {"company": company}
            )
        finally:
            client.close()

        logs.append(
            f"fetch_graph_relations_node: {len(graph_relations)} graph relations fetched"
        )

        return {
            **state,
            "graph_relations": graph_relations,
            "logs": logs
        }

    except Exception as e:
        logs.append(f"fetch_graph_relations_node error: {str(e)}")
        return {
            **state,
            "graph_relations": [],
            "logs": logs
        }
    
def generate_relation_points_node(state: AppState) -> AppState:
    
    # source_relations = state.get("graph_relations", [])
    source_relations = state.get("hybrid_graph_relations", []) or state.get("relations", [])
    # if not source_relations:
    #     source_relations = state.get("relations", [])

    relation_points = generate_relation_points_from_graph_relations(
        sort_relations_by_confidence(
            deduplicate_relations_for_report(source_relations)
        )
    )

    logs = state.get("logs", []) + [
        f"generate_relation_points_node: {len(relation_points)} relation points generated"
    ]

    return {
        "relation_points": relation_points,
        "logs": logs
    }

def analysis_agent_node(state:AppState) -> AppState:
    return run_analysis_agent(state)

def group_relations_by_document(relations):
    grouped = {}

    for rel in relations:
        doc_id = rel.get("document_id", "unknown_doc")
        grouped.setdefault(doc_id, []).append(rel)

    return grouped
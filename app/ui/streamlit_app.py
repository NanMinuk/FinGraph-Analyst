import streamlit as st
import requests
import pandas as pd
import tempfile
import streamlit.components.v1 as components
from pyvis.network import Network

API_URL = "http://127.0.0.1:8000/analyze"


def deduplicate_graph_relations_for_vis(graph_relations):
    seen = set()
    unique_relations = []

    for rel in graph_relations:
        key = (
            rel.get("head"),
            rel.get("relation"),
            rel.get("tail"),
            rel.get("source_type"),
        )
        if key not in seen:
            seen.add(key)
            unique_relations.append(rel)

    return unique_relations


def relation_label_ko(relation: str) -> str:
    mapping = {
        "benefits_from": "수혜 가능성",
        "reports": "실적/공시 관련",
        "regulatory_risk": "규제 리스크",
        "supplies": "공급 관련",
        "invests_in": "투자 확대",
    }
    return mapping.get(relation, relation)


def source_type_ko(source_type: str) -> str:
    mapping = {
        "current": "이번 질문",
        "persistent": "기존 그래프",
        "hybrid": "혼합",
    }
    return mapping.get(source_type, source_type or "N/A")


def render_graph_legend():
    st.markdown("### 그래프 범례")

    legend_html = """
    <div style="padding: 12px; border: 1px solid #ddd; border-radius: 8px; background-color: #fafafa;">
        <div style="margin-bottom: 8px;"><b>노드</b></div>
        <div style="margin-bottom: 6px;">
            <span style="display:inline-block; width:14px; height:14px; background:#8ecae6; border-radius:50%; margin-right:8px;"></span>
            Company
        </div>
        <div style="margin-bottom: 12px;">
            <span style="display:inline-block; width:14px; height:14px; background:#ffe08a; border-radius:50%; margin-right:8px;"></span>
            Event
        </div>
    </div>
    """
    st.markdown(legend_html, unsafe_allow_html=True)


def render_relation_graph(graph_relations, focus_current_only=True):
    if not graph_relations:
        return None

    graph_relations = deduplicate_graph_relations_for_vis(graph_relations)

    if focus_current_only:
        graph_relations = [
            r for r in graph_relations
            if r.get("source_type", "current") in ("current", "hybrid")
        ]

    if not graph_relations:
        return None

    net = Network(height="560px", width="100%", directed=True, bgcolor="#ffffff", font_color="#222222")

    relation_colors = {
        "benefits_from": "#2ca02c",
        "reports": "#1f77b4",
        "regulatory_risk": "#d62728",
        "supplies": "#ff7f0e",
        "invests_in": "#9467bd",
    }

    node_colors = {
        "Company": "#8ecae6",
        "Event": "#ffe08a",
        "Unknown": "#d9d9d9",
    }

    added_nodes = set()

    current_nodes = set()
    for rel in graph_relations:
        if rel.get("source_type", "current") in ("current", "hybrid"):
            current_nodes.add(rel.get("head", "Unknown"))
            current_nodes.add(rel.get("tail", "Unknown"))

    def get_node_style(node_name, node_type):
        base_color = node_colors.get(node_type, node_colors["Unknown"])
        if node_name in current_nodes:
            return {
                "color": base_color,
                "size": 28,
                "borderWidth": 2,
            }
        return {
            "color": base_color,
            "size": 18,
            "borderWidth": 1,
        }

    for rel in graph_relations:
        head = rel.get("head", "Unknown")
        tail = rel.get("tail", "Unknown")
        relation = rel.get("relation", "related_to")
        confidence = rel.get("confidence", "N/A")
        document_id = rel.get("document_id", "N/A")
        evidence = rel.get("evidence", "N/A")
        source_type = rel.get("source_type", "current")

        head_type = rel.get("head_type", "Company")
        tail_type = rel.get("tail_type", "Event")

        if head not in added_nodes:
            style = get_node_style(head, head_type)
            net.add_node(
                head,
                label=head,
                title=f"Node: {head}<br>type: {head_type}",
                color=style["color"],
                size=style["size"],
                borderWidth=style["borderWidth"],
            )
            added_nodes.add(head)

        if tail not in added_nodes:
            style = get_node_style(tail, tail_type)
            net.add_node(
                tail,
                label=tail,
                title=f"Node: {tail}<br>type: {tail_type}",
                color=style["color"],
                size=style["size"],
                borderWidth=style["borderWidth"],
            )
            added_nodes.add(tail)

        label_ko = relation_label_ko(relation)
        edge_tooltip = (
            f"relation: {label_ko}<br>"
            f"source_type: {source_type_ko(source_type)}<br>"
            f"confidence: {confidence}<br>"
            f"document_id: {document_id}<br>"
            f"evidence: {evidence}"
        )

        base_color = relation_colors.get(relation, "#888888")

        if source_type == "current":
            edge_color = base_color
            edge_width = 4
            edge_dashes = False
        elif source_type == "hybrid":
            edge_color = base_color
            edge_width = 3
            edge_dashes = False
        else:
            edge_color = "rgba(160,160,160,0.45)"
            edge_width = 1.5
            edge_dashes = True

        net.add_edge(
            head,
            tail,
            label=label_ko,
            title=edge_tooltip,
            arrows="to",
            color=edge_color,
            width=edge_width,
            dashes=edge_dashes,
        )

    net.set_options("""
    var options = {
      "nodes": {
        "font": {
          "size": 20,
          "face": "arial"
        },
        "shadow": true
      },
      "edges": {
        "smooth": {
          "type": "dynamic"
        },
        "font": {
          "size": 14,
          "align": "middle"
        },
        "shadow": false
      },
      "physics": {
        "enabled": true,
        "barnesHut": {
          "gravitationalConstant": -3000,
          "springLength": 180,
          "springConstant": 0.03
        },
        "stabilization": {
          "iterations": 250
        }
      },
      "interaction": {
        "hover": true,
        "navigationButtons": true,
        "keyboard": true
      }
    }
    """)

    with tempfile.NamedTemporaryFile(delete=False, suffix=".html") as tmp_file:
        net.save_graph(tmp_file.name)
        return tmp_file.name


st.set_page_config(page_title="FinGraph Analyst", layout="wide")
st.title("FinGraph Analyst")
st.caption("금융 문서 관계 추출 기반 GraphRAG 투자 리서치 에이전트")

st.markdown("### 예시 질문")

col1, col2, col3 = st.columns(3)

if "preset_query" not in st.session_state:
    st.session_state.preset_query = "삼성전자 최근 투자포인트 정리해줘"
if "preset_company" not in st.session_state:
    st.session_state.preset_company = "삼성전자"
if "analysis_result" not in st.session_state:
    st.session_state.analysis_result = None

with col1:
    if st.button("삼성전자 투자포인트"):
        st.session_state.preset_query = "삼성전자 최근 투자포인트 정리해줘"
        st.session_state.preset_company = "삼성전자"

with col2:
    if st.button("SK하이닉스 리스크"):
        st.session_state.preset_query = "SK하이닉스 최근 리스크 요인 알려줘"
        st.session_state.preset_company = "SK하이닉스"

query = st.text_input("질문", value=st.session_state.preset_query)
company = st.text_input("회사명 (없으면 비워두기)", value=st.session_state.preset_company)

if st.button("분석 실행"):
    payload = {
        "query": query,
        "company": company if company.strip() else None
    }

    with st.spinner("분석 중..."):
        resp = requests.post(API_URL, json=payload, timeout=120)
        st.session_state.analysis_result = resp.json()

data = st.session_state.analysis_result

if data:
    intent = data.get("intent")
    documents = data.get("documents", [])
    entities = data.get("entities", [])
    relations = data.get("relations", [])
    document_relation_map = data.get("document_relation_map", {})

    selected_graph_relations = data.get("selected_graph_relations", [])
    persistent_graph_relations = data.get("persistent_graph_relations", [])
    hybrid_graph_relations = data.get("hybrid_graph_relations", [])
    graph_upsert_result = data.get("graph_upsert_result", {})

    key_points = data.get("key_points", [])
    risk_points = data.get("risk_points", [])
    relation_points = data.get("relation_points", [])

    report_text = data.get("report", "")
    raw_report = data.get("raw_report", "")
    supervisor_explanation = data.get("supervisor_explanation", {})
    logs = data.get("logs", [])

    tabs = st.tabs(["요약", "리포트", "그래프", "문서", "로그"])

    with tabs[0]:
        st.subheader("분석 결과")
        st.write(f"**Intent:** {intent}")

        c1, c2, c3 = st.columns(3)
        c1.metric("검색 문서 수", len(documents))
        c2.metric("추출 관계 수", len(relations))
        c3.metric("하이브리드 관계 수", len(hybrid_graph_relations))

        st.markdown("### 핵심 요약")
        if intent == "company_analysis":
            for point in key_points or ["없음"]:
                st.write(f"- {point}")
        elif intent == "risk_analysis":
            for point in risk_points or ["없음"]:
                st.write(f"- {point}")
        elif intent == "relation_query":
            for point in relation_points or ["없음"]:
                st.write(f"- {point}")

        st.markdown("### 그래프 저장 결과")
        c4, c5, c6 = st.columns(3)
        c4.metric("선택된 관계", graph_upsert_result.get("selected_relations", 0))
        c5.metric("삽입된 관계", graph_upsert_result.get("inserted_relations", 0))
        c6.metric("저장 스킵", "Yes" if graph_upsert_result.get("skipped") else "No")

        st.markdown("### 분석 경로")
        if supervisor_explanation:
            if supervisor_explanation.get("initial_plan_reason"):
                st.write(f"- 초기 계획: {supervisor_explanation['initial_plan_reason']}")
            if supervisor_explanation.get("replan_reason"):
                st.write(f"- 재계획(검색): {supervisor_explanation['replan_reason']}")
            if supervisor_explanation.get("extraction_replan_reason"):
                st.write(f"- 재계획(추출): {supervisor_explanation['extraction_replan_reason']}")
            if supervisor_explanation.get("final_upsert_decision"):
                st.write(f"- 저장 결정: {supervisor_explanation['final_upsert_decision']}")
            if supervisor_explanation.get("final_brief_mode"):
                st.write(f"- 브리프 모드: {supervisor_explanation['final_brief_mode']}")
        else:
            st.write("기록된 분석 경로가 없습니다.")

    with tabs[1]:
        st.markdown("### 최종 답변")
        st.write(report_text if report_text else "생성된 최종 답변이 없습니다.")

        with st.expander("상세 리포트 보기", expanded=False):
            st.text(raw_report if raw_report else "상세 리포트가 없습니다.")

        st.download_button(
            label="리포트 다운로드 (.txt)",
            data=raw_report if raw_report else report_text,
            file_name="fingraph_report.txt",
            mime="text/plain"
        )

    with tabs[2]:
        st.markdown("### 하이브리드 그래프 관계")

        focus_current_only = st.checkbox("이번 질문 중심만 보기", value=True)
        filtered_graph_relations = hybrid_graph_relations[:15]

        if filtered_graph_relations:
            graph_df = pd.DataFrame(filtered_graph_relations).copy()
            if "relation" in graph_df.columns:
                graph_df["relation_ko"] = graph_df["relation"].apply(relation_label_ko)
            if "source_type" in graph_df.columns:
                graph_df["source_type_ko"] = graph_df["source_type"].apply(source_type_ko)

            st.dataframe(graph_df, use_container_width=True)
        else:
            st.write("그래프 관계가 없습니다.")

        st.markdown("### 관계 그래프 시각화")
        graph_file = render_relation_graph(
            filtered_graph_relations,
            focus_current_only=focus_current_only
        )

        if graph_file:
            with open(graph_file, "r", encoding="utf-8") as f:
                html = f.read()
            components.html(html, height=580, scrolling=True)
        else:
            if focus_current_only:
                st.info("이번 질문 중심 관계가 아직 없어서 표시할 그래프가 없습니다.")
            else:
                st.write("시각화할 그래프가 없습니다.")

        render_graph_legend()

    with tabs[3]:
        st.markdown("### 검색된 문서/청크")
        if documents:
            df_docs = pd.DataFrame(documents).copy()
            if "text" in df_docs.columns:
                df_docs["preview"] = df_docs["text"].fillna("").apply(lambda x: x[:120])
            show_cols = [c for c in ["title", "chunk_id", "date", "company", "preview"] if c in df_docs.columns]
            st.dataframe(df_docs[show_cols], use_container_width=True)

            for i, doc in enumerate(documents, start=1):
                title = doc.get("title", "Untitled")
                chunk_id = doc.get("chunk_id", "N/A")
                text = doc.get("text", "")
                with st.expander(f"{i}. {title} ({chunk_id})"):
                    st.write(text)
        else:
            st.write("검색된 문서가 없습니다.")

    with tabs[4]:
        st.markdown("### 실행 로그")
        for log in logs:
            st.write(f"- {log}")
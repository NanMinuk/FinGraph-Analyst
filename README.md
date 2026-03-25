# FinGraph Analyst

금융 뉴스에서 **기업-이벤트 관계를 추출**하고,  
**Vector DB(Chroma)** 와 **Graph DB(Neo4j)** 를 결합해  
투자 포인트와 리스크를 구조화하는 **Agentic GraphRAG 분석 시스템**입니다.

---

## Overview

일반적인 뉴스 검색/요약은 문서 단위 정보 제공에 머무르는 경우가 많습니다.  
FinGraph Analyst는 금융 뉴스 안의 비정형 정보를 **Company / Event / Relation** 구조로 변환하고,  
현재 질의에서 추출한 관계와 기존에 축적된 그래프 관계를 결합해  
**설명 가능한 투자 인사이트**를 생성하는 것을 목표로 합니다.

### Example
- **삼성전자 최근 투자포인트 정리해줘**
- **SK하이닉스 최근 리스크 요인 알려줘**

<img width="2437" height="754" alt="image" src="https://github.com/user-attachments/assets/20c07ff9-75fe-4fd3-9d39-acb98e4a778d" />

<img width="2401" height="738" alt="image" src="https://github.com/user-attachments/assets/3f806bfd-8626-4031-b288-262528b98dbf" />

<img width="2394" height="501" alt="image" src="https://github.com/user-attachments/assets/99a11792-8a93-42fc-8783-ce4fbe37a3b6" />

<img width="2396" height="630" alt="image" src="https://github.com/user-attachments/assets/682436e4-50c3-4247-aa78-2b52624d4440" />

<img width="2410" height="576" alt="image" src="https://github.com/user-attachments/assets/eda1172f-0ace-4508-be55-69e8c49e2e1a" />

---

## Key Features

### 0. Workflow Orchestration
- **LangGraph**
- 전체 분석 흐름을 관리하는 orchestration layer.
- 각 단계를 독립 노드로 분리하여 supervisor의 re-planning을 conditional edge로 처리.

**Ingestion 워크플로우 노드 구성:**
- `validate_urls` → `fetch` → `store_raw` → `chunk` → `store_chunks` → `summarize_ingestion`
- URL이 없거나 신규 문서가 없으면 조기 종료

**분석 워크플로우 노드 구성:**
- `route` → `plan` → `retrieval` → `extraction` → `upsert` → `graph` → `brief` → `structured`
- retrieval / extraction 결과가 없을 경우 `replan_retrieval` / `replan_extraction` 노드를 거쳐 재시도

<table>
  <tr>
    <th>Ingestion 워크플로우</th>
    <th>분석 워크플로우</th>
  </tr>
  <tr>
    <td><img width="211" height="729" alt="ingestion_workflow" src="https://github.com/user-attachments/assets/59ace98a-f87a-4c59-b533-d91973a184b7" /></td>
    <td><img width="429" height="928" alt="analysis_workflow" src="https://github.com/user-attachments/assets/f7a90aac-6229-4ada-a632-92f21bf397d1" /></td>
  </tr>
</table>

### 1. Intent-aware analysis
- **LangChain + OpenAI LLM**
- `route` 노드에서 사용자 질의를 분석하여 intent를 분류한다.
- 지원 intent:
  - `company_analysis`
  - `risk_analysis`
  - `relation_query` *(현재는 실험 단계)*

### 2. Supervisor Agent
- **LangChain + OpenAI LLM**
- `plan` 노드에서 현재 질문에 대해 어떤 분석 전략을 사용할지 결정.

다음과 같은 결정을 담당:
- retrieval 범위 (`retrieval_k`)
- 특정 기업 중심 검색 여부 (`retrieval_company`)
- selective upsert 수행 여부
- hybrid graph 사용 여부
- brief generation 수행 여부
- retrieval / extraction 실패 시 re-planning (`replan_retrieval`, `replan_extraction` 노드로 분기)

### 3. Analysis Agent
- **LangChain + OpenAI LLM**
- Supervisor가 정한 계획을 각 독립 노드에서 단계별로 실행.

| 노드 | 역할 |
|---|---|
| `retrieval` | 관련 뉴스 chunk retrieval |
| `extraction` | LLM 기반 relation / entity 추출 |
| `upsert` | selective graph upsert (Neo4j) |
| `graph` | persistent relation 조회 + hybrid graph 생성 |
| `brief` | 투자 brief / report 생성 |
| `structured` | structured output 반환 |

### 4. News retrieval with vector search
- **LangChain-Chroma Vector DB**
- 뉴스 문서를 chunk 단위로 저장하고 semantic retrieval을 수행한다.
- 질문과 관련된 문서 조각을 검색하는 역할을 담당.

### 5. Relation Extraction
- **LangChain + OpenAI LLM**
- 뉴스 본문에서 기업과 이벤트 간 관계를 추출.

예:
- `삼성전자 -> benefits_from -> 상법 개정안 통과`
- `삼성전자 -> reports -> 대규모 자사주 소각`

### 6. Graph Layer
- **Neo4j**
- 고신뢰 relation만 selective upsert 방식으로 저장.
- 질의 시점 current relation과 기존 persistent relation을 결합하여
  hybrid graph context를 구성.

### 7. Report Generation Layer
- **LangChain + OpenAI structured output**
- 핵심 투자 포인트 / 리스크 포인트 / 관계 요약을 생성하고,
- 최종적으로 explainable report와 structured response를 반환.

---

## System Architecture

```text
User Query
   ↓
[Streamlit UI]
   ↓
[FastAPI API]
   ↓
[LangGraph Workflow]
   │
   ├── route          : LLM intent classification
   ├── plan           : Supervisor (전략 수립 / re-plan)
   ├── retrieval      : Chroma vector search
   ├── replan_retrieval    : 검색 결과 없을 때 plan 재수립
   ├── extraction     : LLM relation / entity 추출
   ├── replan_extraction   : relation 없을 때 plan 재수립
   ├── upsert         : Neo4j selective upsert
   ├── graph          : Hybrid graph context 구성
   ├── brief          : 투자 brief 생성
   └── structured     : Structured output 반환
   ↓
Structured Response + Graph + Logs
   ↓
[Streamlit Visualization]
```

---

## Tech Stack

| 분류 | 기술 |
|---|---|
| Workflow | LangGraph |
| LLM | LangChain + OpenAI |
| Vector DB | Chroma |
| Graph DB | Neo4j |
| API | FastAPI + Uvicorn |
| UI | Streamlit + Pyvis |

---

## Getting Started

### 1. 환경 설정

```bash
python -m venv venv
source venv/bin/activate 
pip install -r requirements.txt
```

### 2. 환경변수 설정

`.env` 파일을 프로젝트 루트에 생성:

```
OPENAI_API_KEY=sk-...
NEO4J_URI=neo4j://127.0.0.1:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_password
```

### 3. 실행

```bash
# FastAPI 서버 (터미널 1)
uvicorn app.api.main:app --reload

# Streamlit UI (터미널 2)
streamlit run app/ui/streamlit_app.py
```

# FinGraph Analyst

금융 뉴스에서 **기업-이벤트 관계를 추출**하고,  
**Vector DB(Chroma)** 와 **Graph DB(Neo4j)** 를 결합해  
투자 포인트와 리스크를 구조화하는 **Agentic GraphRAG 분석 시스템**입니다.

---
<img width="429" height="928" alt="analysis_workflow" src="https://github.com/user-attachments/assets/035a54c8-5151-426a-90b9-031fc99c3757" />


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
- 현재 workflow는 다음 두 개의 핵심 노드로 구성:
  - `route_node`
  - `analysis_agent_node`

### 1. Intent-aware analysis
- **LangChain + OpenAI LLM**
- `route_node`에서 사용자 질의를 분석하여 intent를 분류한다.
- 지원 intent:
  - `company_analysis`
  - `risk_analysis`
  - `relation_query` *(현재는 실험 단계)*

### 2. Supervisor Agent
- **LangChain + OpenAI LLM**
- 현재 질문에 대해 어떤 분석 전략을 사용할지 결정.

다음과 같은 결정을 담당:
- retrieval 범위(`retrieval_k`)
- 특정 기업 중심 검색 여부(`retrieval_company`)
- selective upsert 수행 여부
- hybrid graph 사용 여부
- brief generation 수행 여부
- retrieval / extraction 실패 시 re-planning

### 3. Analysis Agent 
- **LangChain + OpenAI LLM**
- Supervisor가 정한 계획을 실제로 실행.
- 
다음 단계를 수행:
1. 관련 뉴스 chunk retrieval
2. LLM 기반 relation extraction
3. selective graph upsert
4. persistent graph relation 조회
5. hybrid graph relation 생성
6. 최종 brief / report 생성
7. structured output 반환

### 4. News retrieval with vector search
- **LangChain-Chroma Vector DB**
- 뉴스 문서를 chunk 단위로 저장하고 semantic retrieval을 수행한다.
- 질문과 관련된 문서 조각을 검색하는 역할을 담당.

### 5. Relation Extraction
- **LangChain + OpenAI LLM**
뉴스 본문에서 기업과 이벤트 간 관계를 추출.

예:
- `삼성전자 -> benefits_from -> 상법 개정안 통과`
- `삼성전자 -> reports -> 대규모 자사주 소각`

### 6. Graph Layer
- **Neo4j**
- 고신뢰 relation만 selective upsert 방식으로 저장.
- 질의 시점 current relation과 기존 persistent relation을 결합하여
  hybrid graph context를 구성..

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
   ├── route_node
   │     └── LLM intent classification
   │
   └── analysis_agent_node
         ├── Supervisor Agent (plan / re-plan)
         ├── Retriever (Chroma)
         ├── Relation Extractor (LLM)
         ├── Selective Upsert (Neo4j)
         ├── Hybrid Graph Builder
         └── Brief / Report Generator
   ↓
Structured Response + Graph + Logs
   ↓
[Streamlit Visualization]

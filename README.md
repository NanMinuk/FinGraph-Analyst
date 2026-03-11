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

<img width="2394" height="501" alt="image" src="https://github.com/user-attachments/assets/99a11792-8a93-42fc-8783-ce4fbe37a3b6" />


---

## Key Features

### 1. Intent-aware analysis
LLM 기반 intent classification으로 질의를 다음 유형으로 분류.

- `company_analysis`
- `risk_analysis`
- `relation_query` *(현재는 실험 단계)*

### 2. News retrieval with vector search
금융 뉴스 문서를 chunk 단위로 분할하고, Chroma 기반 semantic retrieval을 수행.

### 3. LLM-based relation extraction
뉴스 본문에서 기업과 이벤트 간 관계를 추출.

예:
- `삼성전자 -> benefits_from -> 상법 개정안 통과`
- `삼성전자 -> reports -> 대규모 자사주 소각`

### 4. Selective graph persistence
모든 관계를 저장하지 않고, post-processing 이후 남은 **고신뢰 relation만 Neo4j에 selective upsert** 함.

### 5. Hybrid Graph Context
현재 질의에서 추출한 relation과 기존 그래프에 축적된 persistent relation을 결합해  
`current / persistent / hybrid` source type을 구분.

### 6. Explainable report generation
최종 결과를 단순 답변이 아니라 다음 요소와 함께 제공.

- 핵심 투자 포인트
- 리스크 포인트
- 하이브리드 그래프 관계
- 검색 문서 근거
- 분석 경로(supervisor explanation)

### 7. Streamlit UI
분석 결과를 보고서와 그래프 시각화 형태로 확인.

---

## System Architecture

```text
User Query
   ↓
Intent Classifier (LLM)
   ↓
Supervisor Planner (LLM)
   ↓
Retriever (Chroma)
   ↓
Relation Extractor (LLM)
   ↓
Selective Upsert (Neo4j)
   ↓
Hybrid Graph Builder
   ↓
Brief / Report Generator
   ↓
Streamlit UI / FastAPI Response

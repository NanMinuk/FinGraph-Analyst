# FinGraph Analyst

금융 뉴스에서 **기업-이벤트 관계를 추출**하고,  
**Vector DB(Chroma)** 와 **Graph DB(Neo4j)** 를 결합해  
투자 포인트와 리스크를 구조화하는 **Agentic GraphRAG 분석 시스템**입니다.

---

## 왜 GraphRAG인가?

일반적인 RAG는 질문과 유사한 문서를 찾아 LLM에 넘깁니다.  
하지만 금융 분석에서는 **문서 간 관계의 축적**이 중요합니다.

> "삼성전자가 지난 3개월간 어떤 이벤트와 연결됐는가?"

이 질문은 단일 문서로 답하기 어렵습니다.  
여러 뉴스에 걸쳐 등장한 관계를 **누적·구조화**해야 답할 수 있습니다.

| 방식 | 한계 |
|---|---|
| 순수 RAG | 문서 단위 응답, 관계 축적 불가 |
| Fine-tuning | 실시간 뉴스 반영 어려움, 비용 큼 |
| **GraphRAG (본 시스템)** | 관계를 그래프로 누적, 설명 가능한 인사이트 생성 |

---

## 성능 측정 결과

삼성전자 뉴스 14개 (46 chunks) 기준, LLM-as-Judge 자동 평가:

### Retrieval Hit Rate 비교

| 검색 방식 | Hit Rate |
|---|---|
| 순수 벡터 검색 (baseline) | 65% |
| **Hybrid Graph (본 시스템)** | **85%** |

> 순수 벡터 검색 대비 **+20%p** 향상

### 관계 추출 정확도 (Precision)

| 방식 | Precision |
|---|---|
| 순수 벡터 검색 (baseline) | 62% |
| **Hybrid Graph (본 시스템)** | **79%** |

> 순수 벡터 검색 대비 **+17%p** 향상

- 평가 방식: LLM-as-Judge (`gpt-4.1-mini`)
- 평가 샘플: 삼성전자 뉴스 14개 (46 chunks)

---

## 시스템 구조

```text
User Query
   ↓
[Streamlit UI]
   ↓
[FastAPI]
   ↓
[LangGraph Workflow]
   │
   ├── route          : LLM intent 분류 (company_analysis / risk_analysis / relation_query)
   ├── plan           : Supervisor — retrieval 전략 수립 / re-plan 분기
   ├── retrieval      : Chroma 벡터 검색 (3단계 폴백)
   ├── replan_retrieval    : 검색 결과 없을 때 plan 재수립
   ├── extraction     : LLM relation / entity 추출
   ├── replan_extraction   : relation 없을 때 plan 재수립
   ├── upsert         : Neo4j selective upsert (신뢰도 0.8 이상)
   ├── graph          : persistent relation 조회 + hybrid graph 구성
   ├── brief          : 투자 brief 생성
   └── structured     : Structured output 반환
   ↓
Structured Response + Graph Visualization + Logs
   ↓
[Streamlit + Pyvis]
```

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

---

## 주요 설계 결정

### 1. LangGraph를 선택한 이유
Supervisor의 re-planning 로직을 구현할 때 **조건부 분기**가 핵심이었습니다.  
retrieval 결과가 0이면 `replan_retrieval` 노드로, relation이 0이면 `replan_extraction` 노드로 분기하는 구조는 LangGraph의 conditional edge로 자연스럽게 표현됩니다.  
단순 체인(LangChain LCEL)으로는 이 분기를 명시적으로 표현하기 어려웠습니다.

### 2. Hybrid Graph 설계
현재 질의에서 추출한 관계(current)와 기존에 축적된 관계(persistent)를 단순 합산하면 오래된 정보가 최신 정보를 희석합니다.  
이를 해결하기 위해 **current 70% + persistent 30% 가중치** 방식의 hybrid scoring을 적용했습니다.

### 3. Selective Upsert
모든 관계를 Neo4j에 저장하면 노이즈가 누적됩니다.  
**신뢰도 0.8 이상**인 관계만 저장하는 selective upsert로 그래프 품질을 유지했습니다.

### 4. 3단계 Retrieval 폴백
company 필터 + 벡터 검색 → company 텍스트 매칭 → 필터 없는 전체 검색 순으로 폴백합니다.  
첫 번째 단계만 사용하면 새로운 기업 질의 시 결과가 0건이 되는 케이스가 있었기 때문입니다.

---

## 사용 예시

<img width="2437" height="754" alt="image" src="https://github.com/user-attachments/assets/20c07ff9-75fe-4fd3-9d39-acb98e4a778d" />

<img width="2401" height="738" alt="image" src="https://github.com/user-attachments/assets/3f806bfd-8626-4031-b288-262528b98dbf" />

<img width="2394" height="501" alt="image" src="https://github.com/user-attachments/assets/99a11792-8a93-42fc-8783-ce4fbe37a3b6" />

<img width="2396" height="630" alt="image" src="https://github.com/user-attachments/assets/682436e4-50c3-4247-aa78-2b52624d4440" />

<img width="2410" height="576" alt="image" src="https://github.com/user-attachments/assets/eda1172f-0ace-4508-be55-69e8c49e2e1a" />

---

## 한계점 및 개선 방향

| 한계 | 원인 | 개선 방안 |
|---|---|---|
| 관계 추출 Precision 74% | LLM이 head 기업 미언급 문장에서도 관계 생성 | head 기업 명시 조건 강화, few-shot 예시 추가 |
| 단일 뉴스 소스 | 네이버 뉴스 HTML 파싱 특화 | RSS + 다중 소스 폴백 |
| Neo4j 쿼리 성능 | LIMIT 하드코딩, 인덱스 없음 | 인덱스 전략 추가, 페이지네이션 적용 |
| 동기 처리 | FastAPI sync-only | async 전환 + 워커 분리 |

---

## Tech Stack

| 분류 | 기술 |
|---|---|
| Workflow Orchestration | LangGraph |
| LLM | LangChain + OpenAI (gpt-4.1-mini / gpt-4.1-nano) |
| Vector DB | Chroma + CacheBackedEmbeddings |
| Graph DB | Neo4j |
| API | FastAPI + Uvicorn |
| UI | Streamlit + Pyvis |
| 평가 | LLM-as-Judge (gpt-4.1-mini) |
| 배포 | Docker Compose |

---

## Getting Started

### 1. 환경변수 설정

```bash
cp .env.example .env
# .env 파일에서 OPENAI_API_KEY, NEO4J_PASSWORD 입력
```

### 2. 실행 (Docker)

```bash
docker-compose up --build
```

| 서비스 | 주소 |
|---|---|
| Streamlit UI | http://localhost:8501 |
| FastAPI docs | http://localhost:8000/docs |
| Neo4j Browser | http://localhost:7474 |

### 3. 뉴스 수집 (Ingest)

`http://localhost:8000/docs` → `/ingest` → 네이버 뉴스 URL 입력

### 4. 분석 실행

Streamlit UI에서 기업명과 질문 입력:
- `삼성전자 최근 투자포인트 정리해줘`
- `SK하이닉스 최근 리스크 요인 알려줘`

---

## 평가 재현

```bash
python -m tests.evaluate \
  --query "삼성전자 최근 투자포인트" \
  --company 삼성전자 \
  --mode auto
```

결과는 `tests/results/` 에 JSON으로 저장됩니다.

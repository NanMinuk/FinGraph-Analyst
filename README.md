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

## 주요 실험 결과

### 1. 뉴스 감성 기반 백테스팅

GraphRAG로 추출한 관계를 매매 시그널로 변환해 실제 주가 수익률과 비교합니다.

**실험 조건**: 삼성전자(005930) / 2026-03-16 ~ 2026-03-30 

| 지표 | T+1 전략 | 포지션 전략 | Buy & Hold |
|---|---|---|---|
| 누적 수익률 | **+10.99%** | **+4.24%** | -6.57% |
| 승률 | 80.0% | 50.0% | - |
| 샤프 비율 | 9.84 | 6.01 | - |
| 전략 초과수익 (Alpha) | **+17.56%p** | **+10.81%p** | 기준 |

- **T+1 전략**: 시그널 당일 매수 → 다음 거래일 청산 (5회 거래, 4승 1패)
- **포지션 전략**: buy 시그널에 진입 → sell 시그널에 청산 (2회 거래)

> 단순 보유 대비 +17.56%p 초과수익. 뉴스의 관계 구조가 가격 방향성과 상관관계가 있음을 시사합니다.

### 2. GraphRAG vs 순수 벡터 검색

삼성전자 뉴스 14개 (46 chunks) 기준, LLM-as-Judge 자동 평가:

| 지표 | 순수 벡터 검색 | Hybrid GraphRAG | 향상 |
|---|---|---|---|
| Retrieval Hit Rate | 65% | **85%** | **+20%p** |
| 관계 추출 Precision | 62% | **79%** | **+17%p** |

- 평가 방식: LLM-as-Judge (`gpt-4.1-mini`)

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

### 1. DB 구조: 벡터 DB + 그래프 DB 결합

처음에는 벡터 DB만으로 구현하는 방안을 검토했습니다. 구현이 단순하고 유사도 검색이 빠르다는 장점이 있었습니다.  
그러나 "A 기업이 B 기업에 투자했고, B 기업이 C 기업과 합병했다"는 식의 다단계 관계 추론은 벡터 유사도만으로는 처리할 수 없었습니다.

결과적으로 **Chroma(벡터) + Neo4j(그래프)** 결합 구조를 선택했습니다.
- 문서 간 relevance → 벡터 검색
- 기업-이벤트 관계 맥락 → 그래프 탐색

### 2. 에이전트 구조: Supervisor-Executor 분리

초기에는 단일 에이전트가 계획과 실행을 모두 담당했습니다. 개발 속도는 빠르지만, 쿼리 유형이 달라질 때 retrieval 실패와 관계 추출 오류가 연쇄적으로 전파됐습니다.

오류 로그를 분석한 결과, 계획과 실행이 분리되지 않으면 실행 단계 실패 시 전체 흐름이 복구 불가능한 상태에 빠지는 것이 원인이었습니다.  
**Supervisor Agent**(전략 수립) + **Analysis Agent**(단계별 실행)으로 역할을 분리하고, 실패 감지 시 `replan_retrieval` / `replan_extraction` 노드가 흐름을 자동 재구성하도록 conditional edge를 추가했습니다.

### 3. Hybrid Graph 가중치 설계

현재 질의에서 추출한 관계(current)와 기존 누적 관계(persistent)를 단순 합산하면 오래된 정보가 최신 정보를 희석합니다.  
**current 70% + persistent 30%** 가중치 방식의 hybrid scoring으로 최신성을 유지했습니다.

### 4. Selective Upsert

모든 관계를 Neo4j에 저장하면 노이즈가 누적됩니다.  
**신뢰도 0.8 이상**인 관계만 저장하는 selective upsert로 그래프 품질을 유지했습니다.

---

## 사용 예시

<img width="2437" height="754" alt="image" src="https://github.com/user-attachments/assets/20c07ff9-75fe-4fd3-9d39-acb98e4a778d" />

<img width="2401" height="738" alt="image" src="https://github.com/user-attachments/assets/3f806bfd-8626-4031-b288-262528b98dbf" />

<img width="2394" height="501" alt="image" src="https://github.com/user-attachments/assets/99a11792-8a93-42fc-8783-ce4fbe37a3b6" />

<img width="2396" height="630" alt="image" src="https://github.com/user-attachments/assets/682436e4-50c3-4247-aa78-2b52624d4440" />

<img width="2410" height="576" alt="image" src="https://github.com/user-attachments/assets/eda1172f-0ace-4508-be55-69e8c49e2e1a" />

<img width="2406" height="1130" alt="image" src="https://github.com/user-attachments/assets/8e56a3eb-3fb0-4a4a-9c4b-73b745365a03" />

---

## 한계점 및 개선 방향

| 한계 | 원인 | 개선 방안 |
|---|---|---|
| 관계 추출 Precision 74% | LLM이 head 기업 미언급 문장에서도 관계 생성 | head 기업 명시 조건 강화, few-shot 예시 추가 |
| 단일 뉴스 소스 | 네이버 뉴스 HTML 파싱 특화 | RSS + 다중 소스 폴백 |
| Neo4j 쿼리 성능 | LIMIT 하드코딩, 인덱스 없음 | 인덱스 전략 추가 |

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

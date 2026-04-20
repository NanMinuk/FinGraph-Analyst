from datetime import date

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv
from app.agents.workflow import build_workflow
from app.agents.ingestion_workflow import build_ingestion_workflow
from app.ingestion.chroma_store import get_raw_news_vectorstore, get_chunk_vectorstore, get_all_chunks_raw
from app.backtest.sentiment_scorer import compute_daily_sentiment, generate_signals, parse_date
from app.backtest.backtester import run_backtest, run_position_backtest, format_report
from app.backtest.price_fetcher import fetch_stock_prices
from app.tools.extraction_tools import extract_relations_from_chunks_tool

load_dotenv()
app = FastAPI(title="FinGraph Analyst API")
workflow = build_workflow()
ingestion_workflow = build_ingestion_workflow()

class QueryRequest(BaseModel):
    query: str
    company: str | None = None

class IngestRequest(BaseModel):
    urls: list[str]

class BacktestRequest(BaseModel):
    company: str
    ticker: str
    start: str          # "YYYY-MM-DD"
    end: str            # "YYYY-MM-DD"
    hold_days: int = 1
    buy_threshold: float = 0.3
    sell_threshold: float = -0.3

@app.get("/")
def root():
    return {"message": "FinGraph Analyst API is running"}


@app.get("/stats")
def stats():
    raw_count = get_raw_news_vectorstore()._collection.count()
    chunk_count = get_chunk_vectorstore()._collection.count()
    return {
        "raw_news": raw_count,
        "news_chunks": chunk_count,
    }


@app.post("/analyze")
def analyze(req: QueryRequest):
    result = workflow.invoke({
        "query": req.query,
        "company": req.company,
        "logs": []
    })

    return {
        "query": result.get("query"),
        "company": result.get("company"),
        "intent": result.get("intent"),
        "documents": result.get("documents", []),
        "entities": result.get("entities", []),
        "relations": result.get("relations", []),
        "document_relation_map": result.get("document_relation_map", {}),
        "selected_graph_relations" : result.get("selected_graph_relations", []),
        "persistent_graph_relations": result.get("persistent_graph_relations", []),
        "hybrid_graph_relations": result.get("hybrid_graph_relations", []),
        "graph_upsert_result": result.get("graph_upsert_result", {}),
        "key_points": result.get("key_points", []),
        "risk_points": result.get("risk_points", []),
        "relation_points": result.get("relation_points", []),
        "report": result.get("report", ""),
        "raw_report" : result.get("raw_report", ""),
        "supervisor_explanation" : result.get("supervisor_explanation", {}),
        "logs": result.get("logs", [])
    }

@app.post("/ingest")
def ingest(req: IngestRequest):
    result = ingestion_workflow.invoke({
        "urls": req.urls,
        "logs": []
    })

    print("INGEST RESULT =", result)

    return {
        "ingestion_summary": result.get("ingestion_summary", {}),
        "ingestion_results": result.get("ingestion_results", []),
        "logs": result.get("logs", []),
    }


@app.post("/backtest")
def backtest(req: BacktestRequest):
    try:
        start = date.fromisoformat(req.start)
        end   = date.fromisoformat(req.end)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"날짜 형식 오류: {e}")

    # 1) Chroma에서 전체 청크를 가져온 뒤 날짜·키워드 필터
    all_chunks = get_all_chunks_raw()

    from collections import defaultdict
    chunks_by_date: dict = defaultdict(list)

    for chunk in all_chunks:
        date_str = chunk.get("date") or ""
        doc_date = parse_date(str(date_str)) if date_str else None
        if not doc_date or not (start <= doc_date <= end):
            continue
        title = chunk.get("title") or ""
        text  = chunk.get("text") or ""
        company_meta = chunk.get("company") or ""
        if not (
            company_meta == req.company
            or req.company in title
            or req.company in text
        ):
            continue
        chunks_by_date[doc_date].append(chunk)

    # 날짜당 최대 3청크만 사용 (LLM 호출량 제한)
    documents = []
    for doc_date in sorted(chunks_by_date):
        documents.extend(chunks_by_date[doc_date][:3])

    if not documents:
        raise HTTPException(
            status_code=422,
            detail=f"해당 기간({req.start}~{req.end}) '{req.company}' 문서가 없습니다. 먼저 뉴스를 ingest 해주세요.",
        )

    # 2) 관계 추출 (전체 문서를 한 번에)
    extraction = extract_relations_from_chunks_tool(documents, confidence_threshold=0.5)
    relations  = extraction["relations"]

    if not relations:
        raise HTTPException(status_code=422, detail="관계 추출 결과가 없습니다.")

    # 3) 감성 점수 → 매매 시그널
    daily_sentiment = compute_daily_sentiment(relations, documents)
    signals = generate_signals(
        daily_sentiment,
        buy_threshold=req.buy_threshold,
        sell_threshold=req.sell_threshold,
    )

    # 4) 주가 데이터 수집
    try:
        price_df = fetch_stock_prices(req.ticker, start, end)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"주가 데이터 수집 실패: {e}")

    # 5) 백테스팅 실행 — T+N 전략 & 포지션 전략 둘 다
    result_tn  = run_backtest(signals, price_df, hold_days=req.hold_days)
    result_pos = run_position_backtest(signals, price_df)

    report_tn  = format_report(result_tn,  req.ticker, f"T+{req.hold_days}")
    report_pos = format_report(result_pos, req.ticker, "포지션 전략")

    return {
        "ticker":    req.ticker,
        "company":   req.company,
        "period":    {"start": req.start, "end": req.end},
        "hold_days": req.hold_days,
        "doc_count": len(documents),
        "daily_sentiment": {str(k): round(v, 4) for k, v in daily_sentiment.items()},
        "signals":   {str(k): v for k, v in signals.items()},
        # T+N 전략
        "trades":    result_tn["trades"],
        "metrics":   result_tn["metrics"],
        "buy_and_hold_return": result_tn["buy_and_hold_return"],
        "report":    report_tn,
        # 포지션 전략
        "position_trades":   result_pos["trades"],
        "position_metrics":  result_pos["metrics"],
        "report_position":   report_pos,
    }
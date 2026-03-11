from fastapi import FastAPI
from pydantic import BaseModel
from dotenv import load_dotenv
from app.agents.workflow import build_workflow
from app.agents.ingestion_workflow import build_ingestion_workflow

load_dotenv()
app = FastAPI(title="FinGraph Analyst API")
workflow = build_workflow()
ingestion_workflow = build_ingestion_workflow()

class QueryRequest(BaseModel):
    query: str
    company: str | None = None

class IngestRequest(BaseModel):
    urls: list[str]

@app.get("/")
def root():
    return {"message": "FinGraph Analyst API is running"}


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
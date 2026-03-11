from typing import Dict, Any, List, Optional

from app.graph.neo4j_client import Neo4jClient
from app.graph.queries import GET_RELEVANT_GRAPH_RELATIONS_QUERY, UPSERT_RELATION_QUERY
from app.extraction.relation_postprocessor import filter_persistent_relations_for_hybrid, select_relations_for_graph_upsert

def selective_upsert_graph_tool(
    relations: List[Dict[str, Any]],
    min_confidence: float = 0.8,
) -> Dict[str, Any]:
    selected_relations = select_relations_for_graph_upsert(
        relations,
        min_confidence=min_confidence,
    )

    inserted = 0

    if not selected_relations:
        return {
            "summary": {
                "selected_relations": 0,
                "inserted_relations": 0,
                "skipped": True,
            },
            "selected_graph_relations": [],
        }

    try:
        client = Neo4jClient()
        try:
            for rel in selected_relations:
                client.run_query(UPSERT_RELATION_QUERY, rel)
                inserted += 1
        finally:
            client.close()

        return {
            "summary": {
                "selected_relations": len(selected_relations),
                "inserted_relations": inserted,
                "skipped": False,
            },
            "selected_graph_relations": selected_relations,
        }

    except Exception as e:
        return {
            "summary": {
                "selected_relations": len(selected_relations),
                "inserted_relations": inserted,
                "skipped": False,
                "error": str(e),
            },
            "selected_graph_relations": selected_relations,
        }


def rerank_hybrid_relations(current_relations, persistent_relations):
    merged = {}

    def relation_key(rel):
        return (
            rel.get("head"),
            rel.get("relation"),
            rel.get("tail"),
        )

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
            merged[key]["persistent_confidence"] = max(
                merged[key].get("persistent_confidence", 0.0),
                p_conf,
            )

            c_conf = merged[key].get("current_confidence", 0.0)
            p_conf = merged[key].get("persistent_confidence", 0.0)

            if c_conf > 0.0:
                merged[key]["hybrid_score"] = c_conf * 0.7 + p_conf * 0.3 + 0.1
                merged[key]["source_type"] = "hybrid"
            else:
                merged[key]["hybrid_score"] = p_conf
                merged[key]["source_type"] = "persistent"

    ranked = sorted(
        merged.values(),
        key=lambda x: x.get("hybrid_score", 0.0),
        reverse=True,
    )
    return ranked


def build_hybrid_graph_context_tool(
    current_relations: List[Dict[str, Any]],
    company: Optional[str] = None,
) -> Dict[str, Any]:
    persistent_relations: List[Dict[str, Any]] = []

    if company:
        try:
            client = Neo4jClient()
            try:
                persistent_relations = client.run_query(
                    GET_RELEVANT_GRAPH_RELATIONS_QUERY,
                    {"company": company},
                )
            finally:
                client.close()
        except Exception as e:
            return {
                "summary": {
                    "company": company,
                    "current_count": len(current_relations),
                    "persistent_count": 0,
                    "hybrid_count": len(current_relations),
                    "error": str(e),
                },
                "persistent_graph_relations": [],
                "hybrid_graph_relations": current_relations,
            }

    persistent_relations = filter_persistent_relations_for_hybrid(
        persistent_relations,
        min_confidence=0.75,
    )

    hybrid_relations = rerank_hybrid_relations(
        current_relations,
        persistent_relations,
    )

    summary = {
        "company": company,
        "current_count": len(current_relations),
        "persistent_count": len(persistent_relations),
        "hybrid_count": len(hybrid_relations),
    }

    return {
        "summary": summary,
        "persistent_graph_relations": persistent_relations,
        "hybrid_graph_relations": hybrid_relations,
    }
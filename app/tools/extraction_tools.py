from typing import Dict, Any, List

from app.extraction.llm_extractor import extract_entities_and_relations_llm_batch
from app.extraction.relation_extractor import extract_entities_and_relations
from app.extraction.relation_postprocessor import postprocess_relations


def group_relations_by_document(relations: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    grouped = {}

    for rel in relations:
        doc_id = rel.get("document_id", "unknown_doc")
        grouped.setdefault(doc_id, []).append(rel)

    return grouped


def extract_relations_from_chunks_tool(
    documents: List[Dict[str, Any]],
    confidence_threshold: float = 0.65,
) -> Dict[str, Any]:
    if not documents:
        return {
            "summary": {
                "input_chunks": 0,
                "entities": 0,
                "relations": 0,
                "document_groups": 0,
                "llm_used": False,
                "fallback_used": False,
            },
            "entities": [],
            "relations": [],
            "document_relation_map": {},
        }

    llm_out = extract_entities_and_relations_llm_batch(documents)

    entities = llm_out.get("entities", [])
    relations = llm_out.get("relations", [])

    llm_used = True
    fallback_used = False

    if not entities and not relations:
        entities, relations = extract_entities_and_relations(documents)
        fallback_used = True

    relations = postprocess_relations(
        relations,
        confidence_threshold=confidence_threshold,
    )

    document_relation_map = group_relations_by_document(relations)

    summary = {
        "input_chunks": len(documents),
        "entities": len(entities),
        "relations": len(relations),
        "document_groups": len(document_relation_map),
        "llm_used": llm_used,
        "fallback_used": fallback_used,
    }

    return {
        "summary": summary,
        "entities": entities,
        "relations": relations,
        "document_relation_map": document_relation_map,
    }
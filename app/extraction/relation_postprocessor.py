from typing import List, Dict, Any


def filter_persistent_relations_for_hybrid(
    relations: List[Dict[str, Any]],
    min_confidence: float = 0.75,
) -> List[Dict[str, Any]]:
    relations = filter_low_confidence_relations(relations, min_confidence)
    relations = filter_weak_tail_relations(relations)
    relations = deduplicate_relations(relations)
    return relations

def deduplicate_relations(relations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen = set()
    unique_relations = []

    for rel in relations:
        key = (
            rel.get("head"),
            rel.get("relation"),
            rel.get("tail"),
            rel.get("document_id"),
        )
        if key not in seen:
            seen.add(key)
            unique_relations.append(rel)

    return unique_relations


def filter_low_confidence_relations(
    relations: List[Dict[str, Any]],
    threshold: float = 0.65,
) -> List[Dict[str, Any]]:
    return [
        rel for rel in relations
        if float(rel.get("confidence", 0.0)) >= threshold
    ]


def filter_weak_tail_relations(relations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    weak_tails = {"수혜", "실적", "공급", "투자", "이벤트", "변화"}

    filtered = []
    for rel in relations:
        tail = (rel.get("tail") or "").strip()
        if not tail:
            continue
        if len(tail) <= 1:
            continue
        if tail in weak_tails:
            continue
        filtered.append(rel)

    return filtered


def postprocess_relations(
    relations: List[Dict[str, Any]],
    confidence_threshold: float = 0.65,
) -> List[Dict[str, Any]]:
    relations = filter_low_confidence_relations(relations, confidence_threshold)
    relations = filter_weak_tail_relations(relations)
    relations = deduplicate_relations(relations)
    return relations

def select_relations_for_graph_upsert(
    relations: List[Dict[str, Any]],
    min_confidence: float = 0.8,
) -> List[Dict[str, Any]]:
    selected = []

    for rel in relations:
        head = (rel.get("head") or "").strip()
        tail = (rel.get("tail") or "").strip()
        relation = (rel.get("relation") or "").strip()
        confidence = float(rel.get("confidence", 0.0))

        if not head or not tail or not relation:
            continue
        if confidence < min_confidence:
            continue
        if len(tail) <= 1:
            continue

        selected.append(rel)

    return deduplicate_relations(selected)
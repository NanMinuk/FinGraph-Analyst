from typing import List, Dict, Any


CANONICAL_RELATIONS = {
    "benefits_from": [
        "benefits_from",
        "benefit_from",
        "beneficiary_of",
        "positive_impact",
        "favorable_to",
        "수혜",
        "수혜가능성",
    ],
    "reports": [
        "reports",
        "report",
        "announces",
        "discloses",
        "earnings_related",
        "실적",
        "공시",
    ],
    "supplies": [
        "supplies",
        "supply",
        "provides_to",
        "supplier_of",
        "공급",
        "공급관련",
    ],
    "invests_in": [
        "invests_in",
        "invest_in",
        "investment_in",
        "expands_investment",
        "투자",
        "투자확대",
    ],
    "regulatory_risk": [
        "regulatory_risk",
        "regulation_risk",
        "policy_risk",
        "legal_risk",
        "규제",
        "규제리스크",
    ],
}


def normalize_relation_label(label: str) -> str:
    raw = (label or "").strip().lower().replace(" ", "_")

    for canonical, variants in CANONICAL_RELATIONS.items():
        normalized_variants = [
            v.strip().lower().replace(" ", "_") for v in variants
        ]
        if raw in normalized_variants:
            return canonical

    return "reports"


def normalize_relations(relations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    normalized = []

    for rel in relations:
        copied = dict(rel)
        copied["relation"] = normalize_relation_label(rel.get("relation", ""))
        normalized.append(copied)

    return normalized
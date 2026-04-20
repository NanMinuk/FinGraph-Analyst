from collections import defaultdict
from datetime import date, datetime
from typing import Optional

SENTIMENT_WEIGHT = {
    "benefits_from":   +1.0,
    "invests_in":      +0.7,
    "supplies":        +0.5,
    "reports":          0.0,
    "regulatory_risk": -1.0,
}


def parse_date(date_str: str) -> Optional[date]:
    """다양한 날짜 형식 파싱"""
    if not date_str:
        return None
    # 전체 문자열로 시도
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d", "%Y.%m.%d"):
        try:
            return datetime.strptime(date_str, fmt).date()
        except (ValueError, TypeError):
            continue
    # 앞 10자만 잘라서 재시도 (ISO datetime → YYYY-MM-DD 또는 YYYY.MM.DD)
    if len(date_str) >= 10:
        for fmt in ("%Y-%m-%d", "%Y.%m.%d"):
            try:
                return datetime.strptime(date_str[:10], fmt).date()
            except (ValueError, TypeError):
                continue
    return None


def compute_daily_sentiment(
    relations: list[dict],
    documents: list[dict],
) -> dict[date, float]:
    """
    날짜별 감성 점수 계산.

    Args:
        relations: /analyze API의 relations 필드
        documents: /analyze API의 documents 필드 (날짜 정보 포함)

    Returns:
        {date: sentiment_score} dict
    """
    # document_id → date 매핑 구성
    doc_date_map: dict[str, date] = {}
    for doc in documents:
        doc_id = doc.get("doc_id") or doc.get("metadata", {}).get("doc_id")
        date_str = doc.get("date") or doc.get("metadata", {}).get("date")
        if doc_id and date_str:
            parsed = parse_date(str(date_str))
            if parsed:
                doc_date_map[doc_id] = parsed

    # 날짜별 감성 점수 합산
    daily_scores: dict[date, list[float]] = defaultdict(list)

    for rel in relations:
        doc_id = rel.get("document_id")
        relation = rel.get("relation", "reports")
        confidence = float(rel.get("confidence", 0.0))

        doc_date = doc_date_map.get(doc_id)
        if not doc_date:
            continue

        weight = SENTIMENT_WEIGHT.get(relation, 0.0)
        score = weight * confidence
        daily_scores[doc_date].append(score)

    # 날짜별 평균
    return {
        d: sum(scores) / len(scores)
        for d, scores in daily_scores.items()
        if scores
    }


def generate_signals(
    daily_sentiment: dict[date, float],
    buy_threshold: float = 0.3,
    sell_threshold: float = -0.3,
) -> dict[date, str]:
    """
    감성 점수 → 매매 시그널 변환.

    Returns:
        {date: "buy" | "sell" | "hold"}
    """
    signals = {}
    for d, score in sorted(daily_sentiment.items()):
        if score >= buy_threshold:
            signals[d] = "buy"
        elif score <= sell_threshold:
            signals[d] = "sell"
        else:
            signals[d] = "hold"
    return signals

from typing import List, Dict, Any


def generate_key_points_from_graph_relations(graph_relations: List[Dict[str, Any]]) -> List[str]:
    key_points = []

    for rel in graph_relations:
        head = rel.get("head", "해당 기업")
        relation = rel.get("relation", "")
        tail = rel.get("tail", "이벤트")

        if relation == "benefits_from":
            key_points.append(
                f"{head}는 {tail} 이벤트와 연결되어 긍정적 모멘텀 가능성이 있습니다."
            )
        elif relation == "reports":
            key_points.append(
                f"{head}는 {tail} 관련 이벤트와 연결되어 실적 흐름을 점검할 필요가 있습니다."
            )
        elif relation == "supplies":
            key_points.append(
                f"{head}는 {tail} 관련 공급 이슈와 연결되어 공급 확대 흐름을 확인할 필요가 있습니다."
            )
        elif relation == "invests_in":
            key_points.append(
                f"{head}는 {tail} 관련 투자 움직임과 연결되어 중장기 성장 포인트로 볼 수 있습니다."
            )
        else:
            key_points.append(
                f"{head}는 {tail} 이벤트와 연결되어 추가 확인이 필요한 상태입니다."
            )

    return list(dict.fromkeys(key_points))[:3]


def generate_risk_points_from_graph_relations(graph_relations: List[Dict[str, Any]]) -> List[str]:
    risk_points = []

    for rel in graph_relations:
        head = rel.get("head", "해당 기업")
        relation = rel.get("relation", "")
        tail = rel.get("tail", "이벤트")

        if relation == "regulatory_risk":
            risk_points.append(
                f"{head}는 {tail}와 관련된 규제 리스크를 점검할 필요가 있습니다."
            )
        elif relation == "reports":
            risk_points.append(
                f"{head}는 {tail} 관련 이벤트와 연결되어 실적 변동 가능성을 확인할 필요가 있습니다."
            )
        elif relation == "supplies":
            risk_points.append(
                f"{head}는 {tail} 관련 공급 이슈와 연결되어 공급 차질 또는 변동성을 점검할 필요가 있습니다."
            )
        elif relation == "benefits_from":
            risk_points.append(
                f"{head}는 {tail} 이벤트와 연결되어 있으나 기대가 과도하게 반영되었는지 점검할 필요가 있습니다."
            )
        elif relation == "invests_in":
            risk_points.append(
                f"{head}는 {tail} 관련 투자 확대와 연결되어 있으므로 투자 집행 부담과 성과 가시성을 함께 확인할 필요가 있습니다."
            )
        else:
            risk_points.append(
                f"{head}는 {tail} 이벤트와 연결되어 있어 추가적인 리스크 점검이 필요합니다."
            )

    return list(dict.fromkeys(risk_points))[:3]


def generate_relation_points_from_graph_relations(graph_relations: List[Dict[str, Any]]) -> List[str]:
    relation_points = []

    for rel in graph_relations:
        head = rel.get("head", "해당 종목")
        relation = rel.get("relation", "")
        tail = rel.get("tail", "이벤트")

        if relation == "invests_in":
            relation_points.append(
                f"{head}는 {tail} 관련 투자 확대와 연결된 종목으로 식별되었습니다."
            )
        elif relation == "supplies":
            relation_points.append(
                f"{head}는 {tail} 관련 공급 확대 흐름과 연결된 종목으로 식별되었습니다."
            )
        elif relation == "benefits_from":
            relation_points.append(
                f"{head}는 {tail} 이벤트 수혜 가능성과 연결된 종목으로 식별되었습니다."
            )
        elif relation == "reports":
            relation_points.append(
                f"{head}는 {tail} 관련 실적 흐름과 연결된 종목으로 식별되었습니다."
            )
        else:
            relation_points.append(
                f"{head}는 {tail} 이벤트와 연결된 종목으로 확인되었습니다."
            )

    return list(dict.fromkeys(relation_points))[:5]
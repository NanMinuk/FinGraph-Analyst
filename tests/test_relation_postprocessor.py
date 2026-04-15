import pytest
from app.extraction.relation_postprocessor import (
    filter_low_confidence_relations,
    filter_weak_tail_relations,
    deduplicate_relations,
    select_relations_for_graph_upsert,
    postprocess_relations,
)


def make_relation(**kwargs):
    defaults = {
        "head": "삼성전자",
        "relation": "benefits_from",
        "tail": "HBM 수요 증가",
        "confidence": 0.9,
        "document_id": "doc_001",
    }
    return {**defaults, **kwargs}


class TestFilterLowConfidence:

    def test_임계값_미만_관계_제거(self):
        relations = [
            make_relation(confidence=0.4),
            make_relation(confidence=0.65),
            make_relation(confidence=0.9),
        ]
        result = filter_low_confidence_relations(relations, threshold=0.65)
        assert len(result) == 2
        assert all(r["confidence"] >= 0.65 for r in result)

    def test_빈_리스트_입력(self):
        assert filter_low_confidence_relations([]) == []

    def test_모두_통과(self):
        relations = [make_relation(confidence=0.8), make_relation(confidence=0.9)]
        result = filter_low_confidence_relations(relations, threshold=0.5)
        assert len(result) == 2

    def test_모두_제거(self):
        relations = [make_relation(confidence=0.3), make_relation(confidence=0.4)]
        result = filter_low_confidence_relations(relations, threshold=0.8)
        assert result == []


class TestFilterWeakTail:

    def test_약한_tail_제거(self):
        weak = ["수혜", "실적", "공급", "투자", "이벤트", "변화"]
        for tail in weak:
            relations = [make_relation(tail=tail)]
            result = filter_weak_tail_relations(relations)
            assert result == [], f"'{tail}' 이 제거되어야 하는데 통과됨"

    def test_한글자_tail_제거(self):
        relations = [make_relation(tail="A")]
        assert filter_weak_tail_relations(relations) == []

    def test_빈_tail_제거(self):
        relations = [make_relation(tail="")]
        assert filter_weak_tail_relations(relations) == []

    def test_정상_tail_통과(self):
        relations = [make_relation(tail="HBM 수요 증가")]
        result = filter_weak_tail_relations(relations)
        assert len(result) == 1


class TestDeduplicateRelations:

    def test_완전_동일한_관계_중복_제거(self):
        rel = make_relation()
        result = deduplicate_relations([rel, rel.copy()])
        assert len(result) == 1

    def test_document_id_다르면_별개로_유지(self):
        rel1 = make_relation(document_id="doc_001")
        rel2 = make_relation(document_id="doc_002")
        result = deduplicate_relations([rel1, rel2])
        assert len(result) == 2

    def test_빈_리스트(self):
        assert deduplicate_relations([]) == []


class TestSelectRelationsForGraphUpsert:

    def test_신뢰도_0_8_미만_제외(self):
        relations = [
            make_relation(confidence=0.75),
            make_relation(confidence=0.8),
            make_relation(confidence=0.95),
        ]
        result = select_relations_for_graph_upsert(relations, min_confidence=0.8)
        assert len(result) == 2
        assert all(r["confidence"] >= 0.8 for r in result)

    def test_head_없으면_제외(self):
        relations = [make_relation(head="")]
        assert select_relations_for_graph_upsert(relations) == []

    def test_tail_없으면_제외(self):
        relations = [make_relation(tail="")]
        assert select_relations_for_graph_upsert(relations) == []

    def test_한글자_tail_제외(self):
        relations = [make_relation(tail="A", confidence=0.95)]
        assert select_relations_for_graph_upsert(relations) == []


class TestPostprocessRelations:

    def test_전체_파이프라인(self):
        relations = [
            make_relation(confidence=0.9, tail="HBM 수요 증가"),   # 통과
            make_relation(confidence=0.3, tail="HBM 수요 증가"),   # 신뢰도 낮아 제거
            make_relation(confidence=0.8, tail="수혜"),             # weak tail 제거
            make_relation(confidence=0.9, tail="HBM 수요 증가"),   # 중복 제거
        ]
        result = postprocess_relations(relations, confidence_threshold=0.65)
        assert len(result) == 1
        assert result[0]["tail"] == "HBM 수요 증가"

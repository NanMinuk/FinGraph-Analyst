"""
관계 정규화 테스트
- 한글/영문 변형 → canonical 관계명으로 정규화되는지 검증
"""

import pytest
from app.extraction.relation_normalizer import normalize_relation_label, normalize_relations


class TestNormalizeRelationLabel:

    def test_한글_수혜_benefits_from으로_정규화(self):
        assert normalize_relation_label("수혜") == "benefits_from"

    def test_한글_실적_reports로_정규화(self):
        assert normalize_relation_label("실적") == "reports"

    def test_한글_공급_supplies로_정규화(self):
        assert normalize_relation_label("공급") == "supplies"

    def test_한글_투자_invests_in으로_정규화(self):
        assert normalize_relation_label("투자") == "invests_in"

    def test_한글_규제_regulatory_risk로_정규화(self):
        assert normalize_relation_label("규제") == "regulatory_risk"

    def test_영문_변형_benefits_from으로_정규화(self):
        assert normalize_relation_label("benefit_from") == "benefits_from"
        assert normalize_relation_label("positive_impact") == "benefits_from"

    def test_영문_변형_reports로_정규화(self):
        assert normalize_relation_label("announces") == "reports"
        assert normalize_relation_label("discloses") == "reports"

    def test_알수없는_관계는_reports로_폴백(self):
        assert normalize_relation_label("unknown_relation") == "reports"
        assert normalize_relation_label("") == "reports"

    def test_대소문자_무관하게_정규화(self):
        assert normalize_relation_label("SUPPLIES") == "supplies"
        assert normalize_relation_label("Benefits_From") == "benefits_from"

    def test_공백포함_관계명_정규화(self):
        assert normalize_relation_label("regulatory risk") == "regulatory_risk"


class TestNormalizeRelations:

    def test_빈_리스트_입력시_빈_리스트_반환(self):
        assert normalize_relations([]) == []

    def test_단일_관계_정규화(self):
        relations = [{"head": "삼성전자", "relation": "수혜", "tail": "HBM 수요 증가"}]
        result = normalize_relations(relations)
        assert result[0]["relation"] == "benefits_from"

    def test_기존_필드_보존(self):
        relations = [{
            "head": "삼성전자",
            "relation": "공급",
            "tail": "TSMC",
            "confidence": 0.9,
            "evidence": "삼성전자가 TSMC에 공급한다.",
        }]
        result = normalize_relations(relations)
        assert result[0]["head"] == "삼성전자"
        assert result[0]["confidence"] == 0.9
        assert result[0]["relation"] == "supplies"

    def test_여러_관계_일괄_정규화(self):
        relations = [
            {"relation": "수혜"},
            {"relation": "실적"},
            {"relation": "투자확대"},
        ]
        result = normalize_relations(relations)
        assert result[0]["relation"] == "benefits_from"
        assert result[1]["relation"] == "reports"
        assert result[2]["relation"] == "invests_in"

    def test_원본_딕셔너리_불변(self):
        original = {"head": "삼성전자", "relation": "수혜", "tail": "이벤트"}
        normalize_relations([original])
        assert original["relation"] == "수혜"  # 원본 변경 없음

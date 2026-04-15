import pytest
from unittest.mock import MagicMock, patch
from app.retrieval.retriever import diversify_documents, _convert_results, retrieve_documents


class TestDiversifyDocuments:

    def test_같은_doc_id_중복_제거(self):
        docs = [
            {"doc_id": "doc_1", "text": "청크 A"},
            {"doc_id": "doc_1", "text": "청크 B"},  # 동일 doc_id
            {"doc_id": "doc_2", "text": "청크 C"},
        ]
        result = diversify_documents(docs, k=5)
        doc_ids = [d["doc_id"] for d in result]
        assert doc_ids.count("doc_1") == 1

    def test_k개_이상_반환_안함(self):
        docs = [{"doc_id": f"doc_{i}", "text": f"텍스트{i}"} for i in range(10)]
        result = diversify_documents(docs, k=3)
        assert len(result) <= 3

    def test_빈_리스트_입력(self):
        assert diversify_documents([], k=5) == []

    def test_k보다_적은_문서(self):
        docs = [{"doc_id": "doc_1", "text": "텍스트"}]
        result = diversify_documents(docs, k=5)
        assert len(result) == 1


class TestConvertResults:

    def test_langchain_document_딕셔너리_변환(self):
        mock_doc = MagicMock()
        mock_doc.page_content = "뉴스 본문"
        mock_doc.metadata = {
            "doc_id": "doc_001",
            "title": "삼성전자 뉴스",
            "company": "삼성전자",
            "url": "https://example.com",
        }

        result = _convert_results([mock_doc])
        assert len(result) == 1
        assert result[0]["doc_id"] == "doc_001"
        assert result[0]["title"] == "삼성전자 뉴스"
        assert result[0]["text"] == "뉴스 본문"

    def test_메타데이터_없어도_에러_없음(self):
        mock_doc = MagicMock()
        mock_doc.page_content = "본문"
        mock_doc.metadata = {}
        result = _convert_results([mock_doc])
        assert result[0]["doc_id"] is None

    def test_빈_리스트(self):
        assert _convert_results([]) == []


class TestRetrieveDocuments:

    def _make_mock_doc(self, doc_id: str, company: str, text: str):
        doc = MagicMock()
        doc.page_content = text
        doc.metadata = {"doc_id": doc_id, "company": company, "title": f"{company} 뉴스"}
        return doc

    @patch("app.retrieval.retriever.search_chunk_documents")
    def test_company_포함된_문서_반환(self, mock_search):
        mock_search.return_value = [
            self._make_mock_doc("doc_1", "삼성전자", "삼성전자 HBM 수요 증가"),
        ]
        result = retrieve_documents("투자포인트", company="삼성전자", k=5)
        assert len(result) == 1
        assert result[0]["company"] == "삼성전자"

    @patch("app.retrieval.retriever.search_chunk_documents")
    def test_company_없으면_전체_검색(self, mock_search):
        mock_search.return_value = [
            self._make_mock_doc("doc_1", "삼성전자", "뉴스 본문"),
            self._make_mock_doc("doc_2", "SK하이닉스", "뉴스 본문"),
        ]
        result = retrieve_documents("반도체 뉴스", company=None, k=5)
        assert len(result) == 2

    @patch("app.retrieval.retriever.search_chunk_documents")
    def test_결과_없으면_빈_리스트(self, mock_search):
        mock_search.return_value = []
        result = retrieve_documents("쿼리", company="존재하지않는기업", k=5)
        assert result == []

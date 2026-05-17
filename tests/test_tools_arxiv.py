"""tools/arxiv.py のユニットテスト。"""

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from tools.arxiv import ArxivError, fetch_paper, search_papers


def _make_mock_paper(
    paper_id: str = "2401.00001",
    title: str = "Test Paper",
    published_days_ago: int = 1,
) -> MagicMock:
    """モック用 arxiv.Result オブジェクトを生成する。"""
    paper = MagicMock()
    paper.get_short_id.return_value = paper_id
    paper.title = title
    paper.authors = [MagicMock(__str__=lambda self: "Alice")]
    paper.published = datetime.now(UTC) - timedelta(days=published_days_ago)
    paper.summary = "This is a test abstract about LLMs."
    paper.pdf_url = f"https://arxiv.org/pdf/{paper_id}"
    paper.categories = ["cs.AI", "cs.CL"]
    return paper


class TestSearchPapers:
    """search_papers の正常系・異常系テスト。"""

    @patch("tools.arxiv.arxiv.Client")
    def test_returns_list_of_papers(self, mock_client_cls):
        """クエリに対して論文リストを返す。"""
        mock_paper = _make_mock_paper()
        mock_client = MagicMock()
        mock_client.results.return_value = iter([mock_paper])
        mock_client_cls.return_value = mock_client

        results = search_papers("LLM agent", max_results=1)

        assert len(results) == 1
        assert results[0]["title"] == "Test Paper"
        assert results[0]["paper_id"] == "2401.00001"
        assert results[0]["url"] == "https://arxiv.org/abs/2401.00001"
        assert "cs.AI" in results[0]["categories"]

    @patch("tools.arxiv.arxiv.Client")
    def test_days_filter_excludes_old_papers(self, mock_client_cls):
        """--days フィルタで古い論文を除外する。"""
        old_paper = _make_mock_paper("2401.00001", "Old Paper", published_days_ago=30)
        recent_paper = _make_mock_paper("2401.00002", "Recent Paper", published_days_ago=1)

        mock_client = MagicMock()
        mock_client.results.return_value = iter([old_paper, recent_paper])
        mock_client_cls.return_value = mock_client

        results = search_papers("LLM", days=7)

        titles = [r["title"] for r in results]
        assert "Recent Paper" in titles
        assert "Old Paper" not in titles

    @patch("tools.arxiv.arxiv.Client")
    def test_empty_results(self, mock_client_cls):
        """検索結果が0件の場合は空リストを返す。"""
        mock_client = MagicMock()
        mock_client.results.return_value = iter([])
        mock_client_cls.return_value = mock_client

        results = search_papers("nonexistent_query_xyz")

        assert results == []

    @patch("tools.arxiv.arxiv.Client")
    def test_api_error_raises(self, mock_client_cls):
        """API呼び出し失敗時にArxivErrorを送出する。"""
        mock_client = MagicMock()
        mock_client.results.side_effect = RuntimeError("connection error")
        mock_client_cls.return_value = mock_client

        with pytest.raises(ArxivError):
            search_papers("LLM")


class TestFetchPaper:
    """fetch_paper の正常系・異常系テスト。"""

    @patch("tools.arxiv.arxiv.Client")
    def test_fetch_by_id(self, mock_client_cls):
        """IDで論文を1件取得できる。"""
        mock_paper = _make_mock_paper("2401.00001", "Specific Paper")
        mock_client = MagicMock()
        mock_client.results.return_value = iter([mock_paper])
        mock_client_cls.return_value = mock_client

        result = fetch_paper("2401.00001")

        assert result["paper_id"] == "2401.00001"
        assert result["title"] == "Specific Paper"
        assert "Alice" in result["authors"]

    @patch("tools.arxiv.arxiv.Client")
    def test_not_found_raises(self, mock_client_cls):
        """論文が存在しない場合はArxivErrorを送出する。"""
        mock_client = MagicMock()
        mock_client.results.return_value = iter([])
        mock_client_cls.return_value = mock_client

        with pytest.raises(ArxivError, match="見つかりません"):
            fetch_paper("9999.99999")

    @patch("tools.arxiv.arxiv.Client")
    def test_api_error_raises(self, mock_client_cls):
        """API呼び出し失敗時にArxivErrorを送出する。"""
        mock_client = MagicMock()
        mock_client.results.side_effect = RuntimeError("timeout")
        mock_client_cls.return_value = mock_client

        with pytest.raises(ArxivError):
            fetch_paper("2401.00001")

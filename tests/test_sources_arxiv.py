"""sources/arxiv.py のユニットテスト。"""

from datetime import UTC, datetime
from unittest.mock import patch

from sources.arxiv import ArxivSource


class TestArxivSourceFetch:
    """ArxivSource.fetch の正常系・異常系テスト。"""

    def _make_paper(
        self,
        paper_id: str = "2401.00001",
        title: str = "Test LLM Paper",
        published: str = "2026-01-01",
    ) -> dict:
        """ダミー PaperResult を生成する。"""
        return {
            "paper_id": paper_id,
            "title": title,
            "authors": ["Alice Smith", "Bob Jones"],
            "published": published,
            "abstract": "This paper proposes a new method for LLM reasoning.",
            "url": f"https://arxiv.org/abs/{paper_id}",
            "pdf_url": f"https://arxiv.org/pdf/{paper_id}",
            "categories": ["cs.AI", "cs.CL"],
        }

    @patch("sources.arxiv.search_papers")
    def test_fetch_returns_markdown(self, mock_search):
        """正常ケース: 論文リストをMarkdownで返す。"""
        mock_search.return_value = [self._make_paper()]
        source = ArxivSource()
        cutoff = datetime.now(UTC)

        md, latest_seen = source.fetch(
            {"query": "LLM reasoning", "days": 7}, cutoff
        )

        assert "arXiv" in md
        assert "Test LLM Paper" in md
        assert "https://arxiv.org/abs/2401.00001" in md
        assert latest_seen == {}

    @patch("sources.arxiv.search_papers")
    def test_fetch_empty_results(self, mock_search):
        """論文0件の場合は「該当なし」メッセージを返す。"""
        mock_search.return_value = []
        source = ArxivSource()
        md, _ = source.fetch({"query": "no-match-xyz"}, datetime.now(UTC))

        assert "該当論文なし" in md

    @patch("sources.arxiv.search_papers")
    def test_fetch_api_error_returns_error_md(self, mock_search):
        """API エラー時はエラーメッセージ入りMarkdownを返す（例外を外に出さない）。"""
        from tools.arxiv import ArxivError
        mock_search.side_effect = ArxivError("connection failed")
        source = ArxivSource()
        md, _ = source.fetch({"query": "LLM"}, datetime.now(UTC))

        assert "エラー" in md

    @patch("sources.arxiv.fetch_paper")
    def test_fetch_by_paper_id(self, mock_fetch_paper):
        """paper_id 指定時は fetch_paper() を呼ぶ。"""
        mock_fetch_paper.return_value = self._make_paper("2401.99999", "Specific Paper")
        source = ArxivSource()
        md, _ = source.fetch({"paper_id": "2401.99999"}, datetime.now(UTC))

        assert "Specific Paper" in md
        mock_fetch_paper.assert_called_once_with("2401.99999")

    @patch("sources.arxiv.search_papers")
    def test_fetch_markdown_structure(self, mock_search):
        """Markdownが ### 見出し構造を持つ。"""
        mock_search.return_value = [
            self._make_paper("2401.00001", "Paper A"),
            self._make_paper("2401.00002", "Paper B"),
        ]
        source = ArxivSource()
        md, _ = source.fetch({"query": "LLM"}, datetime.now(UTC))

        assert "### 1. Paper A" in md
        assert "### 2. Paper B" in md
        assert "- URL:" in md
        assert "- Abstract:" in md

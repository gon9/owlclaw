"""sources/gmail.py の単体テスト。"""

import sys
from datetime import UTC, datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

PROJ = Path(__file__).parent.parent
sys.path.insert(0, str(PROJ))
sys.path.insert(0, str(PROJ / "sources"))

from sources.gmail import GmailSource, _extract_headers  # noqa: E402

JST = timezone(datetime.now(UTC).astimezone().utcoffset())


def _make_msg(email_id: str, subject: str, from_: str, date_str: str, snippet: str,
              internal_date_ms: int) -> dict:
    """テスト用 Gmail メッセージオブジェクトを生成する。"""
    return {
        "id": email_id,
        "snippet": snippet,
        "internalDate": str(internal_date_ms),
        "payload": {
            "headers": [
                {"name": "From", "value": from_},
                {"name": "Subject", "value": subject},
                {"name": "Date", "value": date_str},
            ]
        },
    }


class TestExtractHeaders:
    """_extract_headers() のテスト。"""

    def test_全ヘッダーを抽出する(self):
        msg = {
            "payload": {
                "headers": [
                    {"name": "From", "value": "Amazon <noreply@amazon.co.jp>"},
                    {"name": "Subject", "value": "ご注文確認"},
                    {"name": "Date", "value": "Mon, 28 Apr 2026 10:00:00 +0900"},
                ]
            }
        }
        result = _extract_headers(msg)
        assert result["from"] == "Amazon <noreply@amazon.co.jp>"
        assert result["subject"] == "ご注文確認"
        assert result["date"] == "Mon, 28 Apr 2026 10:00:00 +0900"

    def test_存在しないヘッダーは空文字(self):
        msg = {"payload": {"headers": []}}
        result = _extract_headers(msg)
        assert result.get("from", "") == ""
        assert result.get("subject", "") == ""

    def test_payloadがない場合は空辞書(self):
        msg = {}
        result = _extract_headers(msg)
        assert result == {}


class TestGmailSource:
    """GmailSource.fetch() のテスト。"""

    BASE_CONFIG = {
        "query": "from:amazon newer_than:7d",
        "max_results": 100,
        "__seen_email_ids__": [],
    }

    @patch("sources.gmail._build_service")
    def test_新着メールなしの場合はヘッダーのみ返す(self, mock_build):
        service = MagicMock()
        service.users().messages().list().execute.return_value = {"messages": []}
        mock_build.return_value = service

        cutoff = datetime(2026, 4, 21, tzinfo=UTC)
        markdown, state_patch = GmailSource().fetch(self.BASE_CONFIG, cutoff)

        assert "Gmail 決済メール" in markdown
        assert "新着: 0 件" in markdown
        assert state_patch == {"__gmail_seen_ids__": []}

    @patch("sources.gmail._build_service")
    def test_新着メールを取得しIDリストを返す(self, mock_build):
        msg = _make_msg(
            email_id="msg001",
            subject="Amazonからのご注文確認",
            from_="noreply@amazon.co.jp",
            date_str="Mon, 28 Apr 2026 10:00:00 +0900",
            snippet="¥3,480 のお買い物",
            internal_date_ms=int(datetime(2026, 4, 28, 1, 0, tzinfo=UTC).timestamp() * 1000),
        )
        service = MagicMock()
        service.users().messages().list().execute.return_value = {"messages": [{"id": "msg001"}]}
        service.users().messages().get().execute.return_value = msg
        mock_build.return_value = service

        cutoff = datetime(2026, 4, 27, tzinfo=UTC)
        markdown, state_patch = GmailSource().fetch(self.BASE_CONFIG, cutoff)

        assert "Amazonからのご注文確認" in markdown
        assert "msg001" in state_patch["__gmail_seen_ids__"]

    @patch("sources.gmail._build_service")
    def test_既読IDはスキップされる(self, mock_build):
        service = MagicMock()
        service.users().messages().list().execute.return_value = {"messages": [{"id": "seen001"}]}
        mock_build.return_value = service

        config = dict(self.BASE_CONFIG)
        config["__seen_email_ids__"] = ["seen001"]

        cutoff = datetime(2026, 4, 27, tzinfo=UTC)
        markdown, state_patch = GmailSource().fetch(config, cutoff)

        assert state_patch["__gmail_seen_ids__"] == []
        assert "新着: 0 件" in markdown
        service.users().messages().get.assert_not_called()

    @patch("sources.gmail._build_service")
    def test_cutoff以前のメールは除外される(self, mock_build):
        old_msg = _make_msg(
            email_id="old001",
            subject="古いメール",
            from_="noreply@amazon.co.jp",
            date_str="Mon, 14 Apr 2026 10:00:00 +0900",
            snippet="¥1,000",
            internal_date_ms=int(datetime(2026, 4, 14, 1, 0, tzinfo=UTC).timestamp() * 1000),
        )
        service = MagicMock()
        service.users().messages().list().execute.return_value = {"messages": [{"id": "old001"}]}
        service.users().messages().get().execute.return_value = old_msg
        mock_build.return_value = service

        cutoff = datetime(2026, 4, 21, tzinfo=UTC)
        markdown, state_patch = GmailSource().fetch(self.BASE_CONFIG, cutoff)

        assert "古いメール" not in markdown
        assert state_patch["__gmail_seen_ids__"] == []

    @patch("sources.gmail._build_service")
    def test_認証エラー時はエラーメッセージのMarkdownと空dictを返す(self, mock_build):
        mock_build.side_effect = RuntimeError("トークン期限切れ")

        cutoff = datetime(2026, 4, 27, tzinfo=UTC)
        markdown, state_patch = GmailSource().fetch(self.BASE_CONFIG, cutoff)

        assert "認証エラー" in markdown
        assert state_patch == {}

    @patch("sources.gmail._build_service")
    def test_APIエラー時はエラーメッセージのMarkdownと空dictを返す(self, mock_build):
        service = MagicMock()
        service.users().messages().list().execute.side_effect = Exception("API quota exceeded")
        mock_build.return_value = service

        cutoff = datetime(2026, 4, 27, tzinfo=UTC)
        markdown, state_patch = GmailSource().fetch(self.BASE_CONFIG, cutoff)

        assert "API エラー" in markdown
        assert state_patch == {}

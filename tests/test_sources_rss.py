"""
sources/rss.py のユニットテスト。

正常系・異常系をモジュール単位で検証する。
"""

import sys
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from sources.rss import RssSource, _clean, _fetch_feed, _parse_pub_date


class TestClean:
    """_clean() のテスト。"""

    def test_htmlタグを除去する(self):
        assert _clean("<b>Hello</b>") == "Hello"

    def test_htmlエンティティをデコードする(self):
        assert _clean("&amp;") == "&"
        assert _clean("&lt;p&gt;") == ""  # decode後にタグとして除去される

    def test_空白を正規化する(self):
        assert _clean("  foo   bar  ") == "foo bar"

    def test_空文字はそのまま返す(self):
        assert _clean("") == ""

    def test_タグとエンティティの混合(self):
        assert _clean("<p>AI &amp; ML</p>") == "AI & ML"


class TestParsePubDate:
    """_parse_pub_date() のテスト。"""

    def test_rfc2822形式を変換する(self):
        dt = _parse_pub_date("Mon, 28 Apr 2026 12:00:00 +0000")
        assert dt is not None
        assert dt.year == 2026
        assert dt.tzinfo is not None

    def test_iso形式を変換する(self):
        dt = _parse_pub_date("2026-04-28T12:00:00")
        assert dt is not None
        assert dt.year == 2026

    def test_iso形式_タイムゾーン付きZ(self):
        dt = _parse_pub_date("2026-04-28T12:00:00Z")
        assert dt is not None

    def test_空文字はNoneを返す(self):
        assert _parse_pub_date("") is None

    def test_不正な文字列はNoneを返す(self):
        assert _parse_pub_date("not-a-date") is None

    def test_タイムゾーンなしはUTCとして補完する(self):
        dt = _parse_pub_date("2026-04-28T12:00:00")
        assert dt is not None
        assert dt.tzinfo == UTC


class TestFetchFeed:
    """_fetch_feed() のテスト。"""

    RSS_XML = b"""<?xml version="1.0"?>
<rss version="2.0">
  <channel>
    <item>
      <title>Test Article</title>
      <link>https://example.com/1</link>
      <description>Short description here.</description>
      <pubDate>Mon, 28 Apr 2026 09:00:00 +0000</pubDate>
    </item>
    <item>
      <title>Old Article</title>
      <link>https://example.com/0</link>
      <description>Very old content.</description>
      <pubDate>Mon, 01 Jan 2024 09:00:00 +0000</pubDate>
    </item>
  </channel>
</rss>"""

    ATOM_XML = b"""<?xml version="1.0"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <title>Atom Entry</title>
    <link href="https://example.com/atom/1"/>
    <summary>Atom summary text.</summary>
    <updated>2026-04-28T09:00:00Z</updated>
  </entry>
</feed>"""

    def _mock_urlopen(self, content: bytes):
        """urllib.request.urlopen をモック化するヘルパー。"""
        ctx = MagicMock()
        ctx.__enter__ = MagicMock(return_value=MagicMock(read=MagicMock(return_value=content)))
        ctx.__exit__ = MagicMock(return_value=False)
        return ctx

    @patch("sources.rss.urllib.request.urlopen")
    def test_rssフィードから記事を取得する(self, mock_urlopen):
        mock_urlopen.return_value = self._mock_urlopen(self.RSS_XML)
        cutoff = datetime(2026, 4, 27, tzinfo=UTC)
        items = _fetch_feed("https://example.com/feed", "Test", cutoff)
        assert len(items) == 1
        assert items[0]["title"] == "Test Article"
        assert items[0]["url"] == "https://example.com/1"

    @patch("sources.rss.urllib.request.urlopen")
    def test_atomフィードから記事を取得する(self, mock_urlopen):
        mock_urlopen.return_value = self._mock_urlopen(self.ATOM_XML)
        cutoff = datetime(2026, 4, 27, tzinfo=UTC)
        items = _fetch_feed("https://example.com/feed", "Atom", cutoff)
        assert len(items) == 1
        assert items[0]["title"] == "Atom Entry"

    @patch("sources.rss.urllib.request.urlopen")
    def test_cutoff以前の記事は除外される(self, mock_urlopen):
        mock_urlopen.return_value = self._mock_urlopen(self.RSS_XML)
        cutoff = datetime(2026, 4, 29, tzinfo=UTC)
        items = _fetch_feed("https://example.com/feed", "Test", cutoff)
        assert len(items) == 0

    @patch("sources.rss.urllib.request.urlopen", side_effect=Exception("connection refused"))
    def test_ネットワークエラー時は空リストを返す(self, mock_urlopen):
        cutoff = datetime(2026, 4, 27, tzinfo=UTC)
        items = _fetch_feed("https://example.com/feed", "Test", cutoff)
        assert items == []

    @patch("sources.rss.urllib.request.urlopen")
    def test_xmlパースエラー時は空リストを返す(self, mock_urlopen):
        mock_urlopen.return_value = self._mock_urlopen(b"not valid xml!!!<>")
        cutoff = datetime(2026, 4, 27, tzinfo=UTC)
        items = _fetch_feed("https://example.com/feed", "Test", cutoff)
        assert items == []


class TestRssSource:
    """RssSource.fetch() のテスト。"""

    MINIMAL_CONFIG = {
        "digest": {"lookback_hours": 24, "persona": "テスト読者。"},
        "sources": [],
    }

    def test_ソースが空の場合はヘッダーのみ返す(self):
        cutoff = datetime(2026, 4, 28, tzinfo=UTC)
        result = RssSource().fetch(self.MINIMAL_CONFIG, cutoff)
        assert "owlclaw digest input" in result
        assert "合計 0 件" in result

    def test_disabled_ソースはスキップされる(self):
        config = {
            "digest": {"lookback_hours": 24, "persona": "テスト。"},
            "sources": [
                {"name": "Disabled", "url": "https://example.com/feed", "enabled": False}
            ],
        }
        cutoff = datetime(2026, 4, 28, tzinfo=UTC)
        result = RssSource().fetch(config, cutoff)
        assert "Disabled" not in result

    @patch("sources.rss._fetch_feed", return_value=[])
    def test_取得0件ソースは取得できませんでしたと表示(self, mock_fetch):
        config = {
            "digest": {"lookback_hours": 24, "persona": "テスト。"},
            "sources": [{"name": "TestFeed", "url": "https://example.com/feed", "enabled": True}],
        }
        cutoff = datetime(2026, 4, 28, tzinfo=UTC)
        result = RssSource().fetch(config, cutoff)
        assert "取得できませんでした" in result

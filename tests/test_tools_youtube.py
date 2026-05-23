"""tools/youtube.py のユニットテスト。"""

from unittest.mock import MagicMock, patch

import pytest

from tools.youtube import (
    TranscriptError,
    extract_video_id,
    fetch_transcript,
    fetch_transcript_from_url,
)


class TestExtractVideoId:
    """extract_video_id の正常系・異常系テスト。"""

    def test_standard_url(self):
        """通常のYouTube URLからvideo_idを抽出できる。"""
        assert extract_video_id("https://www.youtube.com/watch?v=dQw4w9WgXcQ") == "dQw4w9WgXcQ"

    def test_short_url(self):
        """短縮URL (youtu.be) からvideo_idを抽出できる。"""
        assert extract_video_id("https://youtu.be/dQw4w9WgXcQ") == "dQw4w9WgXcQ"

    def test_mobile_url(self):
        """モバイルURL (m.youtube.com) からvideo_idを抽出できる。"""
        assert extract_video_id("https://m.youtube.com/watch?v=dQw4w9WgXcQ") == "dQw4w9WgXcQ"

    def test_embed_url(self):
        """埋め込みURL (/embed/) からvideo_idを抽出できる。"""
        assert extract_video_id("https://www.youtube.com/embed/dQw4w9WgXcQ") == "dQw4w9WgXcQ"

    def test_shorts_url(self):
        """Shorts URL (/shorts/) からvideo_idを抽出できる。"""
        assert extract_video_id("https://www.youtube.com/shorts/dQw4w9WgXcQ") == "dQw4w9WgXcQ"

    def test_raw_video_id(self):
        """11文字のvideo_idをそのまま渡せる。"""
        assert extract_video_id("dQw4w9WgXcQ") == "dQw4w9WgXcQ"

    def test_short_url_with_query(self):
        """youtu.be URLにクエリパラメータが付いていても正しく抽出できる。"""
        assert extract_video_id("https://youtu.be/dQw4w9WgXcQ?t=42") == "dQw4w9WgXcQ"

    def test_invalid_url_raises(self):
        """video_idを抽出できないURLはTranscriptErrorを送出する。"""
        with pytest.raises(TranscriptError):
            extract_video_id("https://example.com/not-youtube")

    def test_empty_string_raises(self):
        """空文字列はTranscriptErrorを送出する。"""
        with pytest.raises(TranscriptError):
            extract_video_id("")


def _make_mock_snippet(text: str, start: float = 0.0, duration: float = 1.0) -> MagicMock:
    """モック用 FetchedTranscriptSnippet を生成する。"""
    snip = MagicMock()
    snip.text = text
    snip.start = start
    snip.duration = duration
    return snip


def _make_mock_fetched(snippets: list, language_code: str = "en") -> MagicMock:
    """モック用 FetchedTranscript を生成する。"""
    fetched = MagicMock()
    fetched.language_code = language_code
    fetched.__iter__ = MagicMock(return_value=iter(snippets))
    return fetched


class TestFetchTranscript:
    """fetch_transcript の正常系・異常系テスト（モック使用）。"""

    @patch("tools.youtube.YouTubeTranscriptApi")
    def test_fetch_success_english(self, mock_cls):
        """英語字幕を正常に取得できる。"""
        snippets = [
            _make_mock_snippet("Hello world", 0.0, 1.5),
            _make_mock_snippet("This is a test", 1.5, 2.0),
        ]
        mock_fetched = _make_mock_fetched(snippets, "en")
        mock_cls.return_value.fetch.return_value = mock_fetched

        result = fetch_transcript("dQw4w9WgXcQ", languages=["en"])

        assert result["video_id"] == "dQw4w9WgXcQ"
        assert result["language"] == "en"
        assert "Hello world" in result["text"]
        assert len(result["segments"]) == 2
        assert result["char_count"] > 0

    @patch("tools.youtube.YouTubeTranscriptApi")
    def test_fetch_success_japanese(self, mock_cls):
        """日本語字幕を正常に取得できる。"""
        snippets = [_make_mock_snippet("テストです", 0.0, 2.0)]
        mock_fetched = _make_mock_fetched(snippets, "ja")
        mock_cls.return_value.fetch.return_value = mock_fetched

        result = fetch_transcript("dQw4w9WgXcQ", languages=["ja"])

        assert result["language"] == "ja"
        assert "テストです" in result["text"]

    @patch("tools.youtube.YouTubeTranscriptApi")
    def test_transcripts_disabled_raises(self, mock_cls):
        """字幕無効化時にTranscriptErrorを送出する。"""
        from youtube_transcript_api import TranscriptsDisabled

        mock_cls.return_value.fetch.side_effect = TranscriptsDisabled("dQw4w9WgXcQ")

        with pytest.raises(TranscriptError, match="字幕が無効化"):
            fetch_transcript("dQw4w9WgXcQ")

    @patch("tools.youtube.YouTubeTranscriptApi")
    def test_video_unavailable_raises(self, mock_cls):
        """動画不可時にTranscriptErrorを送出する。"""
        from youtube_transcript_api import VideoUnavailable

        mock_cls.return_value.fetch.side_effect = VideoUnavailable("dQw4w9WgXcQ")

        with pytest.raises(TranscriptError, match="動画が利用不可"):
            fetch_transcript("dQw4w9WgXcQ")


class TestFetchTranscriptFromUrl:
    """fetch_transcript_from_url の統合テスト（モック使用）。"""

    @patch("tools.youtube.fetch_transcript")
    def test_url_dispatches_to_fetch(self, mock_fetch):
        """URLからvideo_idを抽出してfetch_transcriptを呼ぶ。"""
        mock_fetch.return_value = {
            "video_id": "dQw4w9WgXcQ",
            "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "text": "test",
            "segments": [],
            "language": "en",
            "char_count": 4,
        }
        fetch_transcript_from_url("https://youtu.be/dQw4w9WgXcQ")
        mock_fetch.assert_called_once_with("dQw4w9WgXcQ", languages=None)

    def test_invalid_url_raises(self):
        """無効なURLはTranscriptErrorを送出する。"""
        with pytest.raises(TranscriptError):
            fetch_transcript_from_url("https://example.com")

"""sources/podcast.py のユニットテスト。"""

from datetime import UTC, datetime
from unittest.mock import patch

from sources.podcast import PodcastSource


class TestPodcastSourceFetch:
    """PodcastSource.fetch の正常系・異常系テスト。"""

    _DUMMY_TRANSCRIPT = {
        "video_id": "dQw4w9WgXcQ",
        "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "text": "This is a test transcript about LLMs and AI agents.",
        "segments": [],
        "language": "en",
        "char_count": 51,
    }

    def _cutoff(self) -> datetime:
        return datetime.now(UTC)

    @patch("sources.podcast.summarize")
    @patch("sources.podcast.fetch_transcript_from_url")
    def test_fetch_success(self, mock_fetch, mock_summarize):
        """正常ケース: 字幕取得・要約してMarkdownを返す。"""
        mock_fetch.return_value = self._DUMMY_TRANSCRIPT
        mock_summarize.return_value = "• LLMエージェントの重要性\n• FDE視点での応用"

        config = {
            "urls": ["https://www.youtube.com/watch?v=dQw4w9WgXcQ"],
            "languages": ["en"],
        }
        source = PodcastSource()
        md, latest_seen = source.fetch(config, self._cutoff())

        assert "Podcast/YouTube" in md
        assert "dQw4w9WgXcQ" in md or "youtube.com" in md
        assert "LLMエージェント" in md
        assert latest_seen == {}

    def test_fetch_no_urls(self):
        """URLが空の場合は「URLが設定されていません」メッセージを返す。"""
        source = PodcastSource()
        md, _ = source.fetch({"urls": []}, self._cutoff())

        assert "URLが設定されていません" in md

    @patch("sources.podcast.fetch_transcript_from_url")
    def test_fetch_transcript_error_continues(self, mock_fetch):
        """字幕取得エラーでも処理を続け、エラー情報をMarkdownに含める。"""
        from tools.youtube import TranscriptError
        mock_fetch.side_effect = TranscriptError("字幕が無効化されています")

        config = {"urls": ["https://youtu.be/ERROR_VIDEO"]}
        source = PodcastSource()
        md, _ = source.fetch(config, self._cutoff())

        assert "字幕取得失敗" in md or "Error" in md

    @patch("sources.podcast.summarize")
    @patch("sources.podcast.fetch_transcript_from_url")
    def test_fetch_summarize_error_continues(self, mock_fetch, mock_summarize):
        """要約エラーでも処理を続け、エラー情報をMarkdownに含める。"""
        from tools.summarize import SummarizeError
        mock_fetch.return_value = self._DUMMY_TRANSCRIPT
        mock_summarize.side_effect = SummarizeError("Claude CLI不可")

        config = {"urls": ["https://www.youtube.com/watch?v=dQw4w9WgXcQ"]}
        source = PodcastSource()
        md, _ = source.fetch(config, self._cutoff())

        assert "要約失敗" in md or "Error" in md

    @patch("sources.podcast.summarize")
    @patch("sources.podcast.fetch_transcript_from_url")
    def test_fetch_multiple_urls(self, mock_fetch, mock_summarize):
        """複数URL処理時に全件がMarkdownに含まれる。"""
        mock_fetch.return_value = self._DUMMY_TRANSCRIPT
        mock_summarize.return_value = "要約テキスト"

        urls = [
            "https://youtu.be/VIDEO1",
            "https://youtu.be/VIDEO2",
        ]
        source = PodcastSource()
        md, _ = source.fetch({"urls": urls}, self._cutoff())

        assert "### 1." in md
        assert "### 2." in md

    @patch("sources.podcast.summarize")
    @patch("sources.podcast.fetch_transcript_from_url")
    def test_context_passed_to_summarize(self, mock_fetch, mock_summarize):
        """config の context が summarize() に渡される。"""
        mock_fetch.return_value = self._DUMMY_TRANSCRIPT
        mock_summarize.return_value = "要約"
        custom_context = "カスタムコンテキスト"

        config = {
            "urls": ["https://youtu.be/VIDEO"],
            "context": custom_context,
        }
        source = PodcastSource()
        source.fetch(config, self._cutoff())

        _, call_kwargs = mock_summarize.call_args
        assert mock_summarize.call_args[1].get("context") == custom_context or \
               mock_summarize.call_args[0][1] == custom_context

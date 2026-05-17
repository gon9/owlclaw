"""tools/summarize.py のユニットテスト。"""

from unittest.mock import patch

import pytest

from tools.summarize import SummarizeError, summarize


class TestSummarize:
    """summarize の正常系・異常系テスト。"""

    @patch("tools.summarize._invoke_claude")
    def test_short_text_single_call(self, mock_claude):
        """chunk_size以内のテキストはClaude CLIを1回だけ呼ぶ。"""
        mock_claude.return_value = "要約結果です。"

        result = summarize("短いテキストです。", chunk_size=1000)

        assert result == "要約結果です。"
        mock_claude.assert_called_once()

    @patch("tools.summarize._invoke_claude")
    def test_long_text_map_reduce(self, mock_claude):
        """chunk_sizeを超えるテキストはClaude CLIを複数回呼びmap-reduceの最終要約を返す。"""
        call_log: list[str] = []

        def fake_claude(prompt: str) -> str:
            call_log.append(prompt)
            return "最終統合要約" if "各チャンクの要約" in prompt else "チャンク要約"

        mock_claude.side_effect = fake_claude

        long_text = "あ" * 500
        result = summarize(long_text, chunk_size=200)

        assert result == "最終統合要約"
        assert mock_claude.call_count >= 2

    @patch("tools.summarize._invoke_claude")
    def test_context_passed_to_prompt(self, mock_claude):
        """contextがプロンプトに含まれる。"""
        mock_claude.return_value = "要約"
        custom_context = "特定の視点でまとめてください"

        summarize("テキスト", context=custom_context)

        call_args = mock_claude.call_args[0][0]
        assert custom_context in call_args

    def test_empty_text_raises(self):
        """空テキストはSummarizeErrorを送出する。"""
        with pytest.raises(SummarizeError, match="空"):
            summarize("")

    def test_whitespace_only_raises(self):
        """空白のみのテキストはSummarizeErrorを送出する。"""
        with pytest.raises(SummarizeError, match="空"):
            summarize("   \n\t  ")

    @patch("tools.summarize._invoke_claude")
    def test_claude_error_propagates(self, mock_claude):
        """Claude CLI失敗時にSummarizeErrorが伝播する。"""
        mock_claude.side_effect = SummarizeError("Claude CLI呼び出し失敗")

        with pytest.raises(SummarizeError):
            summarize("テキスト")

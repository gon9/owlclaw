"""tools/score.py のユニットテスト。"""

import json
from unittest.mock import patch

import pytest

from tools.score import ScoreError, _parse_json_output, score_batch, score_item


class TestParseJsonOutput:
    """_parse_json_output の正常系・異常系テスト。"""

    def test_clean_json(self):
        """クリーンなJSONを正しくパースする。"""
        raw = '{"score": 8, "reason": "重要", "tags": ["LLM"], "priority": "high"}'
        result = _parse_json_output(raw)
        assert result["score"] == 8

    def test_json_with_codeblock(self):
        """コードブロックで囲まれたJSONを正しくパースする。"""
        raw = '```json\n{"score": 7, "reason": "ok", "tags": [], "priority": "high"}\n```'
        result = _parse_json_output(raw)
        assert result["score"] == 7

    def test_json_with_surrounding_text(self):
        """前後にテキストが混入していてもJSONを抽出できる。"""
        raw = (
            'はい、以下が評価結果です:\n'
            '{"score": 5, "reason": "普通", "tags": [], "priority": "medium"}\n'
            '以上です。'
        )
        result = _parse_json_output(raw)
        assert result["score"] == 5

    def test_no_json_raises(self):
        """JSONが含まれない場合はScoreErrorを送出する。"""
        with pytest.raises(ScoreError, match="JSON"):
            _parse_json_output("JSONがありません")

    def test_invalid_json_raises(self):
        """不正なJSONはScoreErrorを送出する。"""
        with pytest.raises(ScoreError):
            _parse_json_output("{invalid json}")


class TestScoreItem:
    """score_item の正常系・異常系テスト。"""

    @patch("tools.score._invoke_claude")
    def test_high_score_item(self, mock_claude):
        """高スコアのコンテンツを正しくスコアリングする。"""
        mock_claude.return_value = json.dumps({
            "score": 9,
            "reason": "GPT-5リリースはFDE業務に直接影響する重大発表",
            "tags": ["LLM", "OpenAI", "モデル動向"],
            "priority": "high",
        })

        result = score_item({"title": "GPT-5 released", "text": "OpenAI announced..."})

        assert result["score"] == 9
        assert result["priority"] == "high"
        assert "LLM" in result["tags"]
        assert len(result["reason"]) > 0

    @patch("tools.score._invoke_claude")
    def test_low_score_item(self, mock_claude):
        """低スコアのコンテンツを正しく分類する。"""
        mock_claude.return_value = json.dumps({
            "score": 2,
            "reason": "既報のアップデートで新規性がない",
            "tags": ["既報"],
            "priority": "low",
        })

        result = score_item({"title": "Minor update", "text": "Small bug fix..."})

        assert result["score"] == 2
        assert result["priority"] == "low"

    @patch("tools.score._invoke_claude")
    def test_score_clamped_to_range(self, mock_claude):
        """スコアが1-10の範囲に収まる（範囲外はクランプ）。"""
        mock_claude.return_value = json.dumps({
            "score": 99,
            "reason": "範囲外スコア",
            "tags": [],
            "priority": "high",
        })

        result = score_item({"title": "test", "text": "test"})
        assert 1 <= result["score"] <= 10

    @patch("tools.score._invoke_claude")
    def test_invalid_priority_corrected(self, mock_claude):
        """不正なpriorityはスコアから自動補正する。"""
        mock_claude.return_value = json.dumps({
            "score": 8,
            "reason": "重要",
            "tags": [],
            "priority": "invalid_value",
        })

        result = score_item({"title": "test", "text": "test"})
        assert result["priority"] in ("high", "medium", "low")

    def test_empty_item_raises(self):
        """title・text両方空の場合はScoreErrorを送出する。"""
        with pytest.raises(ScoreError, match="必須"):
            score_item({"url": "https://example.com"})

    @patch("tools.score._invoke_claude")
    def test_long_text_truncated(self, mock_claude):
        """2000文字を超えるtextはプロンプトで切り詰められる。"""
        mock_claude.return_value = json.dumps({
            "score": 5, "reason": "ok", "tags": [], "priority": "medium"
        })
        long_text = "x" * 5000

        score_item({"title": "test", "text": long_text})

        prompt = mock_claude.call_args[0][0]
        assert len(prompt) < len(long_text) + 2000


class TestScoreBatch:
    """score_batch の正常系・異常系テスト。"""

    @patch("tools.score.score_item")
    def test_batch_all_success(self, mock_score_item):
        """全件スコアリング成功時に全結果を返す。"""
        mock_score_item.return_value = {
            "score": 7, "reason": "ok", "tags": [], "priority": "high"
        }
        items = [
            {"title": "A", "text": "aaa"},
            {"title": "B", "text": "bbb"},
        ]

        results = score_batch(items)

        assert len(results) == 2
        assert results[0]["title"] == "A"
        assert results[0]["score"] == 7

    @patch("tools.score.score_item")
    def test_batch_partial_failure(self, mock_score_item):
        """一部失敗してもバッチ全体は続行しscore=0で埋める。"""
        mock_score_item.side_effect = [
            {"score": 8, "reason": "ok", "tags": [], "priority": "high"},
            ScoreError("失敗"),
        ]
        items = [{"title": "A", "text": "aaa"}, {"title": "B", "text": "bbb"}]

        results = score_batch(items)

        assert len(results) == 2
        assert results[0]["score"] == 8
        assert results[1]["score"] == 0

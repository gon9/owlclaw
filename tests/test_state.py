"""
scripts/state.py のユニットテスト。

正常系・異常系をモジュール単位で検証する。
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import state


class TestLoad:
    """state.load() のテスト。"""

    def test_ファイルが存在しない場合は空辞書を返す(self, tmp_path, monkeypatch):
        monkeypatch.setattr(state, "_STATE_DIR", tmp_path)
        result = state.load("nonexistent")
        assert result == {}

    def test_既存JSONを辞書として読み込む(self, tmp_path, monkeypatch):
        monkeypatch.setattr(state, "_STATE_DIR", tmp_path)
        data = {"last_run": "2026-04-28T09:00:00", "count": 5}
        (tmp_path / "my-task.json").write_text(json.dumps(data), encoding="utf-8")
        result = state.load("my-task")
        assert result == data

    def test_日本語を含むデータを正しく読み込む(self, tmp_path, monkeypatch):
        monkeypatch.setattr(state, "_STATE_DIR", tmp_path)
        data = {"note": "テスト"}
        (tmp_path / "ns.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        result = state.load("ns")
        assert result["note"] == "テスト"


class TestSave:
    """state.save() のテスト。"""

    def test_辞書をJSONファイルに書き出す(self, tmp_path, monkeypatch):
        monkeypatch.setattr(state, "_STATE_DIR", tmp_path)
        data = {"last_run": "2026-04-28T09:00:00"}
        state.save("daily-digest", data)
        written = json.loads((tmp_path / "daily-digest.json").read_text(encoding="utf-8"))
        assert written == data

    def test_ディレクトリが存在しない場合でも作成する(self, tmp_path, monkeypatch):
        new_dir = tmp_path / "subdir" / "state"
        monkeypatch.setattr(state, "_STATE_DIR", new_dir)
        state.save("ns", {"x": 1})
        assert (new_dir / "ns.json").exists()

    def test_上書き保存できる(self, tmp_path, monkeypatch):
        monkeypatch.setattr(state, "_STATE_DIR", tmp_path)
        state.save("ns", {"v": 1})
        state.save("ns", {"v": 2})
        written = json.loads((tmp_path / "ns.json").read_text(encoding="utf-8"))
        assert written["v"] == 2

    def test_日本語を含むデータを正しく書き出す(self, tmp_path, monkeypatch):
        monkeypatch.setattr(state, "_STATE_DIR", tmp_path)
        state.save("ns", {"note": "テスト"})
        raw = (tmp_path / "ns.json").read_text(encoding="utf-8")
        assert "テスト" in raw

"""tools/upload_youtube.py のテスト。"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

# upload_youtube は google 系ライブラリを遅延 import しているのでモジュール自体は読み込める
from tools.upload_youtube import upload_to_youtube


def test_upload_raises_on_missing_file(tmp_path: Path) -> None:
    """存在しないファイルを指定すると FileNotFoundError になる。"""
    missing = tmp_path / "missing.mp4"
    with pytest.raises(FileNotFoundError):
        upload_to_youtube(missing, title="test")


def test_upload_raises_on_missing_token(tmp_path: Path, monkeypatch) -> None:
    """token.json が無い場合は RuntimeError になる。"""
    mp4 = tmp_path / "video.mp4"
    mp4.write_bytes(b"\x00" * 100)

    # TOKEN_PATH を存在しないパスに差し替え
    fake_token = tmp_path / "nonexistent_token.json"
    monkeypatch.setattr("tools.upload_youtube.TOKEN_PATH", fake_token)

    with pytest.raises(RuntimeError, match="認証"):
        upload_to_youtube(mp4, title="test")


def test_upload_returns_video_id(tmp_path: Path, monkeypatch) -> None:
    """正常系: upload 成功時に video_id と URL を返す。"""
    mp4 = tmp_path / "digest.mp4"
    mp4.write_bytes(b"\x00" * 100)

    fake_service = MagicMock()
    fake_request = MagicMock()
    fake_request.next_chunk.return_value = (None, {"id": "abc123xyz"})
    fake_service.videos.return_value.insert.return_value = fake_request

    monkeypatch.setattr(
        "tools.upload_youtube._build_service",
        lambda: fake_service,
    )

    result = upload_to_youtube(mp4, title="owlclaw AI Digest 2026-06-12")

    assert result["id"] == "abc123xyz"
    assert result["url"] == "https://www.youtube.com/watch?v=abc123xyz"

    # insert が正しい引数で呼ばれたか
    call_kwargs = fake_service.videos().insert.call_args
    body = call_kwargs.kwargs.get("body") or call_kwargs[1].get("body")
    assert body["snippet"]["title"] == "owlclaw AI Digest 2026-06-12"
    assert body["snippet"]["categoryId"] == "25"
    assert body["status"]["privacyStatus"] == "public"


def test_upload_custom_privacy(tmp_path: Path, monkeypatch) -> None:
    """privacy_status を指定できる。"""
    mp4 = tmp_path / "digest.mp4"
    mp4.write_bytes(b"\x00" * 100)

    fake_service = MagicMock()
    fake_request = MagicMock()
    fake_request.next_chunk.return_value = (None, {"id": "xyz789"})
    fake_service.videos.return_value.insert.return_value = fake_request

    monkeypatch.setattr(
        "tools.upload_youtube._build_service",
        lambda: fake_service,
    )

    result = upload_to_youtube(
        mp4,
        title="test",
        privacy_status="unlisted",
    )

    assert result["id"] == "xyz789"
    call_kwargs = fake_service.videos().insert.call_args
    body = call_kwargs.kwargs.get("body") or call_kwargs[1].get("body")
    assert body["status"]["privacyStatus"] == "unlisted"

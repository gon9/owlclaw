"""orchestrator の YouTube upload ディスパッチのテスト。"""

from __future__ import annotations

import importlib.util
import types
from pathlib import Path

PROJ = Path(__file__).parent.parent


def _load_orchestrator():
    spec = importlib.util.spec_from_file_location(
        "orchestrator_yt_test",
        PROJ / "scripts" / "orchestrator.py",
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


orchestrator = _load_orchestrator()


def test_youtube_upload_in_video_output(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """youtube_upload: true 時、YouTube にアップロードし Slack に URL が含まれる。"""
    task_dir = tmp_path / "video-digest"
    task_dir.mkdir()
    (task_dir / "slides.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(orchestrator, "_purge_old_videos", lambda *_: 0)
    monkeypatch.setattr(orchestrator.subprocess, "run", lambda *_, **__: None)
    monkeypatch.setitem(
        orchestrator.sys.modules,
        "scripts.check_video_digest",
        types.SimpleNamespace(validate_video_digest=lambda **_: []),
    )

    yt_url = "https://www.youtube.com/watch?v=testid123"

    def fake_yt_upload(path, title="", description="", privacy_status="public", **kw):
        return {"id": "testid123", "url": yt_url}

    monkeypatch.setitem(
        orchestrator.sys.modules,
        "tools.upload_youtube",
        type(
            "M",
            (),
            {"upload_to_youtube": staticmethod(fake_yt_upload)},
        )(),
    )

    orchestrator._dispatch_video_output(
        {
            "youtube_upload": True,
            "slack_notify": True,
        },
        task_dir,
        "2026-06-12",
    )

    slack_msg = (task_dir / "slack_video.txt").read_text(encoding="utf-8")
    assert yt_url in slack_msg
    assert "YouTube で再生" in slack_msg


def test_youtube_and_drive_both_in_slack(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """Drive + YouTube 両方有効時、Slack に両方の URL が含まれる。"""
    task_dir = tmp_path / "video-digest"
    task_dir.mkdir()
    (task_dir / "slides.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(orchestrator, "_purge_old_videos", lambda *_: 0)
    monkeypatch.setattr(orchestrator.subprocess, "run", lambda *_, **__: None)
    monkeypatch.setitem(
        orchestrator.sys.modules,
        "scripts.check_video_digest",
        types.SimpleNamespace(validate_video_digest=lambda **_: []),
    )

    drive_link = "https://drive.google.com/file/d/driveXYZ/view"
    yt_url = "https://www.youtube.com/watch?v=ytABC"

    def fake_drive_upload(_path, folder_path=""):
        return {"webViewLink": drive_link}

    def fake_yt_upload(path, title="", description="", privacy_status="public", **kw):
        return {"id": "ytABC", "url": yt_url}

    monkeypatch.setitem(
        orchestrator.sys.modules,
        "tools.upload_drive",
        type(
            "M",
            (),
            {"upload_to_drive": staticmethod(fake_drive_upload)},
        )(),
    )
    monkeypatch.setitem(
        orchestrator.sys.modules,
        "tools.upload_youtube",
        type(
            "M",
            (),
            {"upload_to_youtube": staticmethod(fake_yt_upload)},
        )(),
    )

    orchestrator._dispatch_video_output(
        {
            "drive_upload": True,
            "drive_folder": "owlclaw/video-digest",
            "youtube_upload": True,
            "slack_notify": True,
        },
        task_dir,
        "2026-06-12",
    )

    slack_msg = (task_dir / "slack_video.txt").read_text(encoding="utf-8")
    assert drive_link in slack_msg
    assert yt_url in slack_msg
    assert "Google Drive で再生" in slack_msg
    assert "YouTube で再生" in slack_msg


def test_build_youtube_description(tmp_path: Path) -> None:
    """_build_youtube_description が note_draft.md の見出しを抽出する。"""
    task_dir = tmp_path / "video-digest"
    task_dir.mkdir()
    note = task_dir / "note_draft.md"
    note.write_text(
        "# Daily Digest\n\n### 1. テスト記事\nsome content\n\n### 2. 別の記事\nmore",
        encoding="utf-8",
    )

    desc = orchestrator._build_youtube_description("2026-06-12", task_dir)
    assert "owlclaw AI Digest 2026-06-12" in desc
    assert "1. テスト記事" in desc
    assert "2. 別の記事" in desc
    assert "#owlclaw" in desc


def test_build_youtube_description_no_note(tmp_path: Path) -> None:
    """note_draft.md が無い場合でもエラーにならない。"""
    task_dir = tmp_path / "video-digest"
    task_dir.mkdir()

    desc = orchestrator._build_youtube_description("2026-06-12", task_dir)
    assert "owlclaw AI Digest 2026-06-12" in desc
    assert "#owlclaw" in desc

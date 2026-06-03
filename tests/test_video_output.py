"""動画ダイジェスト出力ディスパッチャの Slack 通知メッセージのテスト。

Obsidian Vault へのコピーは廃止され、Google Drive アップロードと Slack 通知のみが残った。
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

PROJ = Path(__file__).parent.parent


def _load_orchestrator():
    spec = importlib.util.spec_from_file_location(
        "orchestrator_video_test",
        PROJ / "scripts" / "orchestrator.py",
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


orchestrator = _load_orchestrator()


def test_video_slack_includes_drive_url_when_uploaded(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """Drive アップロード成功時、Slack メッセージに webViewLink が含まれる。"""
    task_dir = tmp_path / "video-digest"
    task_dir.mkdir()
    (task_dir / "slides.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(orchestrator, "_purge_old_videos", lambda *_: 0)
    monkeypatch.setattr(orchestrator.subprocess, "run", lambda *_, **__: None)

    drive_link = "https://drive.google.com/file/d/abc123/view"

    def fake_upload(_path, folder_path: str = ""):  # noqa: ARG001
        return {"webViewLink": drive_link}

    monkeypatch.setitem(
        orchestrator.sys.modules,
        "tools.upload_drive",
        type(
            "M",
            (),
            {"upload_to_drive": staticmethod(fake_upload)},
        )(),
    )

    orchestrator._dispatch_video_output(
        {
            "drive_upload": True,
            "drive_folder": "owlclaw/video-digest",
            "slack_notify": True,
        },
        task_dir,
        "2026-05-30",
    )

    slack_msg = (task_dir / "slack_video.txt").read_text(encoding="utf-8")
    assert drive_link in slack_msg
    assert "Google Drive で再生" in slack_msg


def test_video_slack_local_fallback_when_no_drive(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """Drive アップロード無効時はローカルパスで通知する。"""
    task_dir = tmp_path / "video-digest"
    task_dir.mkdir()
    (task_dir / "slides.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(orchestrator, "_purge_old_videos", lambda *_: 0)
    monkeypatch.setattr(orchestrator.subprocess, "run", lambda *_, **__: None)

    orchestrator._dispatch_video_output(
        {"slack_notify": True},
        task_dir,
        "2026-05-30",
    )

    slack_msg = (task_dir / "slack_video.txt").read_text(encoding="utf-8")
    assert "open '" in slack_msg
    assert str(task_dir) in slack_msg

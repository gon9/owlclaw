"""動画ダイジェストの同期先出力に関するテスト。"""

from __future__ import annotations

import importlib.util
import os
from datetime import UTC, datetime, timedelta
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


def test_publish_video_to_obsidian_copies_video_and_purges_old_files(
    tmp_path: Path,
    monkeypatch,
) -> None:
    vault = tmp_path / "vault"
    local_mp4 = tmp_path / "digest_20260530.mp4"
    local_mp4.write_bytes(b"new-video")
    video_dir = vault / "docs_obsidian" / "20_news" / "owlclaw" / "video"
    video_dir.mkdir(parents=True)
    old_mp4 = video_dir / "digest_20260501.mp4"
    old_mp4.write_bytes(b"old-video")
    old_mtime = (datetime.now(UTC) - timedelta(days=30)).timestamp()
    os.utime(old_mp4, (old_mtime, old_mtime))
    monkeypatch.setenv("OBSIDIAN_VAULT", str(vault))

    dest_mp4, relative_path = orchestrator._publish_video_to_obsidian(
        local_mp4,
        "owlclaw/video",
        retention_days=7,
    )

    assert dest_mp4.read_bytes() == b"new-video"
    assert relative_path == "owlclaw/video/digest_20260530.mp4"
    assert not old_mp4.exists()


def test_publish_video_to_obsidian_rejects_parent_directory_escape(
    tmp_path: Path,
    monkeypatch,
) -> None:
    local_mp4 = tmp_path / "digest_20260530.mp4"
    local_mp4.write_bytes(b"video")
    monkeypatch.setenv("OBSIDIAN_VAULT", str(tmp_path / "vault"))

    try:
        orchestrator._publish_video_to_obsidian(local_mp4, "../outside", retention_days=7)
    except ValueError as e:
        assert "Vault内の相対パス" in str(e)
    else:
        raise AssertionError("parent directory escape must be rejected")


def test_video_slack_fallback_uses_obsidian_relative_path(
    tmp_path: Path,
    monkeypatch,
) -> None:
    task_dir = tmp_path / "video-digest"
    task_dir.mkdir()
    (task_dir / "slides.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(orchestrator, "_purge_old_videos", lambda *_: 0)
    monkeypatch.setattr(
        orchestrator,
        "_publish_video_to_obsidian",
        lambda *_: (
            Path("/vault/docs_obsidian/20_news/owlclaw/video/digest_20260530.mp4"),
            "owlclaw/video/digest_20260530.mp4",
        ),
    )
    monkeypatch.setattr(orchestrator.subprocess, "run", lambda *_, **__: None)

    orchestrator._dispatch_video_output(
        {
            "obsidian_subdir": "owlclaw/video",
            "slack_notify": True,
        },
        task_dir,
        "2026-05-30",
    )

    slack_msg = (task_dir / "slack_video.txt").read_text(encoding="utf-8")
    assert "Obsidian: owlclaw/video/digest_20260530.mp4" in slack_msg
    assert str(task_dir) not in slack_msg

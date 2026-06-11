"""動画ダイジェスト出力ディスパッチャの Slack 通知メッセージのテスト。

Obsidian Vault へのコピーは廃止され、Google Drive アップロードと Slack 通知のみが残った。
"""

from __future__ import annotations

import importlib.util
import os
import types
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
    monkeypatch.setitem(
        orchestrator.sys.modules,
        "scripts.check_video_digest",
        types.SimpleNamespace(validate_video_digest=lambda **_: []),
    )

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
    monkeypatch.setitem(
        orchestrator.sys.modules,
        "scripts.check_video_digest",
        types.SimpleNamespace(validate_video_digest=lambda **_: []),
    )

    orchestrator._dispatch_video_output(
        {"slack_notify": True},
        task_dir,
        "2026-05-30",
    )

    slack_msg = (task_dir / "slack_video.txt").read_text(encoding="utf-8")
    assert "open '" in slack_msg
    assert str(task_dir) in slack_msg


def test_debug_slides_uploads_pngs_and_manifest(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """debug slides は音声/動画を作らず slides.json とPNGだけ Drive に upload する。"""
    task_dir = tmp_path / "video-digest"
    slides_dir = task_dir / "slides"
    slides_dir.mkdir(parents=True)
    slides_json = task_dir / "slides.json"
    slides_json.write_text("{}", encoding="utf-8")
    (slides_dir / "seg1.png").write_bytes(b"png1")
    (slides_dir / "seg2.png").write_bytes(b"png2")

    monkeypatch.setattr(
        orchestrator,
        "_render_and_validate_slides",
        lambda *_: [slides_dir / "seg1.png", slides_dir / "seg2.png"],
    )

    uploaded: list[tuple[str, str]] = []

    def fake_upload(path: Path, folder_path: str = ""):
        uploaded.append((path.name, folder_path))
        return {"webViewLink": f"https://drive.example/{path.name}"}

    monkeypatch.setitem(
        orchestrator.sys.modules,
        "tools.upload_drive",
        type(
            "M",
            (),
            {"upload_to_drive": staticmethod(fake_upload)},
        )(),
    )

    out = orchestrator._dispatch_debug_slides(
        {
            "outputs": [
                {
                    "type": "video",
                    "drive_folder": "owlclaw/video-digest",
                }
            ]
        },
        task_dir,
        "2026-06-11",
    )

    assert [name for name, _ in uploaded] == ["slides.json", "seg1.png", "seg2.png"]
    assert all("owlclaw/video-digest/debug-slides/2026-06-11-" in f for _, f in uploaded)
    text = out.read_text(encoding="utf-8")
    assert "https://drive.example/slides.json" in text
    assert "https://drive.example/seg2.png" in text


def test_retry_succeeds_after_transient_failures(monkeypatch) -> None:
    """_retry は一時的な例外が継続する場合にリトライして成功できる。"""

    calls = {"n": 0}

    def flaky() -> None:
        calls["n"] += 1
        if calls["n"] < 3:
            raise RuntimeError("transient")

    monkeypatch.setattr(orchestrator.time, "sleep", lambda *_: None)
    orchestrator._retry(flaky, label="test", max_attempts=3, base_delay_seconds=0)
    assert calls["n"] == 3


def test_purge_old_video_artifacts_deletes_old_files(tmp_path: Path) -> None:
    """retention_days を超えた mp4/png/wav をタスク実行時に削除できる。"""

    task_dir = tmp_path / "video-digest"
    task_dir.mkdir()
    (task_dir / "slides.json").write_text("{}", encoding="utf-8")

    slides_dir = task_dir / "slides"
    slides_dir.mkdir()
    audio_dir = task_dir / "audio"
    audio_dir.mkdir()

    old_mp4 = task_dir / "digest_20260501.mp4"
    old_png = slides_dir / "seg1.png"
    old_wav = audio_dir / "seg1.wav"
    old_mp4.write_bytes(b"x")
    old_png.write_bytes(b"x")
    old_wav.write_bytes(b"x")

    old_ts = (datetime.now(UTC) - timedelta(days=3)).timestamp()
    os.utime(old_mp4, (old_ts, old_ts))
    os.utime(old_png, (old_ts, old_ts))
    os.utime(old_wav, (old_ts, old_ts))

    orchestrator._purge_old_video_artifacts(task_dir, retention_days=1)

    assert not old_mp4.exists()
    assert not old_png.exists()
    assert not old_wav.exists()

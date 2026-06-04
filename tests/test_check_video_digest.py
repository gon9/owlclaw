"""scripts/check_video_digest.py の単体テスト。"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

PROJ = Path(__file__).parent.parent


def _load_check_video_digest():
    spec = importlib.util.spec_from_file_location(
        "check_video_digest",
        PROJ / "scripts" / "check_video_digest.py",
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["check_video_digest"] = module
    spec.loader.exec_module(module)
    return module


def _write_slides_json(task_dir: Path) -> None:
    task_dir.mkdir(parents=True)
    (task_dir / "slides.json").write_text(
        json.dumps(
            {
                "title": "OWLCLAW NEWS",
                "date": "2026-06-04",
                "slides": [
                    {
                        "id": "seg1",
                        "type": "hero",
                        "narration": "おはようございます。",
                    },
                    {
                        "id": "seg2",
                        "type": "concept",
                        "image_prompt": "Japanese business-news infographic slide",
                        "narration": "ニュースです。",
                    },
                    {
                        "id": "seg3",
                        "type": "closing",
                        "narration": "以上です。",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )


def _write_complete_artifacts(task_dir: Path) -> None:
    slides_dir = task_dir / "slides"
    audio_dir = task_dir / "audio"
    slides_dir.mkdir()
    audio_dir.mkdir()
    for slide_id in ("seg1", "seg2", "seg3"):
        (slides_dir / f"{slide_id}.png").write_bytes(b"png")
        (audio_dir / f"{slide_id}.wav").write_bytes(b"wav")
    (slides_dir / "seg2.codex.log").write_text("generated", encoding="utf-8")
    (task_dir / "digest_20260604.mp4").write_bytes(b"mp4")


def test_validate_video_digest_accepts_complete_outputs(tmp_path: Path) -> None:
    check_video_digest = _load_check_video_digest()
    task_dir = tmp_path / "video-digest"
    _write_slides_json(task_dir)
    _write_complete_artifacts(task_dir)

    items = check_video_digest.validate_video_digest(date="2026-06-04", task_dir=task_dir)

    assert all(item.ok for item in items)


def test_validate_video_digest_requires_concept_codex_log(tmp_path: Path) -> None:
    check_video_digest = _load_check_video_digest()
    task_dir = tmp_path / "video-digest"
    _write_slides_json(task_dir)
    _write_complete_artifacts(task_dir)
    (task_dir / "slides" / "seg2.codex.log").unlink()

    items = check_video_digest.validate_video_digest(date="2026-06-04", task_dir=task_dir)

    assert not all(item.ok for item in items)
    assert any(item.label == "seg2 codex log" and not item.ok for item in items)


def test_validate_video_digest_does_not_require_codex_log_for_static_slides(
    tmp_path: Path,
) -> None:
    check_video_digest = _load_check_video_digest()
    task_dir = tmp_path / "video-digest"
    _write_slides_json(task_dir)
    _write_complete_artifacts(task_dir)

    items = check_video_digest.validate_video_digest(
        date="2026-06-04",
        task_dir=task_dir,
        require_audio=False,
        require_mp4=False,
    )

    labels = [item.label for item in items]
    assert "seg1 codex log" not in labels
    assert "seg3 codex log" not in labels
    assert all(item.ok for item in items)

"""scripts/setup_host.sh の launchd タスク登録に関するテスト。"""

from __future__ import annotations

from pathlib import Path

import yaml

PROJ = Path(__file__).parent.parent
SETUP_HOST = PROJ / "scripts" / "setup_host.sh"


def test_setup_host_registers_video_digest_after_daily_digest() -> None:
    """動画タスクを daily-digest の30分後に生成・登録する。"""
    script = SETUP_HOST.read_text(encoding="utf-8")

    assert '_make_task_plist "daily-digest"     7  0' in script
    assert '_make_task_plist "video-digest"     7 30' in script
    assert (
        "birthday-month daily-digest video-digest blog-watch"
        in script
    )


def test_yaml_schedules_keep_video_digest_after_daily_digest() -> None:
    """YAML の参考 cron も launchd と同じ順序に保つ。"""
    daily = yaml.safe_load((PROJ / "tasks" / "daily-digest.yaml").read_text(encoding="utf-8"))
    video = yaml.safe_load((PROJ / "tasks" / "video-digest.yaml").read_text(encoding="utf-8"))

    assert daily["schedule"]["expr"] == "0 7 * * *"
    assert video["schedule"]["expr"] == "30 7 * * *"

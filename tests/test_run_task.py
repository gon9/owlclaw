"""scripts/run_task.sh の起動処理に関するテスト。"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

PROJ = Path(__file__).parent.parent
RUN_TASK = PROJ / "scripts" / "run_task.sh"


def test_run_task_allows_missing_nvm_and_forwards_extra_args(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    captured_args = tmp_path / "uv-args.txt"
    uv_stub = tmp_path / "uv"
    uv_stub.write_text(
        '#!/usr/bin/env bash\nprintf "%s\\n" "$@" > "$CAPTURED_ARGS"\n',
        encoding="utf-8",
    )
    uv_stub.chmod(0o755)
    env = {
        **os.environ,
        "HOME": str(home),
        "UV": str(uv_stub),
        "CAPTURED_ARGS": str(captured_args),
    }

    result = subprocess.run(
        ["bash", str(RUN_TASK), "daily-digest", "--simulate-date", "2026-05-30"],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )

    assert result.returncode == 0
    assert captured_args.read_text(encoding="utf-8").splitlines() == [
        "run",
        "--directory",
        str(PROJ),
        "python",
        str(PROJ / "scripts" / "orchestrator.py"),
        "daily-digest",
        "--simulate-date",
        "2026-05-30",
    ]

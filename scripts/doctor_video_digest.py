#!/usr/bin/env python3
"""video-digest 実行環境の事前診断。

使い方:
    uv run python scripts/doctor_video_digest.py
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

import httpx

PROJ = Path(__file__).parent.parent
sys.path.insert(0, str(PROJ))
sys.path.insert(0, str(Path(__file__).parent))

from _exec import find_executable  # noqa: E402


@dataclass(frozen=True)
class DoctorCheck:
    """1 つの doctor チェック結果。"""

    ok: bool
    label: str
    detail: str
    fix: str = ""


def check_executable(name: str) -> DoctorCheck:
    """必須実行ファイルが見つかるか検査する。"""
    try:
        path = find_executable(name)
    except RuntimeError as exc:
        return DoctorCheck(
            False,
            f"executable: {name}",
            str(exc),
            f"{name} をインストールし、PATH または ~/.local/bin に配置してください。",
        )
    return DoctorCheck(True, f"executable: {name}", path)


def check_puppeteer_import() -> DoctorCheck:
    """render_html.js と同じ探索順で Puppeteer を import できるか検査する。"""
    try:
        node_bin = find_executable("node")
    except RuntimeError as exc:
        return DoctorCheck(False, "puppeteer import", str(exc), "node をインストールしてください。")

    js = r"""
const path = require('path');
const fs = require('fs');
const candidates = [
  path.join(process.cwd(), 'node_modules', 'puppeteer'),
  '/tmp/puppeteer_test/node_modules/puppeteer',
  '/private/tmp/puppeteer_test/node_modules/puppeteer',
];
const errors = [];
for (const c of candidates) {
  if (fs.existsSync(c)) {
    try {
      require(c);
      console.log(c);
      process.exit(0);
    } catch (err) {
      errors.push(`${c}: ${err.message}`);
    }
  }
}
console.error(errors.join('\n') || 'puppeteer not found');
process.exit(1);
"""
    result = subprocess.run(
        [node_bin, "-e", js],
        cwd=PROJ,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        return DoctorCheck(True, "puppeteer import", result.stdout.strip())
    return DoctorCheck(
        False,
        "puppeteer import",
        result.stderr.strip(),
        "npm install",
    )


def check_generated_images(root: Path | None = None) -> DoctorCheck:
    """Codex imagegen の出力先が存在または作成可能で、書き込み可能か検査する。"""
    root = root or (Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")) / "generated_images")
    try:
        root.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(prefix=".doctor-", dir=root, delete=True) as tmp:
            tmp.write(b"ok")
            tmp.flush()
    except OSError as exc:
        return DoctorCheck(
            False,
            "generated_images writable",
            f"{root}: {exc}",
            f"mkdir -p {root} && chmod u+rwx {root}",
        )
    return DoctorCheck(True, "generated_images writable", str(root))


def check_voicevox(url: str) -> DoctorCheck:
    """VOICEVOX endpoint が応答するか検査する。"""
    try:
        with httpx.Client(timeout=5) as client:
            response = client.get(f"{url.rstrip('/')}/version")
            response.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        return DoctorCheck(
            False,
            "VOICEVOX endpoint",
            f"{url}: {exc}",
            f"curl -fsS {url.rstrip('/')}/version",
        )
    return DoctorCheck(True, "VOICEVOX endpoint", response.text.strip())


def check_daily_digest_note(path: Path | None = None) -> DoctorCheck:
    """video-digest の入力となる daily-digest note_draft.md を検査する。"""
    path = path or (PROJ / "tmp" / "daily-digest" / "note_draft.md")
    if path.exists() and path.stat().st_size > 0:
        return DoctorCheck(True, "daily-digest note", str(path))
    return DoctorCheck(
        False,
        "daily-digest note",
        str(path),
        "bash scripts/run_task.sh daily-digest --simulate-date YYYY-MM-DD",
    )


def run_checks(voicevox_url: str) -> list[DoctorCheck]:
    """video-digest の主要依存をまとめて検査する。"""
    checks = [check_executable(name) for name in ("codex", "ffmpeg", "ffprobe", "node")]
    checks.append(check_puppeteer_import())
    checks.append(check_generated_images())
    checks.append(check_voicevox(voicevox_url))
    checks.append(check_daily_digest_note())
    return checks


def print_checks(checks: list[DoctorCheck]) -> None:
    """doctor の結果を人間が読みやすい一覧で出力する。"""
    for check in checks:
        mark = "OK" if check.ok else "NG"
        print(f"[{mark}] {check.label}: {check.detail}")
        if not check.ok and check.fix:
            print(f"     fix: {check.fix}")


def main() -> None:
    parser = argparse.ArgumentParser(description="video-digest 実行環境を診断")
    parser.add_argument(
        "--voicevox-url",
        default=os.environ.get("VOICEVOX_URL", "http://127.0.0.1:50021"),
        help="VOICEVOX endpoint",
    )
    args = parser.parse_args()

    checks = run_checks(args.voicevox_url)
    print_checks(checks)
    if not all(check.ok for check in checks):
        raise SystemExit(1)


if __name__ == "__main__":
    main()

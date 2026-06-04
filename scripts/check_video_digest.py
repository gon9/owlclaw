#!/usr/bin/env python3
"""video-digest の生成成果物を検証する。

使い方:
    uv run python scripts/check_video_digest.py --date YYYY-MM-DD
"""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

PROJ = Path(__file__).parent.parent
sys.path.insert(0, str(PROJ))

from tools.slide_schema import ImageSlide, SlideDeck, load_deck  # noqa: E402

JST = timezone(timedelta(hours=9))


@dataclass(frozen=True)
class CheckItem:
    """1 つの検証項目の結果。"""

    ok: bool
    label: str
    detail: str


def default_date() -> str:
    """JST の今日を YYYY-MM-DD で返す。"""
    return datetime.now(JST).date().isoformat()


def default_task_dir() -> Path:
    """既定の video-digest 作業ディレクトリを返す。"""
    return PROJ / "tmp" / "video-digest"


def _item_exists(path: Path, label: str) -> CheckItem:
    return CheckItem(path.exists() and path.stat().st_size > 0, label, str(path))


def _latest_generated_image() -> Path | None:
    generated_root = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")) / "generated_images"
    if not generated_root.exists():
        return None
    pngs = list(generated_root.glob("**/*.png"))
    if not pngs:
        return None
    return max(pngs, key=lambda path: path.stat().st_mtime_ns)


def validate_video_digest(
    *,
    date: str,
    task_dir: Path | None = None,
    require_audio: bool = True,
    require_mp4: bool = True,
) -> list[CheckItem]:
    """video-digest の成果物を検証し、検証結果一覧を返す。

    ``render_slides.py`` 直後の post-render validation では
    ``require_audio=False, require_mp4=False`` で呼び出す。
    """
    task_dir = task_dir or default_task_dir()
    items: list[CheckItem] = []
    slides_json = task_dir / "slides.json"
    items.append(_item_exists(slides_json, "slides.json"))
    if not items[-1].ok:
        return items

    try:
        deck = load_deck(slides_json)
    except Exception as exc:  # noqa: BLE001
        items.append(CheckItem(False, "slides.json schema", str(exc)))
        return items

    items.append(
        CheckItem(
            deck.date == date,
            "deck date",
            f"expected={date} actual={deck.date}",
        )
    )
    items.extend(validate_slide_artifacts(deck, task_dir, require_audio=require_audio))

    if require_mp4:
        mp4 = task_dir / f"digest_{date.replace('-', '')}.mp4"
        items.append(_item_exists(mp4, "mp4"))

    latest = _latest_generated_image()
    if latest is not None:
        items.append(CheckItem(True, "latest generated image", str(latest)))

    return items


def validate_slide_artifacts(
    deck: SlideDeck,
    task_dir: Path,
    *,
    require_audio: bool,
) -> list[CheckItem]:
    """各 slide.id に対応する PNG / Codex log / WAV を検証する。"""
    items: list[CheckItem] = []
    slides_dir = task_dir / "slides"
    audio_dir = task_dir / "audio"
    for slide in deck.slides:
        png = slides_dir / f"{slide.id}.png"
        items.append(_item_exists(png, f"{slide.id} png"))

        if isinstance(slide, ImageSlide) and slide.type == "concept":
            log = slides_dir / f"{slide.id}.codex.log"
            items.append(_item_exists(log, f"{slide.id} codex log"))

        if require_audio:
            wav = audio_dir / f"{slide.id}.wav"
            items.append(_item_exists(wav, f"{slide.id} wav"))
    return items


def print_items(items: list[CheckItem]) -> None:
    """検証結果を人間が読みやすい一覧で出力する。"""
    for item in items:
        mark = "OK" if item.ok else "NG"
        print(f"[{mark}] {item.label}: {item.detail}")


def main() -> None:
    parser = argparse.ArgumentParser(description="video-digest の成果物を検証")
    parser.add_argument("--date", default=default_date(), help="対象日 (YYYY-MM-DD)")
    parser.add_argument(
        "--task-dir",
        type=Path,
        default=default_task_dir(),
        help=argparse.SUPPRESS,
    )
    args = parser.parse_args()

    items = validate_video_digest(date=args.date, task_dir=args.task_dir)
    print_items(items)
    if not all(item.ok for item in items):
        raise SystemExit(1)


if __name__ == "__main__":
    main()

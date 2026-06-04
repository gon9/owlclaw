#!/usr/bin/env python3
"""スライドデッキをスライド種別ごとに PNG にレンダリングするディスパッチャ。

使い方:
    uv run python scripts/render_slides.py <slides.json> <output_dir>

各スライドは type に応じて以下のレンダラを呼び出す:
    - hero / closing → 固定 HTML テンプレート
    - concept → Codex CLI ($imagegen) で gpt-image-2
    - data / summary → Jinja2 テンプレ → Puppeteer で PNG 化
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

PROJ = Path(__file__).parent.parent
sys.path.insert(0, str(PROJ))
sys.path.insert(0, str(Path(__file__).parent))

from _exec import find_executable as _find_executable  # noqa: E402

from tools.slide_schema import (  # noqa: E402
    DataSlide,
    ExhibitSlide,
    HeroSlide,
    SlideDeck,
    SummarySlide,
    load_deck,
)


def _render_image_slide(slide: HeroSlide, out_png: Path) -> None:
    """gpt-image-2 (Codex CLI) で画像を生成して指定パスに保存する。"""
    generated_root = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")) / "generated_images"
    before = set(generated_root.glob("**/*.png"))
    prompt = (
        f"$imagegen {slide.image_prompt}\n\n"
        "Generate the image only. Do not run sips. Do not resize or copy any file. "
        "Stop immediately after image generation."
    )
    print(f"  [{slide.id}] Codex CLI で画像生成中...", file=sys.stderr)
    codex_bin = _find_executable("codex")
    log_path = out_png.with_suffix(".codex.log")
    poll_seconds = int(os.environ.get("OWLCLAW_CODEX_POLL_SECONDS", "30"))
    timeout_seconds = int(os.environ.get("OWLCLAW_CODEX_TIMEOUT_SECONDS", "900"))
    max_attempts = int(os.environ.get("OWLCLAW_CODEX_MAX_ATTEMPTS", "2"))
    generated: set[Path] = set()
    for attempt in range(1, max_attempts + 1):
        attempt_log_path = (
            log_path
            if max_attempts == 1
            else out_png.with_suffix(f".codex.attempt{attempt}.log")
        )
        with attempt_log_path.open("w", encoding="utf-8") as logf:
            proc = subprocess.Popen(
                [
                    codex_bin,
                    "exec",
                    "--skip-git-repo-check",
                    "--sandbox",
                    "workspace-write",
                    prompt,
                ],
                stdin=subprocess.DEVNULL,
                stdout=logf,
                stderr=subprocess.STDOUT,
            )
            started = time.monotonic()
            last_report = started
            while True:
                returncode = proc.poll()
                elapsed = time.monotonic() - started
                if returncode is not None:
                    if returncode != 0:
                        raise subprocess.CalledProcessError(returncode, proc.args)
                    break
                if elapsed > timeout_seconds:
                    proc.terminate()
                    try:
                        proc.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                        proc.wait()
                    raise TimeoutError(
                        f"[{slide.id}] Codex imagegen が {timeout_seconds} 秒でタイムアウト: "
                        f"{attempt_log_path}"
                    )
                if time.monotonic() - last_report >= poll_seconds:
                    generated_now = set(generated_root.glob("**/*.png")) - before
                    latest = ""
                    if attempt_log_path.exists() and attempt_log_path.stat().st_size > 0:
                        lines = attempt_log_path.read_text(
                            encoding="utf-8",
                            errors="replace",
                        ).splitlines()
                        latest = f" latest_log={lines[-1][:120]!r}" if lines else ""
                    print(
                        f"  [{slide.id}] Codex imagegen 継続中 "
                        f"(attempt={attempt}/{max_attempts}, {int(elapsed)}s, "
                        f"generated={len(generated_now)}, log={attempt_log_path}){latest}",
                        file=sys.stderr,
                    )
                    last_report = time.monotonic()
                time.sleep(1)
        generated = set(generated_root.glob("**/*.png")) - before
        if generated:
            break
        print(
            f"  [{slide.id}] Codex imagegen は正常終了したが画像なし。再試行します "
            f"({attempt}/{max_attempts}): {attempt_log_path}",
            file=sys.stderr,
        )
    if not generated:
        raise RuntimeError(
            f"[{slide.id}] codex は終了したが生成元画像が見つかりません: {log_path}"
        )

    source_png = max(generated, key=lambda path: path.stat().st_mtime_ns)
    ffmpeg_bin = _find_executable("ffmpeg")
    subprocess.run(
        [
            ffmpeg_bin,
            "-y",
            "-i",
            str(source_png),
            "-vf",
            "scale=1280:720:force_original_aspect_ratio=increase,crop=1280:720",
            str(out_png),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def _render_static_slide(
    slide: HeroSlide,
    deck: SlideDeck,
    out_png: Path,
    env: Environment,
) -> None:
    """hero / closing を固定 HTML テンプレートで PNG 化する。"""
    if slide.type not in ("hero", "closing"):
        raise ValueError(f"固定テンプレートは hero / closing のみ対応: {slide.type}")
    template_name = "cover" if slide.type == "hero" else "closing"
    template = env.get_template(f"{template_name}.html.j2")
    html = template.render(deck=deck, slide=slide)
    html_path = out_png.with_suffix(".html")
    html_path.write_text(html, encoding="utf-8")
    print(f"  [{slide.id}] 固定 {template_name} テンプレ → Puppeteer で PNG 化", file=sys.stderr)
    node_bin = _find_executable("node")
    subprocess.run(
        [
            node_bin,
            str(PROJ / "scripts" / "render_html.js"),
            str(html_path),
            str(out_png),
        ],
        check=True,
    )


def _render_concept_slide(
    slide: HeroSlide,
    _deck: SlideDeck,
    out_png: Path,
    _env: Environment,
) -> None:
    """concept スライドを Codex imagegen で PNG 化する。"""
    _render_image_slide(slide, out_png)


def _render_html_slide(
    slide: DataSlide | ExhibitSlide | SummarySlide,
    out_png: Path,
    env: Environment,
) -> None:
    """Jinja2 テンプレ → HTML → Puppeteer で PNG 化する。"""
    template = env.get_template(f"{slide.template}.html.j2")
    html = template.render(data=slide.data)
    html_path = out_png.with_suffix(".html")
    html_path.write_text(html, encoding="utf-8")
    print(f"  [{slide.id}] HTML テンプレ → Puppeteer で PNG 化", file=sys.stderr)
    node_bin = _find_executable("node")
    subprocess.run(
        [
            node_bin,
            str(PROJ / "scripts" / "render_html.js"),
            str(html_path),
            str(out_png),
        ],
        check=True,
    )


def render_deck(deck: SlideDeck, out_dir: Path) -> list[Path]:
    """SlideDeck の全スライドを PNG にレンダリングする。"""
    out_dir.mkdir(parents=True, exist_ok=True)
    env = Environment(
        loader=FileSystemLoader(str(PROJ / "templates")),
        autoescape=select_autoescape(["html"]),
    )
    pngs: list[Path] = []
    for slide in deck.slides:
        png_path = out_dir / f"{slide.id}.png"
        if isinstance(slide, HeroSlide) and slide.type in ("hero", "closing"):
            _render_static_slide(slide, deck, png_path, env)
        elif isinstance(slide, HeroSlide):
            _render_concept_slide(slide, deck, png_path, env)
        elif isinstance(slide, (DataSlide, ExhibitSlide, SummarySlide)):
            _render_html_slide(slide, png_path, env)
        else:
            raise RuntimeError(f"未対応の slide 型: {type(slide)}")
        pngs.append(png_path)
    return pngs


def main() -> None:
    """CLI エントリポイント。"""
    parser = argparse.ArgumentParser(description="スライドデッキを PNG にレンダリング")
    parser.add_argument("slides_json", help="slides.json のパス")
    parser.add_argument("out_dir", help="出力ディレクトリ")
    args = parser.parse_args()

    deck = load_deck(args.slides_json)
    out_dir = Path(args.out_dir)
    pngs = render_deck(deck, out_dir)

    print(f"✓ {len(pngs)} スライドをレンダリング完了: {out_dir}", file=sys.stderr)


if __name__ == "__main__":
    main()

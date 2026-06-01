#!/usr/bin/env python3
"""スライドデッキをスライド種別ごとに PNG にレンダリングするディスパッチャ。

使い方:
    uv run python scripts/render_slides.py <slides.json> <output_dir>

各スライドは type に応じて以下のレンダラを呼び出す:
    - hero / concept → Codex CLI ($imagegen) で gpt-image-2
    - data / summary → Jinja2 テンプレ → Puppeteer で PNG 化
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

PROJ = Path(__file__).parent.parent
sys.path.insert(0, str(PROJ))

from tools.slide_schema import (  # noqa: E402
    DataSlide,
    HeroSlide,
    SlideDeck,
    SummarySlide,
    load_deck,
)


def _find_executable(name: str) -> str:
    """PATH に無い launchd/SSH 環境でも見つかるように、代表的な場所を探す。"""
    import os as _os  # noqa: PLC0415
    import shutil as _shutil  # noqa: PLC0415
    found = _shutil.which(name)
    if found:
        return found
    extra = [
        f"{_os.path.expanduser('~')}/.local/bin/{name}",
        f"/opt/homebrew/bin/{name}",
        f"/usr/local/bin/{name}",
    ]
    for p in extra:
        if _os.path.exists(p) and _os.access(p, _os.X_OK):
            return p
    raise RuntimeError(f"executable not found: {name} (PATH と {extra} を確認)")


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
    with log_path.open("w", encoding="utf-8") as logf:
        subprocess.run(
            [
                codex_bin,
                "exec",
                "--skip-git-repo-check",
                "--sandbox",
                "workspace-write",
                prompt,
            ],
            stdout=logf,
            stderr=subprocess.STDOUT,
            check=True,
        )
    generated = set(generated_root.glob("**/*.png")) - before
    if not generated:
        raise RuntimeError(f"[{slide.id}] codex は終了したが生成元画像が見つかりません")

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


def _render_html_slide(
    slide: DataSlide | SummarySlide, out_png: Path, env: Environment
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
        if isinstance(slide, HeroSlide):
            _render_image_slide(slide, png_path)
        elif isinstance(slide, (DataSlide, SummarySlide)):
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

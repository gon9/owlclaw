"""scripts/render_slides.py の単体テスト。"""

from __future__ import annotations

import importlib.util
from pathlib import Path

from tools.slide_schema import (
    ExhibitData,
    ExhibitSlide,
    ImageSlide,
    SlideDeck,
    SummaryData,
    SummaryListItem,
    SummarySlide,
)

PROJ = Path(__file__).parent.parent


def _load_render_slides():
    spec = importlib.util.spec_from_file_location(
        "render_slides",
        PROJ / "scripts" / "render_slides.py",
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_render_deck_regenerates_existing_png_files(tmp_path: Path, monkeypatch) -> None:
    """同名PNGが残っていても当日のスライド内容で再生成する。"""
    render_slides = _load_render_slides()
    deck = SlideDeck(
        title="Test",
        date="2026-06-01",
        slides=[
            ImageSlide(
                id="seg1",
                type="hero",
                image_prompt="Today's owl logo",
                narration="今日のオープニング",
            ),
            SummarySlide(
                id="seg2",
                type="summary",
                template="summary",
                data=SummaryData(
                    headline="今日のまとめ",
                    items=[SummaryListItem(title="今日の記事")],
                ),
                narration="今日のまとめです。",
            ),
            ExhibitSlide(
                id="seg3",
                type="data",
                template="exhibit",
                data=ExhibitData(headline="今日のニュース"),
                narration="今日のニュースです。",
            ),
        ],
    )
    out_dir = tmp_path / "slides"
    out_dir.mkdir()
    (out_dir / "seg1.png").write_bytes(b"old-image")
    (out_dir / "seg2.png").write_bytes(b"old-html")
    (out_dir / "seg3.png").write_bytes(b"old-exhibit")

    def render_image(slide, path: Path) -> None:
        path.write_bytes(f"new-{slide.id}".encode())

    def render_html(slide, path: Path, _env) -> None:
        path.write_bytes(f"new-{slide.id}".encode())

    monkeypatch.setattr(render_slides, "_render_image_slide", render_image)
    monkeypatch.setattr(render_slides, "_render_html_slide", render_html)

    pngs = render_slides.render_deck(deck, out_dir)

    assert pngs == [out_dir / "seg1.png", out_dir / "seg2.png", out_dir / "seg3.png"]
    assert (out_dir / "seg1.png").read_bytes() == b"new-seg1"
    assert (out_dir / "seg2.png").read_bytes() == b"new-seg2"
    assert (out_dir / "seg3.png").read_bytes() == b"new-seg3"

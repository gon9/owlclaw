"""scripts/render_slides.py の単体テスト。"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
from jinja2 import Environment, FileSystemLoader

from tools.slide_schema import (
    ExhibitData,
    ExhibitFigure,
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
            ImageSlide(
                id="seg2",
                type="concept",
                image_prompt="Japanese business-news infographic slide",
                narration="今日のニュースです。",
            ),
            SummarySlide(
                id="seg3",
                type="summary",
                template="summary",
                data=SummaryData(
                    headline="今日のまとめ",
                    items=[SummaryListItem(title="今日の記事")],
                ),
                narration="今日のまとめです。",
            ),
            ExhibitSlide(
                id="seg4",
                type="data",
                template="exhibit",
                data=ExhibitData(
                    headline="今日のニュース",
                    left_fig=ExhibitFigure(title="従来", value="A"),
                    middle_fig=ExhibitFigure(title="変化", value="B"),
                    right_fig=ExhibitFigure(title="今後", value="C"),
                ),
                narration="今日のニュースです。",
            ),
        ],
    )
    out_dir = tmp_path / "slides"
    out_dir.mkdir()
    (out_dir / "seg1.png").write_bytes(b"old-image")
    (out_dir / "seg2.png").write_bytes(b"old-concept")
    (out_dir / "seg3.png").write_bytes(b"old-html")
    (out_dir / "seg4.png").write_bytes(b"old-exhibit")

    def render_image(slide, path: Path) -> None:
        path.write_bytes(f"new-{slide.id}".encode())

    def render_static(slide, _deck, path: Path, _env) -> None:
        path.write_bytes(f"new-{slide.id}".encode())

    def render_html(slide, path: Path, _env) -> None:
        path.write_bytes(f"new-{slide.id}".encode())

    monkeypatch.setattr(render_slides, "_render_image_slide", render_image)
    monkeypatch.setattr(render_slides, "_render_static_slide", render_static)
    monkeypatch.setattr(render_slides, "_render_html_slide", render_html)

    pngs = render_slides.render_deck(deck, out_dir)

    assert pngs == [
        out_dir / "seg1.png",
        out_dir / "seg2.png",
        out_dir / "seg3.png",
        out_dir / "seg4.png",
    ]
    assert (out_dir / "seg1.png").read_bytes() == b"new-seg1"
    assert (out_dir / "seg2.png").read_bytes() == b"new-seg2"
    assert (out_dir / "seg3.png").read_bytes() == b"new-seg3"
    assert (out_dir / "seg4.png").read_bytes() == b"new-seg4"


def test_render_html_slide_writes_infographic_story_nodes(tmp_path: Path, monkeypatch) -> None:
    """exhibit は3ノードのインフォグラフィック HTML を生成する。"""
    render_slides = _load_render_slides()
    slide = ExhibitSlide(
        id="seg1",
        type="data",
        template="exhibit",
        data=ExhibitData(
            headline="アンソロピックのGTMスタック",
            left_fig=ExhibitFigure(title="従来", value="SaaS"),
            middle_fig=ExhibitFigure(title="転換点", value="運用設計"),
            right_fig=ExhibitFigure(title="今後", value="GTM"),
        ),
        narration="アンソロピックのニュースです。",
    )
    out_png = tmp_path / "seg1.png"
    env = Environment(loader=FileSystemLoader(str(PROJ / "templates")))
    monkeypatch.setattr(render_slides, "_find_executable", lambda _: "node")
    monkeypatch.setattr(render_slides.subprocess, "run", lambda *_, **__: None)

    render_slides._render_html_slide(slide, out_png, env)

    html = out_png.with_suffix(".html").read_text(encoding="utf-8")
    assert html.count('class="fig-card"') == 3
    assert '<div class="node-index">01</div>' in html
    assert '<div class="node-index">02</div>' in html
    assert '<div class="node-index">03</div>' in html


def test_render_static_slide_writes_fixed_cover_html(tmp_path: Path, monkeypatch) -> None:
    """hero は画像生成せず固定 cover HTML を生成する。"""
    render_slides = _load_render_slides()
    deck = SlideDeck(
        title="OWLCLAW NEWS",
        date="2026-06-04",
        slides=[
            ImageSlide(
                id="seg1",
                type="hero",
                narration="おはようございます。",
            ),
            ImageSlide(
                id="seg2",
                type="closing",
                narration="以上です。",
            ),
        ],
    )
    out_png = tmp_path / "seg1.png"
    env = Environment(loader=FileSystemLoader(str(PROJ / "templates")))
    monkeypatch.setattr(render_slides, "_find_executable", lambda _: "node")
    monkeypatch.setattr(render_slides.subprocess, "run", lambda *_, **__: None)

    render_slides._render_static_slide(deck.slides[0], deck, out_png, env)

    html = out_png.with_suffix(".html").read_text(encoding="utf-8")
    assert "AI NEWS" in html
    assert "2026-06-04" in html


def test_static_slide_rejects_concept(tmp_path: Path) -> None:
    """concept を closing テンプレートへ誤フォールバックさせない。"""
    render_slides = _load_render_slides()
    env = Environment(loader=FileSystemLoader(str(PROJ / "templates")))
    deck = SlideDeck(
        title="OWLCLAW NEWS",
        date="2026-06-04",
        slides=[
            ImageSlide(
                id="seg1",
                type="hero",
                narration="おはようございます。",
            ),
            ImageSlide(
                id="seg2",
                type="concept",
                image_prompt="Japanese business-news infographic slide",
                narration="ニュースです。",
            ),
        ],
    )

    with pytest.raises(ValueError):
        render_slides._render_static_slide(deck.slides[1], deck, tmp_path / "seg2.png", env)

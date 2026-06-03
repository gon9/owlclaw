"""tools/slide_schema.py の単体テスト。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from tools.slide_schema import (
    DataSlide,
    ExhibitData,
    ExhibitFigure,
    HeroSlide,
    KpiColumn,
    KpiThreeColData,
    SlideDeck,
    SummaryData,
    SummaryListItem,
    SummarySlide,
    load_deck,
)


def _hero(seg_id: str = "seg1") -> HeroSlide:
    """テスト用 hero スライドを作る。"""
    return HeroSlide(
        id=seg_id,
        type="hero",
        image_prompt="A modern AI newsroom",
        narration="おはようございます。",
    )


def _data_slide(seg_id: str = "seg2") -> DataSlide:
    """テスト用 data スライドを作る。"""
    return DataSlide(
        id=seg_id,
        type="data",
        template="kpi_three_col",
        data=KpiThreeColData(
            headline="OpenRouter $1.3B 調達",
            subtitle="1年で2倍超",
            columns=[
                KpiColumn(label="調達額", value="$113M", caption="CapitalG"),
                KpiColumn(label="評価額", value="$1.3B", caption="2倍超"),
                KpiColumn(label="Usage", value="5倍", caption="6ヶ月"),
            ],
            insights=["示唆1", "示唆2"],
            source="TechCrunch",
        ),
        narration="続いてのニュースです。",
    )


def _summary_slide(seg_id: str = "seg3") -> SummarySlide:
    """テスト用 summary スライドを作る。"""
    return SummarySlide(
        id=seg_id,
        type="summary",
        template="summary",
        data=SummaryData(
            headline="本日のハイライト",
            items=[SummaryListItem(title="ニュース1", detail="詳細")],
            closing="ご視聴ありがとうございました。",
        ),
        narration="本日のニュースをお伝えしました。",
    )


# 正常系
def test_hero_slide_creation() -> None:
    """hero スライドが正しく構築できる。"""
    h = _hero()
    assert h.id == "seg1"
    assert h.type == "hero"


def test_hero_slide_without_image_prompt() -> None:
    """hero / closing は固定テンプレートなので image_prompt なしでも構築できる。"""
    h = HeroSlide(
        id="seg1",
        type="hero",
        narration="おはようございます。",
    )
    assert h.image_prompt == ""


def test_data_slide_creation() -> None:
    """data スライドが正しく構築できる。"""
    d = _data_slide()
    assert d.template == "kpi_three_col"
    assert len(d.data.columns) == 3


def test_summary_slide_creation() -> None:
    """summary スライドが正しく構築できる。"""
    s = _summary_slide()
    assert s.data.headline == "本日のハイライト"


def test_slide_deck_minimum() -> None:
    """最小構成（2 スライド）の SlideDeck が組める。"""
    deck = SlideDeck(
        title="Test", date="2026-05-28",
        slides=[_hero("a"), _summary_slide("b")],
    )
    assert deck.speaker_id == 13  # 既定値
    assert len(deck.slides) == 2


def test_load_deck_from_json(tmp_path: Path) -> None:
    """JSON ファイルから SlideDeck をロードできる。"""
    payload = {
        "title": "Test", "date": "2026-05-28",
        "slides": [
            _hero("seg1").model_dump(),
            _summary_slide("seg2").model_dump(),
        ],
    }
    json_path = tmp_path / "slides.json"
    json_path.write_text(json.dumps(payload), encoding="utf-8")
    deck = load_deck(json_path)
    assert deck.title == "Test"


# 異常系
def test_kpi_columns_too_few() -> None:
    """KPI 列数が 1 だと ValidationError。"""
    with pytest.raises(ValidationError):
        KpiThreeColData(
            headline="x",
            columns=[KpiColumn(label="a", value="1")],
        )


def test_kpi_columns_too_many() -> None:
    """KPI 列数が 5 だと ValidationError。"""
    with pytest.raises(ValidationError):
        KpiThreeColData(
            headline="x",
            columns=[KpiColumn(label=f"l{i}", value=str(i)) for i in range(5)],
        )


def test_summary_items_zero() -> None:
    """summary の項目数 0 で ValidationError。"""
    with pytest.raises(ValidationError):
        SummaryData(headline="x", items=[])


def test_exhibit_requires_three_story_nodes() -> None:
    """infographic exhibit は3ノードが揃っていないと ValidationError。"""
    with pytest.raises(ValidationError):
        ExhibitData(
            headline="x",
            left_fig=ExhibitFigure(title="従来", value="A"),
            middle_fig=ExhibitFigure(title="変化", value="B"),
        )


def test_slide_deck_too_few() -> None:
    """スライド数 1 で ValidationError。"""
    with pytest.raises(ValidationError):
        SlideDeck(title="x", date="2026-05-28", slides=[_hero()])


def test_slide_deck_duplicate_ids() -> None:
    """slide.id 重複で ValidationError。"""
    with pytest.raises(ValidationError):
        SlideDeck(
            title="x", date="2026-05-28",
            slides=[_hero("dup"), _summary_slide("dup")],
        )


def test_slide_deck_too_many() -> None:
    """スライド数 9 で ValidationError。"""
    slides = [_hero(f"s{i}") for i in range(9)]
    with pytest.raises(ValidationError):
        SlideDeck(title="x", date="2026-05-28", slides=slides)

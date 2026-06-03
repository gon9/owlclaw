"""動画スライドの中間表現スキーマ。

Claude が出力する `slides.json` をバリデーションし、後続の
レンダリング・音声合成・動画合成パイプラインに型安全に渡すための
Pydantic モデル群を定義する。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class KpiColumn(BaseModel):
    """KPI 三列スライドの 1 列分のデータ。"""

    label: str = Field(description="列の見出し（例: 資金調達）")
    value: str = Field(description="大きく表示する数値文字列（例: $113M）")
    caption: str = Field(default="", description="補足説明（例: CapitalG主導）")


class KpiThreeColData(BaseModel):
    """`type=data` + `template=kpi_three_col` のデータ部。"""

    headline: str = Field(description="スライド大見出し（1行）")
    subtitle: str = Field(default="", description="サブタイトル/リード文")
    columns: list[KpiColumn] = Field(description="3 列分の KPI（最大4列）")
    insights: list[str] = Field(default_factory=list, description="戦略的示唆（最大3行）")
    source: str = Field(default="", description="出典（例: TechCrunch 2026-05-26）")

    @field_validator("columns")
    @classmethod
    def _validate_columns(cls, v: list[KpiColumn]) -> list[KpiColumn]:
        """列数を 2-4 に制限する。"""
        if not 2 <= len(v) <= 4:
            raise ValueError(f"columns は 2〜4 個。現在: {len(v)}")
        return v


class SummaryListItem(BaseModel):
    """`type=summary` のリスト項目。"""

    title: str = Field(description="項目タイトル")
    detail: str = Field(default="", description="詳細1行")


class SummaryData(BaseModel):
    """`type=summary` + `template=summary` のデータ部。"""

    headline: str = Field(description="スライド大見出し")
    items: list[SummaryListItem] = Field(description="箇条書き項目（最大6件）")
    closing: str = Field(default="", description="締めの一言")

    @field_validator("items")
    @classmethod
    def _validate_items(cls, v: list[SummaryListItem]) -> list[SummaryListItem]:
        """項目数を 1-6 に制限する。"""
        if not 1 <= len(v) <= 6:
            raise ValueError(f"items は 1〜6 個。現在: {len(v)}")
        return v


class ExhibitFigure(BaseModel):
    """Exhibit内の1つの図解要素（左図・中図・右図など）"""

    title: str = Field(description="図のタイトル")
    icon: str = Field(default="", description="アイコン名（例: hand-drawn scale, gauge, mountain）")
    value: str = Field(default="", description="強調する数字や短いテキスト")
    caption: str = Field(default="", description="図の補足説明")


class ExhibitTableRow(BaseModel):
    """比較テーブルの1行"""

    header: str = Field(description="行の見出し")
    col1: str = Field(description="列1のデータ")
    col2: str = Field(description="列2のデータ")


class ExhibitTable(BaseModel):
    """比較テーブルデータ"""

    col1_header: str = Field(description="列1の見出し")
    col2_header: str = Field(description="列2の見出し")
    rows: list[ExhibitTableRow] = Field(description="行データ配列")


class ExhibitData(BaseModel):
    """`type=data` + `template=exhibit` のデータ部。content-richな構造。"""

    headline: str = Field(description="スライド大見出し")
    subtitle: str = Field(default="", description="サブ段落（リード文）")
    left_fig: ExhibitFigure = Field(description="左ノード（起点・従来）")
    middle_fig: ExhibitFigure = Field(description="中央ノード（変化・転換点）")
    right_fig: ExhibitFigure = Field(description="右ノード（意味・今後）")
    table: ExhibitTable | None = Field(default=None, description="比較テーブル")
    insight_bar: str = Field(default="", description="下部の示唆バー（Insight bar）")
    source: str = Field(default="", description="出典")


class ImageSlide(BaseModel):
    """`type=hero`, `concept`, `closing` のスライド。

    hero / closing は固定 HTML テンプレートでレンダリングする。
    concept は必要な場合だけ gpt-image-2 で生成する。
    """

    id: str = Field(description="スライドID（例: seg1）")
    type: Literal["hero", "concept", "closing"]
    image_prompt: str = Field(default="", description="concept 用の英語プロンプト")
    narration: str = Field(description="ナレーション原稿（日本語）")


# 旧 API 互換: hero 専用だった時代の import を維持する。
HeroSlide = ImageSlide


class DataSlide(BaseModel):
    """`type=data` のスライド。HTML テンプレートでレンダリング。"""

    id: str = Field(description="スライドID（例: seg2）")
    type: Literal["data"] = "data"
    template: Literal["kpi_three_col"] = Field(
        description="使用する HTML テンプレート名"
    )
    data: KpiThreeColData
    narration: str = Field(description="ナレーション原稿（日本語）")


class SummarySlide(BaseModel):
    """`type=summary` のスライド。HTML テンプレートでレンダリング。"""

    id: str = Field(description="スライドID（例: seg5）")
    type: Literal["summary"] = "summary"
    template: Literal["summary"] = Field(description="使用する HTML テンプレート名")
    data: SummaryData
    narration: str = Field(description="ナレーション原稿（日本語）")


class ExhibitSlide(BaseModel):
    """`type=data` のスライドで Exhibit テンプレートを使用"""

    id: str = Field(description="スライドID（例: seg3）")
    type: Literal["data"] = "data"
    template: Literal["exhibit"] = Field(description="使用する HTML テンプレート名")
    data: ExhibitData
    narration: str = Field(description="ナレーション原稿（日本語）")


Slide = ImageSlide | DataSlide | ExhibitSlide | SummarySlide


class SlideDeck(BaseModel):
    """動画全体のスライドデッキ。Claude が `slides.json` として出力する。"""

    title: str = Field(description="動画全体のタイトル")
    date: str = Field(description="ISO 形式日付 (YYYY-MM-DD)")
    slides: list[Slide] = Field(description="スライド配列（先頭から順に再生）")
    speaker_id: int = Field(default=13, description="VOICEVOX speaker id（既定: 青山龍星）")

    @field_validator("slides")
    @classmethod
    def _validate_slides(cls, v: list[Slide]) -> list[Slide]:
        """スライド数を 2〜8 に制限し、id の一意性を確認する。"""
        if not 2 <= len(v) <= 8:
            raise ValueError(f"slides は 2〜8 枚。現在: {len(v)}")
        ids = [s.id for s in v]
        if len(ids) != len(set(ids)):
            raise ValueError(f"slide.id に重複があります: {ids}")
        return v


def load_deck(path: Path | str) -> SlideDeck:
    """JSON ファイルから SlideDeck を読み込む。"""
    p = Path(path)
    raw = json.loads(p.read_text(encoding="utf-8"))
    return SlideDeck.model_validate(raw)

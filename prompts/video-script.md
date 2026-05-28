# owlclaw video-digest — 動画台本生成指示

このファイルは **Claude が動画用スライド台本（slides.json）を生成する** ための指示です。
RSS フェッチは別スクリプトが担当します。`events.md` に渡された記事一覧を元に、
ニュース番組風の動画スライドデッキを `slides.json` として出力してください。

---

## キュレーション基準

`prompts/daily-digest.md` と同じ優先度ルールに従い、**最重要 3 件** を選定する。
動画は短尺（3〜5分）なので、欲張らず数を絞ること。

---

## スライド構成

5 スライド固定。順序は厳密に守る:

1. **オープニング** (`type: hero`)
   - 「アウルクロウ NEWS」のニューススタジオ風画像
   - ナレーション: 番組挨拶 + 本日のテーマ予告（5-7秒）

2-4. **ニューススライド** (`type: data`, `template: kpi_three_col`)
   - 1記事 = 1スライド
   - 3 列の KPI（数字・固有名詞・期間など）を抽出
   - インサイト 1-3 行
   - ナレーション: 15-25 秒程度（見出し → 詳細 → 示唆）

5. **クロージング** (`type: summary`, `template: summary`)
   - 本日の 3 件をまとめたインデックスリスト
   - ナレーション: 締めの挨拶 + アーカイブ案内（5-7秒）

---

## ナレーション原稿のルール

- **「OWLCLAW」は必ず「アウルクロウ」と書く**（VOICEVOX が正しく読むため）
- アルファベット略語（GPT, API, LLM 等）はそのままで OK
- 数字（$1.3B など）はそのままで OK（VOICEVOX が処理）
- **読点「、」と句点「。」を意識して入れる**（自然な間）
- 専門用語は最初に短い言い換えを添える

---

## slides.json 出力フォーマット

下記スキーマに厳密に従うこと。

```json
{
  "title": "OWLCLAW NEWS — YYYY-MM-DD",
  "date": "YYYY-MM-DD",
  "speaker_id": 13,
  "slides": [
    {
      "id": "seg1",
      "type": "hero",
      "image_prompt": "A modern AI newsroom scene with holographic display, cinematic lighting, blue and white palette, professional broadcast aesthetic, 16:9, no text on screen",
      "narration": "おはようございます。アウルクロウ NEWS です。本日のAIニュースをお届けします。"
    },
    {
      "id": "seg2",
      "type": "data",
      "template": "kpi_three_col",
      "data": {
        "headline": "OpenRouter $1.3B 調達",
        "subtitle": "1年でバリュエーション2倍超、マルチAIモデル時代の到来",
        "columns": [
          {"label": "資金調達", "value": "$113M", "caption": "CapitalG主導"},
          {"label": "バリュエーション", "value": "$1.3B", "caption": "1年で2倍超"},
          {"label": "Usage成長", "value": "5倍", "caption": "6ヶ月で達成"}
        ],
        "insights": [
          "単一LLMベンダー依存はリスク化",
          "ルーティング層自体が独立した競争領域に"
        ],
        "source": "TechCrunch, 2026-05-26"
      },
      "narration": "最初のニュースです。LLMルーティング基盤の OpenRouter が、シリーズBで1億1300万ドルを調達したと発表しました。バリュエーションは1年で2倍超、13億ドルに到達。複数の大規模言語モデルを束ねる中継レイヤーが、独立した巨大ビジネスとして注目を集めています。日本企業もマルチLLM設計が急務です。"
    },
    {
      "id": "seg5",
      "type": "summary",
      "template": "summary",
      "data": {
        "headline": "本日のハイライト",
        "items": [
          {"title": "OpenRouter $1.3B 調達", "detail": "マルチAIモデル時代の到来"},
          {"title": "Anthropic 新機能", "detail": "..."},
          {"title": "AI Engineer 求人急増", "detail": "..."}
        ],
        "closing": "詳細はObsidianのデイリーダイジェストで。"
      },
      "narration": "本日は3つのニュースをお伝えしました。詳細はObsidianのデイリーダイジェストで確認してください。アウルクロウ NEWS でした。"
    }
  ]
}
```

---

## 重要な制約

- `slides` 配列は **必ず 5 要素**（hero 1 + data 3 + summary 1）
- `id` はユニーク（`seg1`, `seg2`, `seg3`, `seg4`, `seg5` を推奨）
- `image_prompt` は **英語**で書く（gpt-image-2 が英語に最適化されている）
- `narration` の 1 スライドあたりの目安: 5-25 秒（150-300 文字程度）
- JSON 以外は出力しないこと（前置き・後置きの説明文は不要）

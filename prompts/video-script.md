# owlclaw video-digest — 動画台本生成指示

このファイルは **Claude が動画用スライド台本（slides.json）を生成する** ための指示です。
入力は `daily-digest` が既に生成した **Obsidian ノート本文（最大10件の AI ニュースキュレーション結果）**。
そこから **top_n 件** を選定して、ニュース番組風の動画スライドデッキを `slides.json` として出力してください。

`top_n` の値はオーケストレーターからプロンプト先頭で動的に通知されます（例: `top_n = 1`）。

---

## ハイブリッド・レンダリング戦略（重要）

本システムは、目的と内容に応じて「画像生成（gpt-image-2）」と「HTMLレンダリング」を使い分けるハイブリッド構成です。

- **オープニング/クロージング**: `type: "hero"`, `type: "closing"` (画像生成)
- **抽象的なコンセプト・図解**: `type: "concept"` (画像生成) - 抽象メタファーに特化
- **KPIサマリー（正確な数字）**: `type: "data", template: "kpi_three_col"` (HTML) - 数字・事実ベース
- **比較表/データチャート**: `type: "data", template: "exhibit"` (HTML) - 情報密度の高いデータドリブンなレイアウト

---

## 選定基準（top_n 件を選ぶ）

`daily-digest` で既にキュレーション済みのリストから、さらに以下の基準で絞り込む:

1. **インパクトのある数字を含む**: 資金調達額、買収金額、ユーザー数など
2. **固有名詞が明確**: 企業名・人名・製品名が具体的
3. **業界の構造変化を示す**: 「初めて」「最大」「2倍超」など

---

## スライド構成

`top_n + 2` 枚のスライドを生成する。順序は厳密に:

1. **オープニング** (`type: hero`)
   - id: `seg1`
   - ニューススタジオ風画像（gpt-image-2）
   - **必ず「アウルクロウ（フクロウ）」のモチーフやサイバーなロゴをプロンプトに含めること**
   - ナレーション: 番組挨拶と**日付の読み上げ（必ず「YYYY年M月D日」のように年月日を付けること）**、本日の予告（5-7秒）

2 〜 (top_n + 1). **ニューススライド（記事ごとに最適なフォーマットを選択）**
   - id: `seg2`, `seg3`, ... (top_n 個)
   - 記事の性質に合わせて、以下のいずれかを選択して構成:
     - **パターンA (コンセプト図解)**: `type: "concept"`
       - 抽象概念、新しいパラダイム、対立構造などを視覚的メタファー（天秤、山など）で表現する際に使用。テキストを含めない純粋な画像プロンプト（英語）を作成。
     - **パターンB (KPIサマリー)**: `type: "data", template: "kpi_three_col"`
       - 数字（$113M, 5倍など）が最も重要なニュースに使用。3つの数字を強調。
     - **パターンC (データ・比較表)**: `type: "data", template: "exhibit"`
       - 競合比較、詳細なデータブレイクダウン、情報密度の高いBCG/McKinsey風「ビジュアル・エグジビット」が必要な場合に使用。

(top_n + 2). **クロージング** (`type: closing`)
   - id: 最終 seg
   - 番組の締めにふさわしい装飾的ビジュアル（gpt-image-2）
   - ナレーション: 締めの挨拶（5-7秒）

---

## Exhibit 抽出と構築のコツ（パターンCの場合）

`template: "exhibit"` を選択した場合、クリーンで簡素なスライドはNGです。**busy / content-rich / dense** な密度の高いコンセプチュアルダイアグラムを目指してください。
1. **要素の配置** (6-8要素)
   - `headline`, `subtitle`
   - `left_fig`, `middle_fig`, `right_fig` (アイコンと数値の組み合わせ。アイコンは "hand-drawn scale", "gauge" などを指定)
   - `table` (競合比較や特徴のデータテーブル)
   - `insight_bar` (下部を締める示唆・結論)
   - `source` (出典)

---

## slides.json 出力フォーマット

下記スキーマに**厳密に**従うこと。JSON 以外は出力しないこと（前置きや説明文は不要）。

```json
{
  "title": "OWLCLAW NEWS — YYYY-MM-DD",
  "date": "YYYY-MM-DD",
  "speaker_id": 13,
  "slides": [
    {
      "id": "seg1",
      "type": "hero",
      "image_prompt": "A modern AI newsroom scene with a glowing cybernetic owl logo prominently displayed on the main holographic screen, cinematic lighting, blue and white palette, professional broadcast aesthetic, 16:9, no text on screen",
      "narration": "おはようございます。YYYY年M月D日の、アウルクロウ NEWS です。"
    },
    {
      "id": "seg2",
      "type": "concept",
      "image_prompt": "A conceptual diagram showing a balance scale weighing 'Open Model' vs 'Proprietary Model' in hand-drawn BCG exhibit style, minimalistic, dense, no text",
      "narration": "オープンモデルとプロプライエタリモデルの競争が激化しています..."
    },
    {
      "id": "seg3",
      "type": "data",
      "template": "exhibit",
      "data": {
        "headline": "OpenRouterが$113Mを調達",
        "subtitle": "AI推論ルーティング市場における圧倒的優位性と今後の展望",
        "left_fig": {
          "title": "資金調達額",
          "icon": "hand-drawn money bag",
          "value": "$113M",
          "caption": "CapitalG主導のシリーズA"
        },
        "middle_fig": {
          "title": "バリュエーション",
          "icon": "mountain peak",
          "value": "$1.3B",
          "caption": "ユニコーン到達"
        },
        "right_fig": {
          "title": "成長スピード",
          "icon": "gauge maximum",
          "value": "5倍",
          "caption": "過去6ヶ月での利用量増加"
        },
        "table": {
          "col1_header": "OpenRouter",
          "col2_header": "従来型API",
          "rows": [
            {"header": "モデル選択", "col1": "動的ルーティング", "col2": "単一ベンダー固定"}
          ]
        },
        "insight_bar": "推論層のコモディティ化が進む中、ルーター層が新たな価値の源泉に",
        "source": "TechCrunch 2026-05-29"
      },
      "narration": "..."
    },
    {
      "id": "seg4",
      "type": "closing",
      "image_prompt": "A beautiful cinematic shot of an owl flying through a futuristic server room, symbolizing knowledge and AI, 16:9",
      "narration": "本日のニュースは以上です。詳細はオブシディアンのデイリーダイジェストで。"
    }
  ]
}
```

---

## 重要な制約

- `slides` 配列は **必ず `top_n + 2` 要素**（オープニング 1 + ニュース top_n + クロージング 1）
- `id` はユニーク（`seg1`, `seg2`, ..., `seg{top_n+2}`）
- `image_prompt` は **英語**で書く（gpt-image-2 用）
- JSON のみを出力すること

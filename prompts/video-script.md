# owlclaw video-digest — 動画台本生成指示

このファイルは **Claude が動画用スライド台本（slides.json）を生成する** ための指示です。
入力は `daily-digest` が既に生成した **Obsidian ノート本文（最大10件の AI ニュースキュレーション結果）**。
そこから **top_n 件** を選定して、ニュース番組風の動画スライドデッキを `slides.json` として出力してください。

`top_n` の値はオーケストレーターからプロンプト先頭で動的に通知されます（例: `top_n = 1`）。

---

## 選定基準（top_n 件を選ぶ）

`daily-digest` で既にキュレーション済みのリストから、さらに以下の基準で絞り込む:

### 優先（必ず拾う候補）
1. **インパクトのある数字を含む**: 資金調達額、買収金額、ユーザー数、成長倍率など視覚的に強い
2. **固有名詞が明確**: 企業名・人名・製品名が具体的でクリックを誘発しやすい
3. **業界の構造変化を示す**: 「初めて」「最大」「2倍超」など見出しに強さがある
4. **日本SaaSへの示唆が明確**: 「自分ごと」化しやすい

### 避ける
- アップデートのみ・既報のリピート
- 抽象的な研究論文や将来予測（数字が薄い）

複数の優先項目に該当するものを優先。**最も「動画で見せて映える」もの**を選ぶ。

---

## スライド構成

`top_n + 2` 枚のスライドを生成する。順序は厳密に:

1. **オープニング** (`type: hero`)
   - id: `seg1`
   - ニューススタジオ風画像
   - ナレーション: 番組挨拶 + 本日の予告（5-7秒）

2 〜 (top_n + 1). **ニューススライド** (`type: data`, `template: kpi_three_col`)
   - id: `seg2`, `seg3`, ... (top_n 個)
   - 各記事 = 1スライド
   - 3 列の KPI（数字・固有名詞・期間）を抽出
   - インサイト 1-3 行
   - ナレーション: 15-25 秒程度（見出し → 詳細 → 示唆）

(top_n + 2). **クロージング** (`type: summary`, `template: summary`)
   - id: 最終 seg
   - 本日紹介した top_n 件のインデックス
   - ナレーション: 締めの挨拶（5-7秒）

### 例: top_n の値による枚数

| top_n | 総スライド数 | 構成 |
|---|---|---|
| 1 | 3 | hero + data×1 + summary |
| 3 | 5 | hero + data×3 + summary |
| 5 | 7 | hero + data×5 + summary |

---

## ナレーション原稿のルール

- **「OWLCLAW」は必ず「アウルクロウ」とひらがな/カタカナで書く**（VOICEVOX 対策）
- 「Obsidian」は「オブシディアン」と書く
- アルファベット略語（GPT, API, LLM 等）はそのままで OK
- 数字（$1.3B など）はそのままで OK（VOICEVOX が処理）
- **読点「、」と句点「。」を意識して入れる**（自然な間）
- 専門用語は最初に短い言い換えを添える

---

## KPI 抽出のコツ

入力の各記事 Summary から、視覚的に強い 3 つの数字・固有名詞を `columns` に抽出する。

例（OpenRouter $113M 調達のとき）:
```json
"columns": [
  {"label": "資金調達", "value": "$113M", "caption": "CapitalG主導"},
  {"label": "バリュエーション", "value": "$1.3B", "caption": "1年で2倍超"},
  {"label": "Usage成長", "value": "5倍", "caption": "6ヶ月で達成"}
]
```

`label` は短く（4〜8 文字）、`value` は最大インパクトの 1 単語、`caption` は補足説明。

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
      "image_prompt": "A modern AI newsroom scene with holographic display, cinematic lighting, blue and white palette, professional broadcast aesthetic, 16:9, no text on screen",
      "narration": "おはようございます。アウルクロウ NEWS です。本日のAIニュースをお届けします。"
    },
    {
      "id": "seg2",
      "type": "data",
      "template": "kpi_three_col",
      "data": {
        "headline": "...",
        "subtitle": "...",
        "columns": [
          {"label": "...", "value": "...", "caption": "..."},
          {"label": "...", "value": "...", "caption": "..."},
          {"label": "...", "value": "...", "caption": "..."}
        ],
        "insights": ["...", "..."],
        "source": "..."
      },
      "narration": "..."
    },
    {
      "id": "segN",
      "type": "summary",
      "template": "summary",
      "data": {
        "headline": "本日のハイライト",
        "items": [
          {"title": "...", "detail": "..."}
        ],
        "closing": "詳細はオブシディアンのデイリーダイジェストで。"
      },
      "narration": "..."
    }
  ]
}
```

---

## 重要な制約

- `slides` 配列は **必ず `top_n + 2` 要素**（hero 1 + data top_n + summary 1）
- `id` はユニーク（`seg1`, `seg2`, ..., `seg{top_n+2}`）
- `image_prompt` は **英語**で書く（gpt-image-2 が英語に最適化）
- `narration` は 1 スライドあたり 5-25 秒（150-300 文字目安）
- summary スライドの `items` は **top_n と同じ件数**
- JSON のみを出力すること（コードフェンス ``` も不要）

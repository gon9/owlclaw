# owlclaw video-digest — 動画台本生成指示

このファイルは **Claude が動画用スライド台本（slides.json）を生成する** ための指示です。
入力は `daily-digest` が既に生成した **Obsidian ノート本文（最大10件の AI ニュースキュレーション結果）**。
そこから **top_n 件** を選定して、ニュース番組風の動画スライドデッキを `slides.json` として出力してください。

`top_n` の値はオーケストレーターからプロンプト先頭で動的に通知されます（例: `top_n = 1`）。

---

## ハイブリッド・レンダリング戦略（重要）

本システムは、表紙・締めを固定テンプレート化し、ニュース本文だけを動的生成します。

- **オープニング/クロージング**: `type: "hero"`, `type: "closing"` (固定HTMLテンプレート。画像生成しない)
- **ニュース本文**: `visual_mode = imagegen` のため、`type: "concept"` + `image_prompt` で画像生成する

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
   - 固定表紙テンプレートでレンダリングされるため、`image_prompt` は不要
   - ナレーション: 番組挨拶と**日付の読み上げ（必ず「YYYY年M月D日」のように年月日を付けること）**、本日の予告（5-7秒）

## ナレーション原稿のルール（重要）

- **「OWLCLAW」は必ず「アウルクロウ」とひらがな/カタカナで書く**（VOICEVOX 対策）
- 「Obsidian」は「オブシディアン」と書く
- **「Anthropic」は必ず「アンソロピック」と書く**（英字のままだと一文字ずつ読み上げられるため）
- **日付を読む際は「YYYY年M月D日」のように必ず漢字の年月日を含め、自然な日本語にすること**（例：「20260531」のような数字の羅列はNG）
- **ナレーションの内容は、必ずそのスライド（または画像プロンプト）に表示されているニュース記事と完全に一致させること。スライド上の数字や固有名詞と、ナレーションで読み上げる数字・固有名詞に一切のズレ・矛盾がないようにする。別の記事の内容を混ぜないこと。**
- アルファベット略語（GPT, API, LLM 等）はそのままで OK
- 数字（$1.3B など）はそのままで OK（VOICEVOX が処理）
- **読点「、」と句点「。」を意識して入れる**（自然な間）
- 専門用語は最初に短い言い換えを添える

2 〜 (top_n + 1). **ニューススライド**
   - id: `seg2`, `seg3`, ... (top_n 個)
   - `type: "concept"` を使う。
   - `image_prompt` は英語で書く。
   - 画像内に入れる見出し・数字・出典は、必ず元記事の内容と一致させる。
   - 方向性は「日本語のコンサル資料風 exhibit」。単なる写真・抽象アート・雰囲気画像は禁止。
   - 1枚の中に、見出し、3つの図解パネル、主要指標、下部の示唆バーを含める。

(top_n + 2). **クロージング** (`type: closing`)
   - id: 最終 seg
   - 固定締めテンプレートでレンダリングされるため、`image_prompt` は不要
   - ナレーション: 締めの挨拶（5-7秒）

---

## 画像生成スライドのプロンプト作成ルール（visual_mode=imagegen）

`type: "concept"` の `image_prompt` は、次の要素を必ず含めてください。

1. **レイアウト**
   - 16:9 Japanese business-news infographic slide
   - consulting exhibit style, clean but content-rich
   - large Japanese headline at top
   - three main panels across the middle
   - compact metric table or metric strip at bottom
   - orange strategic insight bar at bottom
2. **図解内容**
   - 記事の構造を、ノード・矢印・比較・チャート・因果関係として描く
   - 企業名、プロダクト名、金額、成長率、日付、出典を明示する
   - ただし、事実にない数字や企業名は追加しない
3. **スタイル**
   - navy blue, white, orange accents
   - hand-drawn technical sketch elements
   - crisp lines, dense but readable
   - no photorealism, no people, no random extra text

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
      "narration": "おはようございます。YYYY年M月D日の、アウルクロウ NEWS です。"
    },
    {
      "id": "seg2",
      "type": "concept",
      "image_prompt": "Create a 16:9 Japanese business-news infographic slide, consulting exhibit style, clean but content-rich. Topic: Replit operates 10,000 AI agents and shifts software development from writing code manually to directing parallel AI work. Layout: large bold Japanese headline at top: \"Replit、1万規模のAIエージェントを稼働\". Three main panels across the middle: INPUT shows natural language instruction, AGENTS shows many parallel AI agents, OUTPUT shows generated app/code, IMPACT shows development bottleneck shifting to task design. Bottom metric strip: 10,000 agents / English prompts / parallel execution / GTM impact. Final orange insight bar: \"戦略的示唆：開発の競争軸は、コードを書く力からAIに仕事を渡す設計力へ移る\". Use navy blue, white, orange accents, hand-drawn technical sketch elements, crisp lines, dense but readable, no photorealism, no people, no random extra text.",
      "narration": "..."
    },
    {
      "id": "seg3",
      "type": "closing",
      "narration": "本日のニュースは以上です。詳細はオブシディアンのデイリーダイジェストで。"
    }
  ]
}
```

---

## 重要な制約

- `slides` 配列は **必ず `top_n + 2` 要素**（オープニング 1 + ニュース top_n + クロージング 1）
- `id` はユニーク（`seg1`, `seg2`, ..., `seg{top_n+2}`）
- `image_prompt` は本文ニュースで `type: "concept"` を使う場合に英語で書く
- JSON のみを出力すること

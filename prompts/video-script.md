# owlclaw video-digest — 動画台本生成指示

このファイルは **Claude が動画用スライド台本（slides.json）を生成する** ための指示です。
主入力は `daily-digest` が既に生成した **Obsidian ノート本文（最大10件の AI ニュースキュレーション結果）**。
そこから **top_n 件** を選定して、ニュース番組風の動画スライドデッキを `slides.json` として出力してください。

`events.md` が追加参照ファイルとして渡されている場合は、`daily-digest` の元フィード一覧として扱います。
Slack/Obsidian 向けのニュースフィード処理をやり直さず、スライド化する記事の URL・抜粋・出典を補うためだけに使ってください。
記事 URL が取得できる場合は、対象記事だけ WebFetch で読み、元記事の内容を直接スライド化してください。

`top_n` の値はオーケストレーターからプロンプト先頭で動的に通知されます（例: `top_n = 1`）。

---

## ハイブリッド・レンダリング戦略（重要）

本システムは、表紙・締めを固定テンプレート化し、ニュース本文だけを動的生成します。

- **オープニング/クロージング**: `type: "hero"`, `type: "closing"` (固定HTMLテンプレート。画像生成しない)
- **ニュース本文**: オーケストレーターから渡される `visual_mode` に必ず従う
  - `visual_mode = imagegen`: `type: "concept"` + `image_prompt`。後段で Codex imagegen が画像化する。
  - `visual_mode = ppt`: `type: "data"` + `template: "exhibit"`。Claude が記事を読んで、自然なPPT風の1枚スライドとして構成し、後段でHTMLテンプレートがPNG化する。
  - `visual_mode = html`: `type: "html"`。Claude が記事を読んで、1枚の完成HTMLスライドを直接作る。最も自由度が高い推奨モード。

---

## 選定基準（top_n 件を選ぶ）

`note_draft.md` の `daily-digest` で既にキュレーション済みのリストを正とし、さらに以下の基準で絞り込む。
`events.md` は再キュレーション用ではなく、選んだ記事の原文 URL や抜粋を復元するための補助情報として使う:

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
- その他の英字ブランド名・固有名詞も、読み上げに不安がある場合はカタカナ表記で書く。音声生成時にも `config/pronunciations.yaml` の読み辞書で補正される。
- **日付を読む際は「YYYY年M月D日」のように必ず漢字の年月日を含め、自然な日本語にすること**（例：「20260531」のような数字の羅列はNG）
- **ナレーションの内容は、必ずそのスライド（または画像プロンプト）に表示されているニュース記事と完全に一致させること。スライド上の数字や固有名詞と、ナレーションで読み上げる数字・固有名詞に一切のズレ・矛盾がないようにする。別の記事の内容を混ぜないこと。**
- アルファベット略語（GPT, API, LLM 等）はそのままで OK
- 数字（$1.3B など）はそのままで OK（VOICEVOX が処理）
- **読点「、」と句点「。」を意識して入れる**（自然な間）
- 専門用語は最初に短い言い換えを添える

2 〜 (top_n + 1). **ニューススライド**
   - id: `seg2`, `seg3`, ... (top_n 個)
   - `visual_mode = imagegen` の場合: `type: "concept"` を使い、`image_prompt` は英語で書く。
   - `visual_mode = ppt` の場合: `type: "data"` + `template: "exhibit"` を使い、`data` を日本語で書く。`image_prompt` は書かない。
   - `visual_mode = html` の場合: `type: "html"` を使い、`html` に完成HTMLドキュメントを書く。`image_prompt` は書かない。
   - スライド内に入れる見出し・数字・出典は、必ず元記事の内容と一致させる。
   - `visual_mode = ppt` では、記事を読んで「視聴者が一目でわかる、いい感じのPPTスライド」にする。決まり文句や型の押し付けより、記事ごとの自然な見せ方を優先する。
   - `visual_mode = html` では、記事そのものを読んで「プロのニュース解説スライド」になるように、レイアウト・余白・色・強調・情報量を自分で設計する。

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

## PPT風スライドのデータ作成ルール（visual_mode=ppt）

記事を読んで、要点が自然に伝わる1枚のPPTスライドにしてください。
細かい型を埋めるより、記事ごとに一番わかりやすい構成を選ぶことを優先します。

出力形式は `type: "data"` + `template: "exhibit"` です。後段テンプレートで描画するため、以下のフィールドは必ず埋めます。

- `headline`: その記事の一番強いニュース価値を、短い日本語タイトルにする。
- `subtitle`: なぜ重要なのかを、自然な1文で補足する。
- `left_fig`, `middle_fig`, `right_fig`: 記事の理解に必要な3つの要素を選ぶ。ラベルは記事に合わせて自然に付ける。
- `table`: 表があると理解しやすい場合だけ2〜3行で入れる。無理にBefore/After表にしない。不要なら `null`。
- `insight_bar`: 視聴者に残したい一言。長すぎず、記事から言える範囲にする。
- `source`: 元記事の媒体名・日付・URLなど、識別できる出典。

やってはいけないこと:

- `concept` や `image_prompt` を使う。
- すべての記事を「従来 / 今回 / 今後」「Before / After」の同じ型に押し込む。
- 「戦略的示唆：」を毎回機械的に付ける。
- 事実にない数字、企業名、効果を追加する。
- 長文を詰め込む。各 `caption` は1文、`value` は短い数字または短語にする。

---

## 直接HTMLスライドの作成ルール（visual_mode=html）

記事を読んで、その記事に一番合う完成スライドをHTML/CSSで直接作ってください。
「型を埋める」のではなく、コンサルティングファームの exhibit / インフォグラフィックとして、
1枚で論点・根拠・構造・示唆が伝わることを最優先します。

出力は `type: "html"` とし、`html` には完全なHTMLドキュメントを入れます。

HTMLを書く前に、各ニュースについて内部的に次の **slide brief** を作ってから構成してください。
この brief は JSON に出力しませんが、スライド内の要素として必ず反映します。

- `core_claim`: 記事から言える一番重要な主張
- `hard_facts`: 記事中の具体情報を5点以上（企業名、人物名、金額、成長率、日付、製品名、調査名など）
- `mechanism`: なぜその変化が起きているかを1本の因果で説明
- `exhibit_pattern`: 比較表 / 因果図 / バリューチェーン / 市場マップ / KPIブリッジ から最適な型
- `implications`: 日本SaaS企業への示唆を2点

もし `hard_facts` が3点未満しか取れない記事は、スライド化対象から外して別の記事を選んでください。

スライド設計の必須構造:

- 上部タイトルは、事実の説明ではなく **so-what 型の主張文** にする。
  - 良い例: 「AI投資は実験費から人件費級の戦略予算へ移った」
  - 悪い例: 「AI企業が月$7,500を支出」
- 1枚の構成は原則として **2階建て** にする。
  - 上段: so-what title + subtitle + 3〜5個の key numbers / hard facts strip
  - 中段: 左側に比較・チャート・市場マップ、右側に因果フロー・バリューチェーン・意思決定構造
  - 下段: implications 2点 + Executive takeaway
- 本文には必ず以下の4要素を入れる。
  - `Claim`: この記事から言える主張
  - `Evidence`: 記事中の数字・固有名詞・日付など具体根拠を5点以上
  - `Mechanism`: なぜそれが起きているのかを示す因果・フロー・比較
  - `Implication`: 日本SaaS企業にとっての示唆を2点
- レイアウトは必ず以下の exhibit パターンから1つ以上を使う。
  - 比較表: Before / Now / Next、旧モデル / 新モデル、既存SaaS / AI-native など
  - 因果図: きっかけ → 構造変化 → 事業インパクト
  - バリューチェーン: 入力 → 処理 → 出力 → 競争優位
  - 市場マップ: プレイヤー / 顧客 / 技術 / 収益モデルの関係
  - KPIブリッジ: 主要数字を起点に、何を意味するかを分解
- 右下または下部に、短い **Executive takeaway** を1本入れる。

デザインの基準:

- 1920x1080 の16:9スライド。`body` は `width: 1920px; height: 1080px; margin: 0; overflow: hidden;`。
- 日本語のニュース解説スライド。視聴者が3秒で主旨をつかみ、10秒で構造を理解できる構成にする。
- 記事ごとに最適なレイアウトを選ぶ。巨大KPIだけ、3カードだけ、タイムラインだけで終わらせない。
- 数字・矢印・ラベル・小さな表・注釈・凡例・ミニチャートを組み合わせ、情報密度のある1枚にする。
- 余白は意図的に使うが、画面の40%以上を空白のまま残さない。空白が多い場合は、key facts strip、比較軸、注釈、implications を追加する。
- 色は白/濃紺/青/アクセント1色程度。過度なグラデーション、装飾過多、安っぽいカード乱立を避ける。
- カードを使う場合は最大4個まで。カード同士の関係を矢印・軸・グルーピングで示す。
- 画像、外部フォント、外部CSS、外部JSは使わない。HTML内のCSSだけで完結させる。
- SVGは必要な簡単な図形・矢印・アイコン程度なら使ってよい。
- `script` タグは禁止。

内容の基準:

- 元記事の企業名、金額、日付、製品名、出典を正確に扱う。
- `note_draft.md` の要約だけでスライドを作り切らない。選んだ記事は `events.md` のURL/抜粋、または WebFetch した元記事本文から具体情報を補う。
- スライド上に最低5個の具体情報を入れる。ただし無根拠な推測や記事外の数字は追加しない。
- 記事にない数字や比較を作らない。
- 毎回同じ「従来/今回/今後」「Before/After」構成にしない。
- スライド末尾に小さく出典を入れる。
- `narration` はスライドに表示した内容と一致させる。

やってはいけないこと:

- 大見出し + KPIカードだけで終わるスライド。
- 大見出し + 2ブロックだけで、下半分に余白が残るスライド。
- 3つの独立カードを並べるだけで、カード間の関係が見えないスライド。
- 記事の要約文を短く並べただけのスライド。
- 箇条書きだけ、単なるタイムラインだけ、単なるKPI一覧だけのスライド。
- 「戦略的示唆」「なぜ重要か」などの抽象ラベルだけで、具体的な根拠が薄いスライド。
- 出典記事にない推測を、事実のように図解すること。

---

## slides.json 出力フォーマット

下記スキーマに**厳密に**従うこと。JSON 以外は出力しないこと（前置きや説明文は不要）。

### visual_mode=imagegen の例

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

### visual_mode=ppt の例

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
      "type": "data",
      "template": "exhibit",
      "data": {
        "headline": "Replit、1万規模のAIエージェントを稼働",
        "subtitle": "開発のボトルネックが、コードを書く作業からAIに仕事を渡す設計へ移り始めている。",
        "left_fig": {
          "title": "何が起きたか",
          "value": "10,000 agents",
          "caption": "Replit が多数のAIエージェントを並列稼働させている。"
        },
        "middle_fig": {
          "title": "なぜ重要か",
          "value": "開発の分業",
          "caption": "人間はコードを書くより、仕事の渡し方を設計する役割に寄る。"
        },
        "right_fig": {
          "title": "次に見る点",
          "value": "品質管理",
          "caption": "成果物レビューとタスク分解の設計が差になりやすい。"
        },
        "table": null,
        "insight_bar": "AI開発ツールの競争は、生成速度だけでなく、人間がどう仕事を設計するかに移っている。",
        "source": "元記事の媒体名 YYYY-MM-DD"
      },
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

### visual_mode=html の例

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
      "type": "html",
      "html": "<!DOCTYPE html><html lang=\"ja\"><head><meta charset=\"UTF-8\"><style>body{width:1920px;height:1080px;margin:0;overflow:hidden;font-family:'Hiragino Sans','Yu Gothic',sans-serif;background:#f7f9fc;color:#14213d}.slide{padding:72px 86px}.kicker{font-size:28px;color:#2563eb;font-weight:800}.headline{font-size:74px;line-height:1.08;font-weight:900;margin-top:28px}.grid{display:grid;grid-template-columns:1.2fr .8fr;gap:54px;margin-top:54px}.metric{font-size:120px;font-weight:900;color:#0f4c81}.note{font-size:34px;line-height:1.5}.source{position:absolute;right:72px;bottom:44px;font-size:22px;color:#667085}</style></head><body><main class=\"slide\"><div class=\"kicker\">AI DEVELOPMENT</div><h1 class=\"headline\">Replit、1万規模のAIエージェントを稼働</h1><section class=\"grid\"><div><div class=\"metric\">10,000</div><p class=\"note\">自然言語の指示から、多数のAIエージェントが並列にアプリやコードを生成する段階へ。</p></div><div class=\"note\">開発の競争軸は、コードを書く速さから、AIに渡す仕事の設計と成果物レビューへ移っている。</div></section><div class=\"source\">Source: 元記事 YYYY-MM-DD</div></main></body></html>",
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
- `visual_mode=imagegen` の本文ニュースは `type: "concept"` を使い、`image_prompt` を英語で書く
- `visual_mode=ppt` の本文ニュースは `type: "data"`, `template: "exhibit"` を使い、`image_prompt` を書かない
- `visual_mode=html` の本文ニュースは `type: "html"` を使い、`html` に完全なHTMLドキュメントを書く
- JSON のみを出力すること
- `note_draft.md` / `events.md` は入力として読むだけにし、`note_draft.md` や `slack.txt` は作成しないこと

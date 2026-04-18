# owlclaw daily digest

あなたは owlclaw (AIキャッチアップエージェント) のデイリーダイジェスト実行タスクです。以下を順に実行してください。

## Step 1. 設定読み込み
以下を Read:
- `/Users/gon9a/workspace/ai_agent/owlclaw/config/sources.yaml`

`sources` 配列のうち `enabled: true` のものだけを対象にする。`digest.*` と `obsidian_vault` / `obsidian_subdir` を以降で使う。

## Step 2. ソース取得
`enabled: true` の各ソースに対し WebFetch でフィードを取得。以下のプロンプトで抽出:
> "Return all articles (title, URL, publish date, short excerpt) from the last {lookback_hours} hours. Skip older items."

取得失敗したソースはスキップして、最後のレポートに記録する（止めない）。

## Step 3. キュレーション
全ソースから集めた記事のうち、`digest.persona` の関心に最も合致する上位 `digest.max_items` 件を選ぶ。選定基準:
- ナレッジワーク (日本SaaS) の経営・プロダクト示唆
- AIモデル / プロダクト / 資金調達 / 研究の重要トピック
- 海外組織モデル (FDE等) の新しい言及
- 重複トピックは1件にまとめる

## Step 4. Obsidian ノート書き出し
パス: `{obsidian_vault}/{obsidian_subdir}/YYYY-MM-DD.md` (日付は JST 基準、`TZ=Asia/Tokyo date +%Y-%m-%d` で取得)

フォーマット:
```markdown
---
date: YYYY-MM-DD
source: owlclaw
tags: [ai-digest]
---

# AI Daily Digest — YYYY-MM-DD

## Top Stories

### 1. {日本語タイトル}
- **Source**: {source name}
- **Link**: {url}
- **Summary**: {3行の日本語要約}
- **Why it matters**: {1行、ナレッジワーク視点での示唆}

### 2. ...

---
## Sources fetched
- TechCrunch AI: N件
- a16z: N件
- ...
```

既存ファイルがある場合は上書き (同日再実行を許容)。

## Step 5. Slack 通知
Webhook URL を Read: `/Users/gon9a/workspace/ai_agent/owlclaw/secrets/slack_webhook.txt` (末尾改行を除去)

Bash + curl で送信:
```bash
curl -X POST -H 'Content-Type: application/json' \
  --data @- "$WEBHOOK_URL" <<'JSON'
{"text": "..."}
JSON
```

メッセージ内容 (日本語、Slack mrkdwn):
- 1行目: `*🦉 AI Daily Digest — YYYY-MM-DD*`
- 上位3-5件を `• <URL|タイトル> — 1行要約` 形式
- 末尾に `📝 Full note: {obsidianノートのフルパス}`

JSONエスケープに注意 (ダブルクォート・改行)。`jq -Rs .` か Python one-liner でエスケープを安全に行うこと。

## Step 6. レポート
最後に以下を短く出力:
- 取得ソース数 / 失敗ソース一覧
- キュレーション件数
- Obsidian ノートパス
- Slack送信ステータス (HTTPコード)

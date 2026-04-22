# owlclaw — Claude Code 設定

## プロジェクト概要

AI ニュースダイジェストパイプライン。RSSフェッチ → LLMキュレーション → Obsidian保存 + Slack通知を自動化する。

## Claude Code スケジューラー設定

### スケジュールタスクのプロンプト（1行のみ）

```
bash /Users/gon9a/workspace/ai_agent/owlclaw/scripts/run_full.sh
```

### 必要なツール権限

- `Bash` — RSSフェッチ・配信スクリプトの実行
- `Read` — digest_input.md / daily_digest.md の読み取り
- `Write` — note_draft.md / slack_draft.txt の書き出し

## パイプライン概要

```
run_full.sh
  [1/3] uv run python scripts/fetch_rss.py
        → tmp/digest_input.md (過去24h以内の記事一覧)

  [2/3] claude --print --allowedTools "Read,Write" "$(cat prompts/claude_task.md)"
        → tmp/note_draft.md  (Obsidianノート)
        → tmp/slack_draft.txt (Slackメッセージ)

  [3/3] bash scripts/run.sh post YYYY-MM-DD
        → Obsidian vault にノート保存
        → Slack Webhook で通知送信
```

## ディレクトリ構成

```
owlclaw/
├── config/
│   └── sources.yaml        # RSSソース定義・ダイジェスト設定
├── prompts/
│   ├── daily_digest.md     # キュレーション・要約指示（Claude向け）
│   └── claude_task.md      # run_full.sh から渡すタスク指示
├── scripts/
│   ├── fetch_rss.py        # RSSフェッチ（uv run python）
│   ├── run.sh              # pre / post サブコマンド
│   ├── run_full.sh         # フルパイプライン（スケジューラー用エントリーポイント）
│   ├── slack_notify.sh     # Slack Webhook 送信
│   └── write_obsidian.sh   # Obsidian vault 書き出し
├── secrets/
│   └── slack_webhook.txt   # Slack Webhook URL（gitignore済み）
└── tmp/                    # 実行中間ファイル（gitignore済み）
```

## セットアップ

詳細は README.md を参照。

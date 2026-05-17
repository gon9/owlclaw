# owlclaw — Claude Code 設定

共通ルールは [AGENTS.md](AGENTS.md) を参照すること。

## プロジェクト概要

AI ニュースダイジェストパイプライン。RSSフェッチ → LLMキュレーション → Obsidian保存 + Slack通知を自動化する。

## Claude Code スケジューラー設定

### スケジュールタスクのプロンプト（1行のみ）

```
bash /Users/gon9a/workspace/ai-agent/owlclaw/scripts/run_full.sh
```

### 実行ルール（厳守）

- 上記の bash コマンド **1つだけ** を実行して終了すること
- 事前確認（ls, cat, ps, find 等）は **一切禁止** — スクリプト内で全て処理される
- 事後確認も **一切禁止** — 成功/失敗はスクリプトの exit code で判定される
- 追加のコマンドやツール呼び出しを行わないこと

### 必要なツール権限

- `Bash` — パイプラインスクリプトの実行（1コマンドのみ）

## パイプライン概要

```
run_full.sh → run_task.sh daily-digest → orchestrator.py
  [1/4] sources fetch    — sources/rss.py で RSS 取得 → tmp/<task-id>/events.md
  [2/4] state/profile    — state.json, profile.yaml を tmp/<task-id>/ に配置
  [3/4] claude --print   — LLM キュレーション → note_draft.md / slack.txt
  [4/4] outputs dispatch — write_obsidian.sh / slack_notify.sh
```

## ディレクトリ構成

```
owlclaw/
├── config/
│   └── sources.yaml        # RSSソース定義・ダイジェスト設定
├── prompts/                # Claude向けプロンプト
├── scripts/
│   ├── orchestrator.py     # タスクオーケストレーター（メインロジック）
│   ├── run_full.sh         # スケジューラー用エントリーポイント
│   ├── run_task.sh         # タスク実行ラッパー
│   ├── oneshot.sh          # 手動実行用ラッパー
│   ├── slack_notify.sh     # Slack Webhook 送信
│   ├── write_obsidian.sh   # Obsidian vault 書き出し
│   └── state.py            # 状態永続化モジュール
├── sources/                # ソースプラグイン (rss.py, gmail.py)
├── tasks/                  # タスク定義 YAML
├── secrets/                # Slack Webhook URL（gitignore済み）
└── tmp/                    # 実行中間ファイル（gitignore済み）
```

## セットアップ

詳細は README.md を参照。

# 🦉 owlclaw

AI ニュースダイジェストパイプライン。複数のRSSフィードから記事を収集し、LLMがキュレーション・日本語要約して Obsidian と Slack に配信する。

## アーキテクチャ

```
[スケジューラー: Claude Code]
        │
        ▼
  run_full.sh
  ┌─────────────────────────────────────────────┐
  │ [1/3] fetch_rss.py                          │
  │       RSSフェッチ → tmp/digest_input.md      │
  │                                             │
  │ [2/3] claude --print (claude_task.md)       │
  │       AI要約 → tmp/note_draft.md            │
  │               tmp/slack_draft.txt           │
  │                                             │
  │ [3/3] write_obsidian.sh + slack_notify.sh   │
  │       Obsidian vault 保存 + Slack 送信       │
  └─────────────────────────────────────────────┘
```

## セットアップ

### 1. 依存パッケージのインストール

```bash
uv sync
```

### 2. Slack Webhook URL の配置

```bash
echo "https://hooks.slack.com/services/YOUR/WEBHOOK/URL" > secrets/slack_webhook.txt
```

### 3. RSSソースの確認・編集

`config/sources.yaml` で `enabled: true` のソースが収集対象。`lookback_hours` で取得期間を調整できる。

## 実行方法

### Claude Code スケジューラー（推奨）

Claude Code のスケジュールタスクに以下の1行を設定する：

```
bash /Users/gon9a/workspace/ai_agent/owlclaw/scripts/run_full.sh
```

必要なツール権限: `Bash`, `Read`, `Write`

### 手動実行

```bash
# フルパイプライン
bash scripts/run_full.sh

# ステップ分割実行
bash scripts/run.sh pre                # RSSフェッチのみ
bash scripts/run.sh post 2025-01-15    # 配信のみ（要約済みの場合）
```

## ファイル構成

| パス | 役割 |
|------|------|
| `config/sources.yaml` | RSSソース定義・ペルソナ・lookback_hours 設定 |
| `prompts/daily_digest.md` | キュレーション基準・要約スタイル・出力フォーマット |
| `prompts/claude_task.md` | run_full.sh がClaudeに渡すタスク指示 |
| `scripts/fetch_rss.py` | RSSフェッチ・整形・Markdown出力 |
| `scripts/run_full.sh` | フルパイプライン（スケジューラーエントリーポイント） |
| `scripts/run.sh` | pre / post サブコマンド |
| `scripts/write_obsidian.sh` | Obsidian vault への書き出し |
| `scripts/slack_notify.sh` | Slack Webhook 送信 |
| `secrets/slack_webhook.txt` | Slack Webhook URL（**gitignore済み・要手動配置**） |
| `tmp/` | 実行中間ファイル（**gitignore済み**） |

## 設定リファレンス（config/sources.yaml）

```yaml
digest:
  max_items: 6          # ダイジェストに掲載する最大記事数
  lookback_hours: 24    # 取得対象期間（時間）
  language: ja
  persona: |            # Claudeへのペルソナ指示

sources:
  - name: TechCrunch AI
    url: https://techcrunch.com/category/artificial-intelligence/feed/
    type: rss
    enabled: true       # false にすると除外
```

## 開発

```bash
# Lintチェック
uv run ruff check scripts/

# 自動修正
uv run ruff check --fix scripts/
```

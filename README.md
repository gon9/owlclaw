# 🦉 owlclaw

AI 自律タスクランナー。複数の Source（RSS / Gmail）からイベントを収集し、
Claude Code CLI がキュレーション・要約・集計を行い、Obsidian と Slack へ配信する。

## アーキテクチャ

```
tasks/<task-id>.yaml
        │
        ▼
  scripts/orchestrator.py
  ┌──────────────────────────────────────────────┐
  │ [1/4] Sources fetch  → tmp/<task-id>/events.md │
  │ [2/4] State / profile 配置                    │
  │ [3/4] claude --print → note_draft.md/slack.txt │
  │ [4/4] write_obsidian.sh + slack_notify.sh     │
  └──────────────────────────────────────────────┘
        │
        ▼
  state/<namespace>.json  (差分追跡・累計集計)
```

## 実装済みタスク

| タスク ID | スケジュール | Source | 出力 |
|---|---|---|---|
| `daily-digest` | 毎朝 9:00 | RSS 全源 | Obsidian + Slack |
| `blog-watch` | 毎週月曜 9:00 | RSS 7 源（差分のみ） | Slack |
| `birthday-month` | 毎月 1 日 8:00 | なし（誕生月のみ起動） | Slack |
| `payment-watch` | 毎週日曜 21:00 | Gmail 決済メール | Slack |

## セットアップ

### 1. 依存パッケージのインストール

```bash
uv sync
```

### 2. Slack Webhook URL の配置

```bash
echo "https://hooks.slack.com/services/YOUR/WEBHOOK/URL" > secrets/slack_webhook.txt
```

### 3. RSS ソースの確認・編集

`config/sources.yaml` で `enabled: true` のソースが収集対象。

### 4. Gmail OAuth 設定（payment-watch を使う場合）

#### 4-1. GCP でクレデンシャル作成

1. [GCP コンソール](https://console.cloud.google.com/) → **API とサービス** → **ライブラリ** → **Gmail API** を有効化
2. **認証情報** → **+ 認証情報を作成** → **OAuth 2.0 クライアント ID** → **デスクトップ アプリ**
3. JSON をダウンロードして `secrets/gmail_oauth.json` として保存

#### 4-2. 初回 OAuth フロー（ブラウザ認証）

```bash
uv run python scripts/auth_gmail.py
```

ブラウザが開き、Google アカウントでの許可画面が表示される。
承認すると `secrets/gmail_token.json` が生成され、以降は自動リフレッシュされる。

> **注意**: `secrets/` は `.gitignore` 済み。リポジトリにコミットしないこと。

## 実行方法

```bash
# タスク実行（スケジューラーエントリーポイント）
bash scripts/run_task.sh daily-digest
bash scripts/run_task.sh blog-watch
bash scripts/run_task.sh payment-watch

# 手動1回実行
bash scripts/oneshot.sh blog-watch

# テスト用日付シミュレーション
bash scripts/run_task.sh birthday-month --simulate-date 2026-10-01
```

## ファイル構成

| パス | 役割 |
|------|------|
| `config/sources.yaml` | RSS ソース定義・ペルソナ・lookback_hours |
| `config/profile.yaml` | ユーザープロファイル（誕生日・居住地・予算等） |
| `tasks/*.yaml` | タスク定義（schedule / sources / prompt / outputs） |
| `prompts/*.md` | Claude へのタスク指示書 |
| `sources/rss.py` | RSS source プラグイン |
| `sources/gmail.py` | Gmail source プラグイン（要 OAuth 設定） |
| `scripts/orchestrator.py` | タスクオーケストレーター |
| `scripts/auth_gmail.py` | Gmail OAuth 初回認証フロー |
| `scripts/run_task.sh` | `orchestrator.py` を `uv run` で起動するラッパー |
| `scripts/oneshot.sh` | 手動1回実行ラッパー |
| `scripts/write_obsidian.sh` | Obsidian vault への書き出し |
| `scripts/slack_notify.sh` | Slack Webhook 送信 |
| `secrets/` | 認証情報（**gitignore済み・要手動配置**） |
| `state/` | タスクごとの永続 state JSON（**gitignore済み**） |
| `tmp/` | 実行中間ファイル（**gitignore済み**） |

## 開発

```bash
# Lint + テスト（順序必須）
uv run ruff check --fix sources/ scripts/state.py scripts/orchestrator.py tests/
uv run pytest tests/ -v
```

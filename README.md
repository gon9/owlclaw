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

`tasks/*.yaml` の `ai.provider` / `ai.model` で、タスクごとに利用する
AI provider とモデル alias/full name を指定できる。現在の provider 実装は
`claude` / `anthropic`（Claude Code CLI）と `antigravity` / `agy`
（Antigravity CLI）で、`ai.model: fable` のような値は
`claude --print --model fable`、`ai.provider: agy` の場合は
`agy --print --model "<model>"` として渡される。
`ai.fallback_models` を指定すると、primary model の CLI 実行が失敗した場合に
同じ provider で後続モデルを順番に試す。運用時だけ差し替えたい場合は
`OWLCLAW_AI_FALLBACK_MODELS=opus,sonnet` のようにカンマ区切りで上書きできる。

動画スライドの本文表現は `video.visual_mode` で切り替える。
`imagegen` は従来どおり `concept` + Codex imagegen でPNG化し、`ppt` は
Claude fable が `data` + `template: exhibit` のPPT風構造データを作り、
HTMLテンプレートでPNG化する。

## 実装済みタスク

### ニュース・情報収集

| タスク ID | スケジュール | Source | 出力 |
|---|---|---|---|
| `daily-digest` | 毎朝 7:00 | RSS（AI/Tech/VC 全源） | Obsidian + Slack |
| `blog-watch` | 毎週月曜 9:00 | RSS（差分のみ） | Slack |
| `arxiv-digest` | 毎朝 10:00 | arXiv API（cs.AI / cs.CL / cs.LG） | Obsidian + Slack |
| `twitter-digest` | 毎朝 8:10 | X(Twitter) フォロー＋キーワード | Obsidian + Slack |
| `bluesky-papers` | 毎朝 9:00 | Bluesky 公開API（AI/ML Starter Pack 起点、論文URL抽出） | Obsidian + Slack |
| `podcast-digest` | 手動 / 任意 | Podcast / YouTube 字幕 | Obsidian + Slack |

### カレンダー・行動支援

| タスク ID | スケジュール | Source | 出力 |
|---|---|---|---|
| `departure-time` | 毎朝 7:00 | Google Calendar（物理外出予定） | Slack |
| `visit-briefing` | 毎晩 20:00 | Google Calendar（翌日訪問先） | Obsidian + Slack |

### 旅行・旅程管理

| タスク ID | スケジュール | Source | 出力 |
|---|---|---|---|
| `travel-watch` | 毎朝 8:00 | Gmail（予約確認メール） | Obsidian + state 更新 |
| `travel-checklist` | 毎朝 8:05 | state（旅程台帳） | Slack（D-14/7/3/1） |

### ライフイベント・家計

| タスク ID | スケジュール | Source | 出力 |
|---|---|---|---|
| `birthday-month` | 毎月 1 日 8:00 | profile（誕生月のみ起動） | Slack |
| `payment-watch` | 毎週日曜 21:00 | Gmail（決済メール） | Slack |

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

### 4. Google Calendar OAuth 設定（departure-time / visit-briefing を使う場合）

1. [GCP コンソール](https://console.cloud.google.com/) → **Google Calendar API** を有効化
2. **OAuth 2.0 クライアント ID**（デスクトップ アプリ）を作成して `secrets/calendar_oauth.json` として保存

```bash
uv run python scripts/auth_calendar.py --login-hint atsushi.tmail@gmail.com
```

承認すると `secrets/calendar_token.json` が生成される。

### Google OAuth 運用ルール

`owlclaw` の Google / GCP 運用は `atsushi.tmail@gmail.com` と
GCP project `ai-agent-gon9a` に統一する。

- `calendar_oauth.json` / `drive_oauth.json` / `gmail_oauth.json` / `youtube_oauth.json`
  は同じ `ai-agent-gon9a` の desktop OAuth client を使う
- Drive / Calendar / Gmail / YouTube の token は `atsushi.tmail@gmail.com` で発行する
- YouTube のアップロード先は `atsushi.tmail@gmail.com` の個人チャンネル `@GON9878`
- 初回または検証時の YouTube 公開設定は `youtube_privacy: unlisted` を使う
- token 本体は表示しない。状態確認は `uv run python scripts/doctor_google_auth.py` を使う

### 5. Gmail OAuth 設定（payment-watch / travel-watch を使う場合）

#### 5-1. GCP でクレデンシャル作成

1. [GCP コンソール](https://console.cloud.google.com/) → **API とサービス** → **ライブラリ** → **Gmail API** を有効化
2. Drive/Calendar/YouTube と同じ OAuth client JSON を `secrets/gmail_oauth.json` として保存

#### 5-2. 初回 OAuth フロー（ブラウザ認証）

```bash
uv run python scripts/auth_gmail.py --login-hint atsushi.tmail@gmail.com
```

ブラウザが開き、Google アカウントでの許可画面が表示される。
承認すると `secrets/gmail_token.json` が生成され、以降は自動リフレッシュされる。

### 6. YouTube OAuth 設定（video-digest → YouTube アップロードを使う場合）

1. [GCP コンソール](https://console.cloud.google.com/) → **API とサービス** → **ライブラリ** → **YouTube Data API v3** を有効化
2. **認証情報** → Drive/Calendar と同じ **OAuth 2.0 クライアント ID** の JSON をダウンロードして `secrets/youtube_oauth.json` として保存（既存の `drive_oauth.json` と同一ファイルのコピーで OK）

```bash
uv run python scripts/auth_youtube.py --login-hint atsushi.tmail@gmail.com
```

ブラウザが開き、YouTube upload 権限の許可画面が表示される。
承認すると `secrets/youtube_token.json` が生成され、以降は自動リフレッシュされる。

#### Google Home での再生

動画タイトルが `owlclaw AI Digest YYYY-MM-DD` で統一されるため、Google Home / Nest デバイスから以下のように再生可能:

```
「OK Google, YouTube で owlclaw を再生」
```

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

# video-digest のスライドだけを確認（slides.json + PNG を Google Drive に upload、音声/動画/Slackなし）
bash scripts/run_task.sh video-digest --debug-slides
bash scripts/run_task.sh video-digest --simulate-date 2026-06-11 --debug-slides

# fable のスライド生成方式を軽く比較
bash scripts/run_task.sh video-digest --simulate-date 2026-06-11 --debug-slides --visual-mode ppt
bash scripts/run_task.sh video-digest --simulate-date 2026-06-11 --debug-slides --visual-mode html

# Antigravity CLI を使う場合は tasks/*.yaml の ai.provider を agy または antigravity にする
# ai:
#   provider: agy
#   model: "Gemini 3.5 Flash (High)"
# ※ model: agy はCLI名として扱われ、--model には渡されない
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
| `sources/calendar.py` | Google Calendar source プラグイン（要 OAuth 設定） |
| `sources/arxiv.py` | arXiv API source プラグイン |
| `sources/twitter.py` | X(Twitter) source プラグイン |
| `sources/podcast.py` | Podcast / YouTube 字幕 source プラグイン |
| `tools/travel.py` | 旅程台帳ユーティリティ（D-N 計算・旅程マージ等） |
| `tools/upload_drive.py` | Google Drive アップロードユーティリティ |
| `tools/upload_youtube.py` | YouTube アップロードユーティリティ（Google Home 再生用） |
| `scripts/orchestrator.py` | タスクオーケストレーター |
| `scripts/auth_gmail.py` | Gmail OAuth 初回認証フロー |
| `scripts/auth_calendar.py` | Google Calendar OAuth 初回認証フロー |
| `scripts/auth_youtube.py` | YouTube OAuth 初回認証フロー |
| `scripts/run_task.sh` | `orchestrator.py` を `uv run` で起動するラッパー |
| `scripts/oneshot.sh` | 手動1回実行ラッパー |
| `scripts/write_obsidian.sh` | Obsidian vault への書き出し |
| `scripts/slack_notify.sh` | Slack Webhook 送信 |
| `scripts/setup_host.sh` | macOS ホスト初回セットアップ（launchd 登録） |
| `secrets/` | 認証情報（**gitignore済み・要手動配置**） |
| `state/` | タスクごとの永続 state JSON（**gitignore済み**） |
| `tmp/` | 実行中間ファイル（**gitignore済み**） |

## 開発

```bash
# Lint + テスト（順序必須）
uv run ruff check --fix sources/ scripts/state.py scripts/orchestrator.py tests/
uv run pytest tests/ -v
```

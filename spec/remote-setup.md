# owlclaw リモート (SSH 先) セットアップ手順

owlclaw を常時稼働マシン (例: Intel Mac の `gon9a-book`) で動かすための手順。
**`scripts/setup-remote.sh` 一発で 80% 自動化、残り 20% は手動 (codex login / uv install)。**

## 前提

| 項目 | 要件 |
|---|---|
| OS | macOS 12+ (Intel x64 or Apple Silicon arm64) |
| 権限 | sudo 不要、ユーザー権限のみ |
| ネットワーク | GitHub への HTTPS 到達 |
| ディスク | ~3GB 以上の空き |

## ステップ

### 0. 前提パッケージの手動 install

setup-remote.sh が前提とするツール：

```bash
# uv (Python パッケージマネージャ)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Node.js (Homebrew or NVM 経由)
brew install node            # Homebrew がある場合
# または
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.0/install.sh | bash
nvm install --lts
```

### 1. owlclaw リポジトリ clone

```bash
mkdir -p ~/workspace/ai-agent
cd ~/workspace/ai-agent
git clone https://github.com/gon9/owlclaw.git
cd owlclaw
```

### 2. setup-remote.sh 実行

```bash
bash scripts/setup-remote.sh
```

このスクリプトは idempotent。**何度叩いても同じ状態に収束**します。実行内容：

| 段 | 内容 | 容量 | 時間 |
|---|---|---|---|
| 0 | py7zr (pip) | ~5MB | 数秒 |
| 1 | VOICEVOX Engine 0.19.1 ダウンロード + 展開 | ~1.7GB | 1-3分 |
| 2 | VOICEVOX を launchd で常駐化 | - | 30秒 (起動待ち) |
| 3 | Puppeteer (`node_modules/puppeteer`, owlclaw 配下) | ~400MB | 30-60秒 |
| 4 | codex CLI バイナリ install | ~86MB | 30秒 |
| 5 | uv sync (Python deps) | ~100MB | 数秒 |

### 3. codex login (手動・初回のみ)

```bash
~/.local/bin/codex login
# → 出力された URL をローカルブラウザで開いて認証
# → auth code を貼り付けて完了
```

ChatGPT サブスクリプションがある場合は OAuth で OK。
API key を使う場合は `printenv OPENAI_API_KEY | codex login --with-api-key`。

### 4. .env / secrets セットアップ

```bash
cp .env.example .env       # 必要な ENV (Slack URL 等) を埋める
mkdir -p secrets/
# secrets/SLACK_WEBHOOK_URL などを配置
```

### 5. 動作確認

```bash
# VOICEVOX
curl http://127.0.0.1:50021/version
# → "0.19.1"

# 動画パイプライン (daily-digest が事前実行されている前提)
bash scripts/run_task.sh video-digest
# → tmp/video-digest/digest_YYYYMMDD.mp4 が生成される
```

## バージョン pinning

`scripts/setup-remote.sh` 先頭で env 変数で上書き可能：

```bash
VOICEVOX_VERSION=0.19.1 CODEX_VERSION=0.135.0 bash scripts/setup-remote.sh
```

### なぜ VOICEVOX 0.19.1 か？

VOICEVOX Engine 0.20+ は numpy 2.x をバンドルしており、macOS 12 では
`Symbol not found: _cblas_caxpy$NEWLAPACK$ILP64` エラーで起動失敗する
（Accelerate framework の新シンボルが macOS 13.3+ 必須）。

macOS 13.3+ で運用する場合は `VOICEVOX_VERSION=0.25.2` 等の最新版を使用可。

## トラブルシューティング

### VOICEVOX が起動しない

```bash
tail -f ~/voicevox/engine.err.log
# numpy ImportError → macOS バージョン不整合。VOICEVOX_VERSION を下げる
# Permission denied → xattr -dr com.apple.quarantine ~/voicevox/macos-x64/
```

### Puppeteer の Chromium が DL 失敗

```bash
# プロキシ環境などで失敗する場合
cd ~/workspace/ai-agent/owlclaw
PUPPETEER_DOWNLOAD_HOST=https://storage.googleapis.com npm install
```

### codex login で URL が表示されるが開けない

remote SSH 環境ではブラウザが開けない。出力された URL を **ローカルマシンの**
ブラウザに貼り付けて認証 → コールバック URL を SSH 越しの codex プロンプトに貼り戻す。

### launchd で VOICEVOX が再起動ループ

```bash
launchctl unload ~/Library/LaunchAgents/com.voicevox.engine.plist
# err log で原因特定 → 修正後再 load
launchctl load -w ~/Library/LaunchAgents/com.voicevox.engine.plist
```

## アンインストール

```bash
# VOICEVOX
launchctl unload -w ~/Library/LaunchAgents/com.voicevox.engine.plist
rm ~/Library/LaunchAgents/com.voicevox.engine.plist
rm -rf ~/voicevox

# codex
rm -f ~/.local/bin/codex
rm -rf ~/.codex

# Puppeteer
rm -rf ~/workspace/ai-agent/owlclaw/node_modules
```

## 関連ドキュメント

- `spec/voicevox-server.md` — VOICEVOX 単体運用ガイド
- `spec/video-pipeline.md` — 動画パイプライン全体仕様
- `tasks/video-digest.yaml` — video-digest タスク定義

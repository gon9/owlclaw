#!/usr/bin/env bash
# owlclaw ホストセットアップスクリプト (MBP 2016 / 常時稼働AIエージェントマシン向け)
# 使い方: bash scripts/setup_host.sh
# 冪等: 何度実行しても安全

set -euo pipefail

PROJ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_URL="https://github.com/gon9/owlclaw.git"
INSTALL_DIR="$HOME/workspace/ai-agent/owlclaw"
OBSIDIAN_VAULT="$HOME/Library/CloudStorage/GoogleDrive-atsushi.tmail@gmail.com/マイドライブ"

log() { echo "[setup] $*"; }
warn() { echo "[setup] WARNING: $*" >&2; }

# ────────────────────────────────────────────
# 1. スリープ無効化
# ────────────────────────────────────────────
log "スリープ設定を無効化..."
sudo pmset -a sleep 0 disablesleep 1 hibernatemode 0 displaysleep 0
# sudo が不要な操作はここ以降ユーザー権限で実行される

# ────────────────────────────────────────────
# 2. nvm + Node.js
# ────────────────────────────────────────────
if [[ ! -d "$HOME/.nvm" ]]; then
  log "nvm をインストール..."
  curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.3/install.sh | bash
fi

export NVM_DIR="$HOME/.nvm"
# shellcheck disable=SC1091
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"

if ! node --version &>/dev/null; then
  log "Node.js LTS をインストール..."
  nvm install --lts
fi
log "Node.js: $(node --version)"

# ────────────────────────────────────────────
# 3. Claude Code CLI
# ────────────────────────────────────────────
if ! claude --version &>/dev/null; then
  log "Claude Code CLI をインストール..."
  npm install -g @anthropic-ai/claude-code
fi
log "Claude Code: $(claude --version)"

# ────────────────────────────────────────────
# 4. uv
# ────────────────────────────────────────────
if [[ ! -f "$HOME/.local/bin/uv" ]]; then
  log "uv をインストール..."
  curl -LsSf https://astral.sh/uv/install.sh | sh
fi
source "$HOME/.local/bin/env"
log "uv: $(uv --version)"

# ────────────────────────────────────────────
# 5. .zshrc に PATH 追加
# ────────────────────────────────────────────
ZSHRC="$HOME/.zshrc"
if ! grep -q "NVM_DIR" "$ZSHRC" 2>/dev/null; then
  log ".zshrc に nvm を追加..."
  cat >> "$ZSHRC" << 'ZSHEOF'

# nvm
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
ZSHEOF
fi
if ! grep -q "local/bin/env" "$ZSHRC" 2>/dev/null; then
  log ".zshrc に uv を追加..."
  echo 'source $HOME/.local/bin/env' >> "$ZSHRC"
fi

# ────────────────────────────────────────────
# 6. owlclaw リポジトリ
# ────────────────────────────────────────────
if [[ ! -d "$INSTALL_DIR" ]]; then
  log "owlclaw を clone..."
  mkdir -p "$(dirname "$INSTALL_DIR")"
  git clone "$REPO_URL" "$INSTALL_DIR"
fi

# ────────────────────────────────────────────
# 7. Python 依存関係
# ────────────────────────────────────────────
log "uv sync..."
cd "$INSTALL_DIR"
uv sync

# ────────────────────────────────────────────
# 8. .env 作成
# ────────────────────────────────────────────
ENV_FILE="$INSTALL_DIR/.env"
if [[ ! -f "$ENV_FILE" ]]; then
  log ".env を作成..."
  cat > "$ENV_FILE" << EOF
OBSIDIAN_VAULT=$OBSIDIAN_VAULT
TWITTER_BEARER_TOKEN=
EOF
  warn ".env の TWITTER_BEARER_TOKEN を手動で設定してください"
else
  # OBSIDIAN_VAULT が古いパスのままなら更新
  if ! grep -q "CloudStorage" "$ENV_FILE"; then
    log ".env の OBSIDIAN_VAULT を Google Drive パスに更新..."
    sed -i "" "s|OBSIDIAN_VAULT=.*|OBSIDIAN_VAULT=$OBSIDIAN_VAULT|" "$ENV_FILE"
  fi
fi

# ────────────────────────────────────────────
# 9. secrets ディレクトリ
# ────────────────────────────────────────────
SECRETS_DIR="$INSTALL_DIR/secrets"
mkdir -p "$SECRETS_DIR"
for f in slack_webhook.txt calendar_oauth.json calendar_token.json; do
  if [[ ! -f "$SECRETS_DIR/$f" ]]; then
    warn "secrets/$f が存在しません。手動でコピーしてください:"
    warn "  scp <source>:$SECRETS_DIR/$f $SECRETS_DIR/$f"
  fi
done

# ────────────────────────────────────────────
# 10. launchd: caffeinate 常駐
# ────────────────────────────────────────────
AGENTS_DIR="$HOME/Library/LaunchAgents"
mkdir -p "$AGENTS_DIR"

cat > "$AGENTS_DIR/com.gon9a.caffeinate.plist" << 'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key><string>com.gon9a.caffeinate</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/caffeinate</string>
        <string>-dimsu</string>
    </array>
    <key>KeepAlive</key><true/>
    <key>RunAtLoad</key><true/>
</dict>
</plist>
PLIST

# ────────────────────────────────────────────
# 11. launchd: キーチェーン自動アンロック
# ────────────────────────────────────────────
cat > "$AGENTS_DIR/com.gon9a.unlock-keychain.plist" << 'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key><string>com.gon9a.unlock-keychain</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/sh</string>
        <string>-c</string>
        <string>security unlock-keychain -p "$(cat $HOME/.keychain_pass)" $HOME/Library/Keychains/login.keychain-db</string>
    </array>
    <key>RunAtLoad</key><true/>
</dict>
</plist>
PLIST

# パスワードファイル（なければ作成）
PASS_FILE="$HOME/.keychain_pass"
if [[ ! -f "$PASS_FILE" ]]; then
  warn ".keychain_pass が存在しません。ログインパスワードを保存してください:"
  warn "  echo 'your_password' > $PASS_FILE && chmod 600 $PASS_FILE"
else
  chmod 600 "$PASS_FILE"
fi

# ────────────────────────────────────────────
# 12. launchd: owlclaw 各タスク plist 生成
# ────────────────────────────────────────────
# 引数: task_id  hour  minute  [extra_interval_xml]
_make_task_plist() {
  local task_id="$1" hour="$2" minute="$3" extra="${4:-}"
  cat > "$AGENTS_DIR/com.gon9a.owlclaw-${task_id}.plist" << PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key><string>com.gon9a.owlclaw-${task_id}</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/zsh</string>
        <string>-c</string>
        <string>source \$HOME/.local/bin/env; export NVM_DIR="\$HOME/.nvm"; [ -s "\$NVM_DIR/nvm.sh" ] &amp;&amp; \\. "\$NVM_DIR/nvm.sh"; security unlock-keychain -p "\$(cat \$HOME/.keychain_pass)" \$HOME/Library/Keychains/login.keychain-db 2>/dev/null || true; cd $INSTALL_DIR &amp;&amp; bash scripts/run_task.sh ${task_id}</string>
    </array>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key><integer>${hour}</integer>
        <key>Minute</key><integer>${minute}</integer>
        ${extra}
    </dict>
    <key>StandardOutPath</key><string>$INSTALL_DIR/tmp/launchd-${task_id}.log</string>
    <key>StandardErrorPath</key><string>$INSTALL_DIR/tmp/launchd-${task_id}-err.log</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>HOME</key><string>$HOME</string>
        <key>USER</key><string>$USER</string>
    </dict>
</dict>
</plist>
PLIST
}

# タスク一覧 (task_id  hour  minute  optional:extra_xml)
_make_task_plist "departure-time"   7  0
_make_task_plist "travel-watch"     8  0
_make_task_plist "travel-checklist" 8  5
_make_task_plist "twitter-digest"   8 10
_make_task_plist "birthday-month"   8  0  "<key>Day</key><integer>1</integer>"
_make_task_plist "daily-digest"     7  0
_make_task_plist "blog-watch"       9  0  "<key>Weekday</key><integer>1</integer>"
_make_task_plist "arxiv-digest"    10  0
_make_task_plist "visit-briefing"  20  0
_make_task_plist "payment-watch"   21  0  "<key>Weekday</key><integer>0</integer>"

# ────────────────────────────────────────────
# 13. launchd 登録 (ユーザー権限で実行すること — sudo 不要)
# ────────────────────────────────────────────
mkdir -p "$INSTALL_DIR/tmp"
if [[ "$(id -u)" == "0" ]]; then
  warn "launchd の登録は sudo なしで実行してください。スキップします。"
  warn "  bash scripts/setup_host.sh を sudo なしで再実行してください。"
else
  for label in com.gon9a.caffeinate com.gon9a.unlock-keychain; do
    launchctl unload "$AGENTS_DIR/$label.plist" 2>/dev/null || true
    launchctl load "$AGENTS_DIR/$label.plist"
    log "launchd: $label 登録完了"
  done
  for task_id in departure-time travel-watch travel-checklist twitter-digest birthday-month daily-digest blog-watch arxiv-digest visit-briefing payment-watch; do
    label="com.gon9a.owlclaw-${task_id}"
    launchctl unload "$AGENTS_DIR/$label.plist" 2>/dev/null || true
    launchctl load "$AGENTS_DIR/$label.plist"
    log "launchd: $label 登録完了"
  done
fi

# ────────────────────────────────────────────
# 完了
# ────────────────────────────────────────────
echo ""
echo "========================================"
echo " owlclaw ホストセットアップ 完了"
echo "========================================"
echo ""
echo "【手動対応が必要な項目】"
echo ""

if [[ ! -f "$HOME/.keychain_pass" ]]; then
  echo "  1. キーチェーンパスワードを保存:"
  echo "     echo 'ログインパスワード' > ~/.keychain_pass && chmod 600 ~/.keychain_pass"
  echo ""
fi

for f in slack_webhook.txt calendar_oauth.json calendar_token.json; do
  if [[ ! -f "$SECRETS_DIR/$f" ]]; then
    echo "  - secrets/$f を配置してください"
  fi
done

echo ""
echo "  ★ Claude Code 認証 (未ログインの場合):"
echo "     claude   ← ブラウザでログイン"
echo ""
echo "  ★ 動作確認:"
echo "     bash $INSTALL_DIR/scripts/run_full.sh"
echo ""

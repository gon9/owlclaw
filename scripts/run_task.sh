#!/usr/bin/env bash
# owlclaw: タスク実行ラッパー
# 使い方: bash scripts/run_task.sh <task-id>
#   例:   bash scripts/run_task.sh daily-digest

set -euo pipefail

PROJ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# .env から環境変数を読み込む（スケジューラー実行時にも確実に設定されるように）
if [[ -f "$PROJ/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$PROJ/.env"
  set +a
fi

TASK_ID="${1:-}"

if [[ -z "$TASK_ID" ]]; then
  echo "Usage: run_task.sh <task-id>" >&2
  exit 1
fi

echo "=== owlclaw: run_task $TASK_ID ==="
# SSH/launchd の最小 PATH でも ~/.local/bin や Homebrew の CLI を見つけられるようにする
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"

# NVM node bin を PATH に追加（SSH/launchd 非インタラクティブ対策）
NVM_NODE_BIN="$(
  find "$HOME/.nvm/versions/node" -mindepth 2 -maxdepth 2 -type d -name bin -print \
    2>/dev/null | sort -V | tail -1 || true
)"
if [[ -n "$NVM_NODE_BIN" ]]; then
  export PATH="$NVM_NODE_BIN:$PATH"
fi

# macOS Keychain をアンロック（Claude Code の認証情報取得に必要）
KEYCHAIN_PASS_FILE="$HOME/.keychain_pass"
if [[ -f "$KEYCHAIN_PASS_FILE" ]]; then
  security unlock-keychain -p "$(cat "$KEYCHAIN_PASS_FILE")" \
    "$HOME/Library/Keychains/login.keychain-db" 2>/dev/null || true
fi

if [[ -n "${UV:-}" ]]; then
  UV_BIN="$UV"
elif [[ -x "$HOME/.local/bin/uv" ]]; then
  UV_BIN="$HOME/.local/bin/uv"
else
  UV_BIN="$(command -v uv || true)"
fi

if [[ -z "$UV_BIN" ]]; then
  echo "Error: uv が見つかりません。PATH または UV 環境変数を確認してください。" >&2
  exit 1
fi

"$UV_BIN" run --directory "$PROJ" python "$PROJ/scripts/orchestrator.py" "$TASK_ID" "${@:2}"

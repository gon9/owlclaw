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
# NVM node bin を PATH に追加（SSH/launchd 非インタラクティブ対策）
NVM_NODE_BIN="$(ls -d "$HOME"/.nvm/versions/node/*/bin 2>/dev/null | sort -V | tail -1)"
if [[ -n "$NVM_NODE_BIN" ]]; then
  export PATH="$NVM_NODE_BIN:$PATH"
fi

UV="${UV:-$HOME/.local/bin/uv}"
"$UV" run --directory "$PROJ" python "$PROJ/scripts/orchestrator.py" "$TASK_ID"

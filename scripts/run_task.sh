#!/usr/bin/env bash
# owlclaw: タスク実行ラッパー
# 使い方: bash scripts/run_task.sh <task-id>
#   例:   bash scripts/run_task.sh daily-digest

set -euo pipefail

PROJ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TASK_ID="${1:-}"

if [[ -z "$TASK_ID" ]]; then
  echo "Usage: run_task.sh <task-id>" >&2
  exit 1
fi

echo "=== owlclaw: run_task $TASK_ID ==="
uv run python "$PROJ/scripts/orchestrator.py" "$TASK_ID"

#!/usr/bin/env bash
# owlclaw: 1回限りのタスク手動実行（Standing Order 昇格前の試し打ちや緊急実行に使う）
#
# 使い方:
#   bash scripts/oneshot.sh <task-id>
#   bash scripts/oneshot.sh blog-watch
#   bash scripts/oneshot.sh birthday-month --simulate-date 2026-10-01

set -euo pipefail
PROJ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <task-id> [orchestrator-args...]" >&2
  exit 1
fi

echo "=== [oneshot] task: $1 ===" >&2
bash "$PROJ/scripts/run_task.sh" "$@"

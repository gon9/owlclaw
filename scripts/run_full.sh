#!/usr/bin/env bash
# owlclaw フルパイプライン — run_task.sh daily-digest の薄いラッパー
# 使い方: bash scripts/run_full.sh
# Claude Code スケジューラーのプロンプト:
#   bash /Users/gon9a/workspace/ai_agent/owlclaw/scripts/run_full.sh

set -euo pipefail

PROJ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

bash "$PROJ/scripts/run_task.sh" daily-digest

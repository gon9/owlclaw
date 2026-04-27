#!/usr/bin/env bash
# owlclaw フルパイプライン（1本実行版）
# 使い方: bash run_full.sh
# Claude Code スケジューラーのプロンプト:
#   bash /Users/gon9a/workspace/ai_agent/owlclaw/scripts/run_full.sh

set -euo pipefail

PROJ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DATE=$(TZ=Asia/Tokyo date +%Y-%m-%d)

echo "=== [1/3] RSS フェッチ ==="
bash "$PROJ/scripts/run.sh" pre

echo "=== [2/3] AI 要約 (claude --print) ==="
cat "$PROJ/prompts/claude_task.md" | claude --print --allowedTools "Read,Write"

echo "=== [3/3] 配信 (Obsidian + Slack) ==="
bash "$PROJ/scripts/run.sh" post "$DATE"

echo "=== owlclaw 完了 ($DATE) ==="

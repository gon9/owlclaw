#!/usr/bin/env bash
# owlclaw フルパイプライン（1本実行版）
# 使い方: bash run_full.sh
# スケジュール実行も手動テストもこれ1本でOK

set -euo pipefail

PROJ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DATE=$(TZ=Asia/Tokyo date +%Y-%m-%d)

echo "=== [1/3] RSS フェッチ ==="
bash "$PROJ/scripts/run.sh" pre

echo "=== [2/3] AI 要約 (claude --print) ==="
claude --print --allowedTools "Read,Write" << EOF
以下を実行してください:
1. Read $PROJ/tmp/digest_input.md
2. Read $PROJ/prompts/daily_digest.md の指示に従いキュレーション・日本語要約
3. Write $PROJ/tmp/note_draft.md にノート本文を書く
4. Write $PROJ/tmp/slack_draft.txt にSlackメッセージを書く
完了したら '完了' とだけ出力してください。
EOF

echo "=== [3/3] 配信 (Obsidian + Slack) ==="
bash "$PROJ/scripts/run.sh" post "$DATE"

echo "=== owlclaw 完了 ($DATE) ==="

#!/usr/bin/env bash
# owlclaw: Slack通知スクリプト
# 使い方: bash slack_notify.sh [draft_path]
#   draft_path: 省略時は tmp/slack_draft.txt (後方互換)
# → draft_path の内容を Slack に送信する

set -euo pipefail

WEBHOOK_FILE="/Users/gon9a/workspace/ai_agent/owlclaw/secrets/slack_webhook.txt"
DRAFT="${1:-/Users/gon9a/workspace/ai_agent/owlclaw/tmp/slack_draft.txt}"

if [[ ! -f "$WEBHOOK_FILE" ]]; then
  echo "Error: $WEBHOOK_FILE が存在しません。secrets/slack_webhook.txt にWebhook URLを配置してください。" >&2
  exit 1
fi

if [[ ! -f "$DRAFT" ]]; then
  echo "Error: $DRAFT が存在しません。先に Write ツールで作成してください。" >&2
  exit 1
fi

WEBHOOK_URL=$(tr -d '[:space:]' < "$WEBHOOK_FILE")

# JSONエスケープ
PAYLOAD=$(python3 -c "
import sys, json
msg = open('$DRAFT').read()
print(json.dumps({'text': msg}))
")

HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" \
  -X POST \
  -H 'Content-Type: application/json' \
  -d "$PAYLOAD" \
  "$WEBHOOK_URL")

echo "Slack HTTP status: $HTTP_STATUS"

if [[ "$HTTP_STATUS" != "200" ]]; then
  echo "Error: Slack送信失敗 (status=$HTTP_STATUS)" >&2
  exit 1
fi

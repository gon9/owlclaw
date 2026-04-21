#!/usr/bin/env bash
# owlclaw: Slack通知スクリプト
# 使い方: bash slack_notify.sh "送りたいメッセージ本文"
# メッセージはSlack mrkdwn形式で渡すこと

set -euo pipefail

WEBHOOK_FILE="/Users/gon9a/workspace/ai_agent/owlclaw/secrets/slack_webhook.txt"
MESSAGE="${1:-}"

if [[ -z "$MESSAGE" ]]; then
  echo "Error: メッセージが空です" >&2
  exit 1
fi

WEBHOOK_URL=$(tr -d '[:space:]' < "$WEBHOOK_FILE")

# JSONエスケープ (バックスラッシュ → \\ 、ダブルクォート → \" 、改行 → \n)
ESCAPED=$(python3 -c "
import sys, json
msg = sys.stdin.read()
print(json.dumps(msg)[1:-1])  # strip surrounding quotes
" <<< "$MESSAGE")

HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" \
  -X POST \
  -H 'Content-Type: application/json' \
  -d "{\"text\": \"${ESCAPED}\"}" \
  "$WEBHOOK_URL")

echo "Slack HTTP status: $HTTP_STATUS"

if [[ "$HTTP_STATUS" != "200" ]]; then
  echo "Error: Slack送信失敗 (status=$HTTP_STATUS)" >&2
  exit 1
fi

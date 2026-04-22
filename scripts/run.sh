#!/usr/bin/env bash
# owlclaw メインパイプライン
#
# 使い方:
#   bash run.sh pre          — RSSフェッチ → tmp/digest_input.md
#   bash run.sh post DATE    — Obsidian書き出し + Slack通知 (DATE: YYYY-MM-DD)

set -euo pipefail

SCRIPTS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

case "${1:-}" in
  pre)
    echo "=== owlclaw: RSSフェッチ開始 ==="
    uv run python "$SCRIPTS_DIR/fetch_rss.py"
    echo "=== 完了: tmp/digest_input.md に保存しました ==="
    ;;
  post)
    DATE="${2:-}"
    if [[ -z "$DATE" ]]; then
      echo "Error: 日付を指定してください: run.sh post YYYY-MM-DD" >&2
      exit 1
    fi
    echo "=== owlclaw: Obsidian書き出し ==="
    bash "$SCRIPTS_DIR/write_obsidian.sh" "$DATE"
    echo "=== owlclaw: Slack通知 ==="
    bash "$SCRIPTS_DIR/slack_notify.sh"
    echo "=== 完了 ==="
    ;;
  *)
    echo "Usage: bash run.sh pre | post YYYY-MM-DD" >&2
    exit 1
    ;;
esac

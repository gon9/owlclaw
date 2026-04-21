#!/usr/bin/env bash
# owlclaw: Obsidianノート書き出しスクリプト
# 使い方: bash write_obsidian.sh "YYYY-MM-DD" "ノート本文（Markdown）"
# → obsidian_drive/docs_obsidian/20_news/owlclaw/daily/YYYY-MM-DD.md に上書き保存

set -euo pipefail

VAULT="/Users/gon9a/Library/CloudStorage/GoogleDrive-gon9a.chan@gmail.com/マイドライブ/workspace/obsidian_drive"
DATE="${1:-}"
CONTENT="${2:-}"

if [[ -z "$DATE" || -z "$CONTENT" ]]; then
  echo "Error: 引数が不足しています: write_obsidian.sh DATE CONTENT" >&2
  exit 1
fi

DEST_DIR="${VAULT}/docs_obsidian/20_news/owlclaw/daily"
DEST_FILE="${DEST_DIR}/${DATE}.md"

mkdir -p "$DEST_DIR"
printf '%s' "$CONTENT" > "$DEST_FILE"
echo "Obsidian note written: $DEST_FILE"

#!/usr/bin/env bash
# owlclaw: Obsidianノート書き出しスクリプト
# 使い方: bash write_obsidian.sh "YYYY-MM-DD"
# → tmp/note_draft.md の内容を Obsidian vault に保存する
# Claudeは Write ツールで tmp/note_draft.md に書いてからこのスクリプトを呼ぶこと

set -euo pipefail

VAULT="/Users/gon9a/Library/CloudStorage/GoogleDrive-gon9a.chan@gmail.com/マイドライブ/workspace/obsidian_drive"
DRAFT="/Users/gon9a/workspace/ai_agent/owlclaw/tmp/note_draft.md"
DATE="${1:-}"

if [[ -z "$DATE" ]]; then
  echo "Error: 日付を引数に渡してください: write_obsidian.sh YYYY-MM-DD" >&2
  exit 1
fi

if [[ ! "$DATE" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}$ ]]; then
  echo "Error: 日付はYYYY-MM-DD形式で渡してください: $DATE" >&2
  exit 1
fi

if [[ ! -f "$DRAFT" ]]; then
  echo "Error: $DRAFT が存在しません。先に Write ツールで作成してください。" >&2
  exit 1
fi

DEST_DIR="${VAULT}/docs_obsidian/20_news/owlclaw/daily"
DEST_FILE="${DEST_DIR}/${DATE}.md"

mkdir -p "$DEST_DIR"
cp "$DRAFT" "$DEST_FILE"
echo "Obsidian note written: $DEST_FILE"

#!/usr/bin/env bash
# owlclaw: Obsidianノート書き出しスクリプト
# 使い方: bash write_obsidian.sh "YYYY-MM-DD" [draft_path]
#   draft_path: 省略時は tmp/note_draft.md (後方互換)
# → draft_path の内容を Obsidian vault に保存する

set -euo pipefail

VAULT="/Users/gon9a/Library/CloudStorage/GoogleDrive-gon9a.chan@gmail.com/マイドライブ/workspace/obsidian_drive"
DATE="${1:-}"
DRAFT="${2:-/Users/gon9a/workspace/ai_agent/owlclaw/tmp/note_draft.md}"

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

if [[ -f "$DEST_FILE" ]]; then
  BACKUP="${DEST_FILE%.md}.bak.md"
  echo "Warning: $DEST_FILE が既に存在します。バックアップ → $BACKUP" >&2
  cp "$DEST_FILE" "$BACKUP"
fi

cp "$DRAFT" "$DEST_FILE"
echo "Obsidian note written: $DEST_FILE"

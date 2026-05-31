#!/usr/bin/env bash
# owlclaw: Obsidianノート書き出しスクリプト
# 使い方: bash write_obsidian.sh "YYYY-MM-DD" [draft_path] [relative_dest]
#   draft_path: 省略時は tmp/note_draft.md (後方互換)
#   relative_dest: 省略時は owlclaw/daily/YYYY-MM-DD.md (後方互換)
# → draft_path の内容を Obsidian vault に保存する

set -euo pipefail

PROJ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [[ -z "${OBSIDIAN_VAULT:-}" ]]; then
  echo "Error: 環境変数 OBSIDIAN_VAULT が未設定です。.env.example を参照して設定してください。" >&2
  exit 1
fi
VAULT="$OBSIDIAN_VAULT"
DATE="${1:-}"
DRAFT="${2:-$PROJ/tmp/note_draft.md}"
RELATIVE_DEST="${3:-owlclaw/daily/${DATE}.md}"

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

if [[ "$RELATIVE_DEST" == /* || "$RELATIVE_DEST" == ".." || "$RELATIVE_DEST" == ../* \
  || "$RELATIVE_DEST" == */../* || "$RELATIVE_DEST" == */.. ]]; then
  echo "Error: relative_dest はVault内の相対パスで指定してください: $RELATIVE_DEST" >&2
  exit 1
fi

DEST_ROOT="${VAULT}/docs_obsidian/20_news"
DEST_FILE="${DEST_ROOT}/${RELATIVE_DEST}"
DEST_DIR="$(dirname "$DEST_FILE")"

mkdir -p "$DEST_DIR"

if [[ -f "$DEST_FILE" ]]; then
  BACKUP="${DEST_FILE%.md}.bak.md"
  echo "Warning: $DEST_FILE が既に存在します。バックアップ → $BACKUP" >&2
  cp "$DEST_FILE" "$BACKUP"
fi

cp "$DRAFT" "$DEST_FILE"
echo "Obsidian note written: $DEST_FILE"

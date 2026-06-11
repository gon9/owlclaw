#!/usr/bin/env bash
# Install or update Claude Code CLI through npm.
#
# Usage:
#   bash scripts/update_claude.sh

set -euo pipefail

export PATH="/opt/homebrew/bin:/usr/local/bin:${HOME}/.local/bin:${PATH}"
export NVM_DIR="${NVM_DIR:-${HOME}/.nvm}"
if [[ -s "${NVM_DIR}/nvm.sh" ]]; then
  # shellcheck disable=SC1090
  . "${NVM_DIR}/nvm.sh"
fi

log() { printf '[claude-update] %s\n' "$*"; }

if ! command -v npm >/dev/null 2>&1; then
  echo "npm not found. Install Node.js or nvm before updating Claude Code CLI." >&2
  exit 1
fi

before="$(claude --version 2>/dev/null || true)"
if [[ -n "$before" ]]; then
  log "Current: ${before}"
else
  log "Claude Code CLI is not installed; installing latest."
fi

npm install -g @anthropic-ai/claude-code@latest --no-audit --no-fund

after="$(claude --version 2>/dev/null || true)"
if [[ -z "$after" ]]; then
  echo "claude command is still not available after npm install" >&2
  exit 1
fi

log "Installed: ${after}"

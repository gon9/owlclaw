#!/usr/bin/env bash
# Register launchd jobs that keep Claude Code CLI and Codex CLI current.

set -euo pipefail

PROJ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOME_DIR="${HOME}"
AGENTS_DIR="${HOME_DIR}/Library/LaunchAgents"

log() { printf '[cli-updaters] %s\n' "$*"; }
warn() { printf '[cli-updaters] WARNING: %s\n' "$*" >&2; }

mkdir -p "$AGENTS_DIR" "$PROJ/tmp"

_write_update_plist() {
  local label="$1" script_name="$2" minute="$3"
  local plist="${AGENTS_DIR}/${label}.plist"
  local log_name="${label#com.gon9a.}"

  cat > "$plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>${label}</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/zsh</string>
        <string>-lc</string>
        <string>source "\$HOME/.local/bin/env" 2>/dev/null || true; export PATH="/opt/homebrew/bin:/usr/local/bin:\$HOME/.local/bin:\$PATH"; cd "${PROJ}" &amp;&amp; bash scripts/${script_name}</string>
    </array>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>3</integer>
        <key>Minute</key>
        <integer>${minute}</integer>
    </dict>
    <key>StandardOutPath</key>
    <string>${PROJ}/tmp/launchd-${log_name}.log</string>
    <key>StandardErrorPath</key>
    <string>${PROJ}/tmp/launchd-${log_name}-err.log</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>HOME</key>
        <string>${HOME_DIR}</string>
        <key>USER</key>
        <string>${USER}</string>
    </dict>
</dict>
</plist>
EOF

  if [[ "$(id -u)" == "0" ]]; then
    warn "Skipping launchctl load for ${label}; run this script without sudo."
    return
  fi

  launchctl unload "$plist" 2>/dev/null || true
  launchctl load -w "$plist"
  log "registered ${label} (03:${minute} daily)"
}

_write_update_plist "com.gon9a.claude-update" "update_claude.sh" "10"
_write_update_plist "com.gon9a.codex-update" "update_codex.sh" "20"

log "done"

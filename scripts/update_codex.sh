#!/usr/bin/env bash
# Install or update the Codex CLI on macOS.
#
# Usage:
#   bash scripts/update_codex.sh
#   CODEX_VERSION=0.135.0 bash scripts/update_codex.sh
#   FORCE_CODEX_UPDATE=1 bash scripts/update_codex.sh

set -euo pipefail

ARCH="$(uname -m)"
HOME_DIR="${HOME}"
LOCAL_BIN="${LOCAL_BIN:-${HOME_DIR}/.local/bin}"
CODEX_BIN="${CODEX_BIN:-${LOCAL_BIN}/codex}"
CODEX_REPO="${CODEX_REPO:-openai/codex}"
CODEX_VERSION="${CODEX_VERSION:-latest}"
FORCE_CODEX_UPDATE="${FORCE_CODEX_UPDATE:-0}"

case "$ARCH" in
  x86_64) CODEX_TARGET="x86_64-apple-darwin" ;;
  arm64) CODEX_TARGET="aarch64-apple-darwin" ;;
  *) echo "Unsupported arch: $ARCH" >&2; exit 1 ;;
esac

log() { printf '[codex-update] %s\n' "$*"; }

mkdir -p "$LOCAL_BIN"
tmp_dir="$(mktemp -d)"
cleanup() {
  rm -rf "$tmp_dir"
}
trap cleanup EXIT

if [[ "$CODEX_VERSION" == "latest" ]]; then
  release_url="https://api.github.com/repos/${CODEX_REPO}/releases/latest"
else
  tag="$CODEX_VERSION"
  case "$tag" in
    rust-v*|v*) ;;
    *) tag="rust-v${tag}" ;;
  esac
  release_url="https://api.github.com/repos/${CODEX_REPO}/releases/tags/${tag}"
fi

release_json="${tmp_dir}/release.json"
log "Checking ${release_url}"
curl -fsSL "$release_url" -o "$release_json"

release_info="$(
  python3 - "$CODEX_TARGET" "$release_json" <<'PY'
import json
import sys

target = sys.argv[1]
path = sys.argv[2]
data = json.load(open(path, encoding="utf-8"))
tag = data["tag_name"]
suffix = f"codex-{target}.tar.gz"

for asset in data.get("assets", []):
    name = asset.get("name", "")
    url = asset.get("browser_download_url", "")
    if name == suffix or name.endswith(suffix):
        print(tag)
        print(url)
        break
else:
    names = ", ".join(asset.get("name", "") for asset in data.get("assets", []))
    raise SystemExit(f"asset not found for {target}; available: {names}")
PY
)"

codex_tag="$(printf '%s\n' "$release_info" | sed -n '1p')"
codex_url="$(printf '%s\n' "$release_info" | sed -n '2p')"
desired_version="${codex_tag#rust-v}"
desired_version="${desired_version#v}"

if [[ -x "$CODEX_BIN" && "$FORCE_CODEX_UPDATE" != "1" ]]; then
  current_version="$("$CODEX_BIN" --version 2>/dev/null || true)"
  if [[ "$current_version" == *"$desired_version"* ]]; then
    log "Already up to date: ${current_version}"
    exit 0
  fi
  log "Current: ${current_version:-unknown}; target: ${codex_tag}"
else
  log "Installing target: ${codex_tag}"
fi

archive="${tmp_dir}/codex.tar.gz"
extract_dir="${tmp_dir}/extract"
mkdir -p "$extract_dir"

log "Downloading ${codex_url}"
curl -fsSL "$codex_url" -o "$archive"
tar -xzf "$archive" -C "$extract_dir"

bin="$(
  find "$extract_dir" -type f -name 'codex-*-apple-darwin' -print | head -1
)"
if [[ -z "$bin" ]]; then
  echo "codex binary not found in archive" >&2
  exit 1
fi

install_tmp="${tmp_dir}/codex"
cp "$bin" "$install_tmp"
chmod +x "$install_tmp"
mv "$install_tmp" "$CODEX_BIN"
xattr -d com.apple.quarantine "$CODEX_BIN" 2>/dev/null || true

log "Installed: $("$CODEX_BIN" --version 2>&1 | head -1)"

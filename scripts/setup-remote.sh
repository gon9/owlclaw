#!/usr/bin/env bash
#
# setup-remote.sh — owlclaw リモートマシンの idempotent セットアップ
#
# 何度実行しても同じ状態に収束する。既にあれば skip、なければ install。
# Docker を使わずに macOS (Intel/Apple Silicon) の素の環境を立ち上げる用途。
#
# 前提:
#   - owlclaw リポジトリが ~/workspace/ai-agent/owlclaw に clone 済み
#   - uv が ~/.local/bin/uv に install 済み (https://docs.astral.sh/uv/)
#   - node + npm が PATH 上 (Homebrew or NVM 推奨)
#   - python3 (system 同梱) が利用可能
#
# 使い方:
#   bash scripts/setup-remote.sh
#
# 実行後の手動ステップ:
#   1. codex login  # ChatGPT OAuth or API key
#   2. bash scripts/run_task.sh video-digest  # 動作確認

set -euo pipefail

# === Pinned versions ===
VOICEVOX_VERSION="${VOICEVOX_VERSION:-0.19.1}"   # numpy 2.x 非互換のため macOS 12 では 0.19.1 が安定
CODEX_VERSION="${CODEX_VERSION:-0.135.0}"

# === Paths ===
ARCH="$(uname -m)"
HOME_DIR="${HOME}"
LOCAL_BIN="${HOME_DIR}/.local/bin"
VOICEVOX_DIR="${HOME_DIR}/voicevox"
OWLCLAW_DIR="${OWLCLAW_DIR:-${HOME_DIR}/workspace/ai-agent/owlclaw}"

case "$ARCH" in
  x86_64)  VV_PLATFORM="macos-x64";   CODEX_TARGET="x86_64-apple-darwin" ;;
  arm64)   VV_PLATFORM="macos-arm64"; CODEX_TARGET="aarch64-apple-darwin" ;;
  *) echo "Unsupported arch: $ARCH" >&2; exit 1 ;;
esac

mkdir -p "$LOCAL_BIN"

# === Logging ===
log()  { printf '\033[1;34m[%s]\033[0m %s\n' "$(date +%H:%M:%S)" "$*"; }
ok()   { printf '\033[1;32m  ✓ %s\033[0m\n' "$*"; }
skip() { printf '\033[1;33m  - skip:\033[0m %s\n' "$*"; }
warn() { printf '\033[1;31m  ! %s\033[0m\n' "$*"; }

log "owlclaw remote setup (arch=$ARCH, voicevox=$VOICEVOX_VERSION, codex=$CODEX_VERSION)"

# === 0. py7zr (VOICEVOX 7z 展開用) ===
log "0/5 py7zr (Python lib for .7z extraction)"
if python3 -c 'import py7zr' 2>/dev/null; then
  skip "py7zr already installed"
else
  python3 -m pip install --user --quiet py7zr
  ok "py7zr installed"
fi

# === 1. VOICEVOX Engine (~1.2GB ダウンロード、初回のみ) ===
log "1/5 VOICEVOX Engine ${VOICEVOX_VERSION} (${VV_PLATFORM})"
if [[ -x "${VOICEVOX_DIR}/${VV_PLATFORM}/run" ]]; then
  skip "VOICEVOX Engine binary exists at ${VOICEVOX_DIR}/${VV_PLATFORM}/run"
else
  mkdir -p "$VOICEVOX_DIR"
  cd "$VOICEVOX_DIR"
  ARCHIVE="voicevox_engine-${VV_PLATFORM}-${VOICEVOX_VERSION}.7z.001"
  URL="https://github.com/VOICEVOX/voicevox_engine/releases/download/${VOICEVOX_VERSION}/${ARCHIVE}"
  log "  Downloading ${ARCHIVE} (~1.2GB)..."
  curl -fLo voicevox.7z.001 "$URL"
  log "  Extracting (py7zr)..."
  python3 -c "
import py7zr, time
start = time.time()
with py7zr.SevenZipFile('voicevox.7z.001', 'r') as z:
    z.extractall(path='.')
print(f'  extracted in {time.time()-start:.0f}s')
"
  rm -f voicevox.7z.001
  xattr -dr com.apple.quarantine . 2>/dev/null || true
  chmod +x "${VV_PLATFORM}/run"
  ok "VOICEVOX Engine installed"
fi

# === 2. VOICEVOX launchd (常駐化) ===
log "2/5 VOICEVOX launchd job"
PLIST="${HOME_DIR}/Library/LaunchAgents/com.voicevox.engine.plist"
VV_RUN="${VOICEVOX_DIR}/${VV_PLATFORM}/run"

if launchctl list 2>/dev/null | grep -q com.voicevox.engine; then
  skip "launchd com.voicevox.engine already loaded"
else
  mkdir -p "$(dirname "$PLIST")"
  cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.voicevox.engine</string>
    <key>ProgramArguments</key>
    <array>
        <string>${VV_RUN}</string>
        <string>--host</string>
        <string>127.0.0.1</string>
        <string>--port</string>
        <string>50021</string>
    </array>
    <key>WorkingDirectory</key>
    <string>${VOICEVOX_DIR}/${VV_PLATFORM}</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>${VOICEVOX_DIR}/engine.out.log</string>
    <key>StandardErrorPath</key>
    <string>${VOICEVOX_DIR}/engine.err.log</string>
</dict>
</plist>
EOF
  launchctl load -w "$PLIST"
  ok "launchd com.voicevox.engine registered"
fi

# 起動待機 (最大 90 秒、numpy/onnxruntime のロードに時間がかかる)
log "  Waiting for VOICEVOX HTTP to become ready..."
for i in $(seq 1 90); do
  if curl -sf -m 1 http://127.0.0.1:50021/version >/dev/null 2>&1; then
    VV_VER=$(curl -s http://127.0.0.1:50021/version)
    ok "VOICEVOX ready: ${VV_VER} (after ${i}s)"
    break
  fi
  sleep 1
done

# === 3. Puppeteer (repo-local node_modules) ===
log "3/5 Puppeteer (Chromium) — for HTML slide rendering"
if [[ ! -d "$OWLCLAW_DIR" ]]; then
  warn "$OWLCLAW_DIR not found. clone owlclaw first then re-run."
  exit 1
fi
cd "$OWLCLAW_DIR"

if [[ -d node_modules/puppeteer ]]; then
  skip "puppeteer already installed at ${OWLCLAW_DIR}/node_modules/puppeteer"
else
  if [[ ! -f package.json ]]; then
    warn "package.json not found in owlclaw. git pull で最新化してください"
    exit 1
  fi
  # SSH 非対話 shell では PATH に node が無い場合がある → 代表的な場所を補完
  export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
  if ! command -v npm >/dev/null; then
    warn "npm が PATH にない。Homebrew or NVM で node を install してください"
    exit 1
  fi
  npm install --no-audit --no-fund 2>&1 | tail -5
  ok "puppeteer installed (repo-local)"
fi

# === 4. codex CLI (auth は手動) ===
log "4/5 codex CLI ${CODEX_VERSION}"
NEED_INSTALL=true
if [[ -x "${LOCAL_BIN}/codex" ]]; then
  CUR_VER=$("${LOCAL_BIN}/codex" --version 2>/dev/null || true)
  if [[ "$CUR_VER" == *"$CODEX_VERSION"* ]]; then
    skip "codex ${CODEX_VERSION} already installed"
    NEED_INSTALL=false
  fi
fi

if $NEED_INSTALL; then
  CODEX_URL="https://github.com/openai/codex/releases/download/rust-v${CODEX_VERSION}/codex-${CODEX_TARGET}.tar.gz"
  log "  Downloading codex-${CODEX_TARGET} (~86MB)..."
  TMP=$(mktemp -d)
  trap "rm -rf $TMP" EXIT
  curl -fLo "$TMP/codex.tar.gz" "$CODEX_URL"
  tar -xzf "$TMP/codex.tar.gz" -C "$TMP"
  BIN=$(find "$TMP" -name 'codex-*-apple-darwin' -type f -perm +111 | head -1)
  if [[ -z "$BIN" ]]; then
    warn "codex binary not found in archive"; exit 1
  fi
  cp "$BIN" "${LOCAL_BIN}/codex"
  chmod +x "${LOCAL_BIN}/codex"
  xattr -d com.apple.quarantine "${LOCAL_BIN}/codex" 2>/dev/null || true
  ok "codex installed: $(${LOCAL_BIN}/codex --version 2>&1 | head -1)"
fi

# 認証チェック (auth.json の有無のみ。トークン有効性はチェックしない)
if [[ -f "${HOME_DIR}/.codex/auth.json" ]] && grep -q -E 'OPENAI_API_KEY|tokens' "${HOME_DIR}/.codex/auth.json" 2>/dev/null; then
  ok "codex auth.json exists (login 済み想定)"
else
  warn "codex login が必要: \`${LOCAL_BIN}/codex login\` を手動実行してください"
fi

# === 5. uv sync (Python deps) ===
log "5/5 uv sync (owlclaw Python deps)"
if [[ ! -x "${LOCAL_BIN}/uv" ]]; then
  warn "uv が ${LOCAL_BIN}/uv に無い。 https://docs.astral.sh/uv/ から install してください"
else
  cd "$OWLCLAW_DIR"
  "${LOCAL_BIN}/uv" sync 2>&1 | tail -3
  ok "uv sync done"
fi

# === Summary ===
echo
log "✅ Setup complete."
echo
echo "Next steps:"
echo "  1. ${LOCAL_BIN}/codex login        # ChatGPT OAuth で認証 (初回のみ)"
echo "  2. bash ${OWLCLAW_DIR}/scripts/run_task.sh video-digest"
echo "                                       # video pipeline の動作確認"
echo
echo "Useful commands:"
echo "  - launchctl list | grep voicevox      # VOICEVOX 常駐状態"
echo "  - tail -f ${VOICEVOX_DIR}/engine.err.log"
echo "  - curl http://127.0.0.1:50021/version # VOICEVOX 動作確認"

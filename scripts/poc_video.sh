#!/usr/bin/env bash
# 動画生成 PoC: 画像1枚 + ナレーション1本 -> mp4
#
# 前提:
#   - ffmpeg (brew install ffmpeg)
#   - codex CLI (brew install codex, ChatGPT サインイン済)
#   - VOICEVOX 起動中 (http://127.0.0.1:50021)
#
# 使い方:
#   bash scripts/poc_video.sh
#
# 出力:
#   tmp/poc/seg1.png  画像
#   tmp/poc/seg1.wav  音声
#   tmp/poc/seg1.mp4  動画
set -euo pipefail

# brew bin を PATH に確保（ログインシェル以外でも動くように）
export PATH="/opt/homebrew/bin:${PATH}"

PROJ_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
POC_DIR="${PROJ_ROOT}/tmp/poc"
VOICEVOX_URL="${VOICEVOX_URL:-http://127.0.0.1:50021}"
VOICEVOX_SPEAKER="${VOICEVOX_SPEAKER:-13}"  # 13 = 青山龍星 (ニュース調)

mkdir -p "${POC_DIR}"

###############################################################################
# 1. ヘルスチェック
###############################################################################
echo "==> [1/4] health check"

command -v ffmpeg >/dev/null || { echo "ERROR: ffmpeg not found in PATH"; exit 1; }
command -v codex  >/dev/null || { echo "ERROR: codex CLI not found in PATH"; exit 1; }

if ! curl -sf "${VOICEVOX_URL}/version" >/dev/null; then
  echo "ERROR: VOICEVOX not running at ${VOICEVOX_URL}"
  echo "  起動方法: VOICEVOX アプリを開いてください"
  exit 1
fi

echo "  ffmpeg : $(ffmpeg -version | head -1)"
echo "  codex  : $(codex --version)"
echo "  voicevox: $(curl -s "${VOICEVOX_URL}/version")"

###############################################################################
# 2. プロンプト準備（無ければデフォルト書き出し）
###############################################################################
echo "==> [2/4] prepare prompts"

PROMPT_IMAGE_FILE="${POC_DIR}/prompt_image.txt"
PROMPT_VOICE_FILE="${POC_DIR}/prompt_voice.txt"

if [[ ! -f "${PROMPT_IMAGE_FILE}" ]]; then
  cat > "${PROMPT_IMAGE_FILE}" <<'EOF'
A modern AI newsroom scene with a holographic display showing the OWLCLAW NEWS logo, dawn lighting, blue and white color palette, cinematic news photography, 16:9 widescreen aspect ratio, professional broadcast aesthetic, no text on screen
EOF
fi

if [[ ! -f "${PROMPT_VOICE_FILE}" ]]; then
  cat > "${PROMPT_VOICE_FILE}" <<'EOF'
おはようございます。OWLCLAW NEWSです。本日のAIニュースをお届けします。
EOF
fi

echo "  image prompt: ${PROMPT_IMAGE_FILE}"
echo "  voice text  : ${PROMPT_VOICE_FILE}"

###############################################################################
# 3. 画像生成 (Codex CLI $imagegen)
###############################################################################
IMG_PATH="${POC_DIR}/seg1.png"

if [[ -f "${IMG_PATH}" && "${REGEN_IMAGE:-0}" != "1" ]]; then
  echo "==> [3a/4] image already exists: ${IMG_PATH} (REGEN_IMAGE=1 で再生成)"
else
  echo "==> [3a/4] generate image via Codex CLI"
  IMG_PROMPT="$(cat "${PROMPT_IMAGE_FILE}")"

  # codex exec に画像生成を依頼。$imagegen スキルを明示的に呼び出し、保存先を指定
  codex exec --skip-git-repo-check --sandbox workspace-write \
    "\$imagegen ${IMG_PROMPT}

Save the generated image to: ${IMG_PATH}
Use 1280x720 resolution. Do not write any other files." \
    2>&1 | tee "${POC_DIR}/codex_image.log"

  if [[ ! -f "${IMG_PATH}" ]]; then
    echo "ERROR: image not generated at ${IMG_PATH}"
    echo "  codex のログを確認: ${POC_DIR}/codex_image.log"
    exit 1
  fi
  echo "  generated: ${IMG_PATH} ($(du -h "${IMG_PATH}" | cut -f1))"
fi

###############################################################################
# 3b. 音声生成 (VOICEVOX)
###############################################################################
WAV_PATH="${POC_DIR}/seg1.wav"
QUERY_PATH="${POC_DIR}/seg1_query.json"
NARRATION="$(cat "${PROMPT_VOICE_FILE}")"

echo "==> [3b/4] generate audio via VOICEVOX (speaker=${VOICEVOX_SPEAKER})"

# audio_query: テキストから音声合成パラメータを生成
curl -sf -X POST \
  "${VOICEVOX_URL}/audio_query?speaker=${VOICEVOX_SPEAKER}" \
  --get --data-urlencode "text=${NARRATION}" \
  -o "${QUERY_PATH}"

# synthesis: パラメータから wav 生成
curl -sf -X POST \
  "${VOICEVOX_URL}/synthesis?speaker=${VOICEVOX_SPEAKER}" \
  -H "Content-Type: application/json" \
  --data-binary "@${QUERY_PATH}" \
  -o "${WAV_PATH}"

DUR=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "${WAV_PATH}")
echo "  generated: ${WAV_PATH} (duration=${DUR}s)"

###############################################################################
# 4. 動画合成 (ffmpeg)
###############################################################################
MP4_PATH="${POC_DIR}/seg1.mp4"

echo "==> [4/4] compose video via ffmpeg"

ffmpeg -y -loglevel warning \
  -loop 1 -i "${IMG_PATH}" \
  -i "${WAV_PATH}" \
  -c:v libx264 -tune stillimage -preset medium \
  -c:a aac -b:a 192k \
  -shortest \
  -pix_fmt yuv420p \
  -vf "scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2" \
  "${MP4_PATH}"

echo
echo "✅ done: ${MP4_PATH}"
echo "   再生: open '${MP4_PATH}'"

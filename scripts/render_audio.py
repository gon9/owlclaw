#!/usr/bin/env python3
"""VOICEVOX HTTP API でナレーション WAV を生成する。

使い方:
    uv run python scripts/render_audio.py <slides.json> <output_dir>

VOICEVOX が起動している必要がある (既定 http://127.0.0.1:50021)。
環境変数 VOICEVOX_URL で上書き可能。
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import httpx

PROJ = Path(__file__).parent.parent
sys.path.insert(0, str(PROJ))

from tools.slide_schema import SlideDeck, load_deck  # noqa: E402

VOICEVOX_URL = os.environ.get("VOICEVOX_URL", "http://127.0.0.1:50021")
TIMEOUT = httpx.Timeout(60.0)


def synthesize(text: str, speaker: int, out_wav: Path) -> None:
    """VOICEVOX で text を音声合成し out_wav に保存する。"""
    with httpx.Client(timeout=TIMEOUT) as client:
        # audio_query: テキストから合成パラメータを生成
        q = client.post(
            f"{VOICEVOX_URL}/audio_query",
            params={"text": text, "speaker": speaker},
        )
        q.raise_for_status()
        # synthesis: パラメータから wav を生成
        s = client.post(
            f"{VOICEVOX_URL}/synthesis",
            params={"speaker": speaker},
            json=q.json(),
        )
        s.raise_for_status()
        out_wav.write_bytes(s.content)


def render_audio(deck: SlideDeck, out_dir: Path) -> list[Path]:
    """SlideDeck の各スライドナレーションを WAV にレンダリングする。"""
    out_dir.mkdir(parents=True, exist_ok=True)
    # ヘルスチェック
    try:
        with httpx.Client(timeout=httpx.Timeout(5.0)) as client:
            client.get(f"{VOICEVOX_URL}/version").raise_for_status()
    except Exception as e:
        raise RuntimeError(
            f"VOICEVOX が応答しません ({VOICEVOX_URL})。アプリを起動してください: {e}"
        ) from e

    wavs: list[Path] = []
    for slide in deck.slides:
        wav_path = out_dir / f"{slide.id}.wav"
        print(f"  [{slide.id}] VOICEVOX 音声合成中 (speaker={deck.speaker_id})", file=sys.stderr)
        synthesize(slide.narration, deck.speaker_id, wav_path)
        wavs.append(wav_path)
    return wavs


def main() -> None:
    """CLI エントリポイント。"""
    parser = argparse.ArgumentParser(description="VOICEVOX でナレーション WAV を生成")
    parser.add_argument("slides_json", help="slides.json のパス")
    parser.add_argument("out_dir", help="出力ディレクトリ")
    args = parser.parse_args()

    deck = load_deck(args.slides_json)
    out_dir = Path(args.out_dir)
    wavs = render_audio(deck, out_dir)

    print(f"✓ {len(wavs)} 音声ファイルを生成完了: {out_dir}", file=sys.stderr)


if __name__ == "__main__":
    main()

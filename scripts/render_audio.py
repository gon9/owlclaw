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
import re
import sys
from pathlib import Path

import httpx
import yaml

PROJ = Path(__file__).parent.parent
sys.path.insert(0, str(PROJ))

from tools.slide_schema import SlideDeck, load_deck  # noqa: E402

VOICEVOX_URL = os.environ.get("VOICEVOX_URL", "http://127.0.0.1:50021")
TIMEOUT = httpx.Timeout(60.0)
PRONUNCIATION_CONFIG = PROJ / "config" / "pronunciations.yaml"

LATIN_WORD_PATTERN = re.compile(r"(?<![A-Za-z0-9_])([A-Z][A-Za-z]{3,})(?![A-Za-z0-9_])")
ACRONYM_PATTERN = re.compile(r"^[A-Z]{2,}$")


def load_pronunciation_replacements(path: Path = PRONUNCIATION_CONFIG) -> dict[str, str]:
    """読み辞書を読み込み、小文字キーの置換マップとして返す。"""
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    terms = data.get("terms", {})
    if not isinstance(terms, dict):
        raise ValueError(f"{path}: terms must be a mapping")
    return {str(surface).lower(): str(reading) for surface, reading in terms.items()}


def build_pronunciation_pattern(replacements: dict[str, str]) -> re.Pattern[str] | None:
    """読み辞書から英字語境界付きの置換パターンを作る。"""
    if not replacements:
        return None
    alternatives = sorted(replacements, key=len, reverse=True)
    return re.compile(
        rf"(?<![A-Za-z0-9_])({'|'.join(map(re.escape, alternatives))})(?![A-Za-z0-9_])",
        flags=re.IGNORECASE,
    )


def find_unregistered_latin_terms(text: str, replacements: dict[str, str]) -> list[str]:
    """読み辞書にない英字固有名詞候補を抽出する。"""
    terms: set[str] = set()
    for match in LATIN_WORD_PATTERN.finditer(text):
        term = match.group(1)
        if term.lower() in replacements or ACRONYM_PATTERN.fullmatch(term):
            continue
        terms.add(term)
    return sorted(terms, key=str.lower)


def normalize_pronunciation(text: str, replacements: dict[str, str] | None = None) -> str:
    """VOICEVOX が英字を一文字ずつ読まないように既知の固有名詞を読みへ置換する。"""
    if replacements is None:
        replacements = load_pronunciation_replacements()
    pattern = build_pronunciation_pattern(replacements)
    if pattern is None:
        return text
    return pattern.sub(lambda match: replacements[match.group(0).lower()], text)


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
    replacements = load_pronunciation_replacements()
    for slide in deck.slides:
        wav_path = out_dir / f"{slide.id}.wav"
        print(f"  [{slide.id}] VOICEVOX 音声合成中 (speaker={deck.speaker_id})", file=sys.stderr)
        normalized = normalize_pronunciation(slide.narration, replacements)
        unregistered_terms = find_unregistered_latin_terms(normalized, replacements)
        if unregistered_terms:
            print(
                "  "
                f"[{slide.id}] 読み辞書未登録の英字語候補: {', '.join(unregistered_terms)} "
                f"(config/pronunciations.yaml に追加してください)",
                file=sys.stderr,
            )
        synthesize(normalized, deck.speaker_id, wav_path)
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

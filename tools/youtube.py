"""
owlclaw tools: YouTube字幕取得ツール。

youtube-transcript-api を使い、YouTube動画から字幕テキストを取得する。
字幕なし動画・言語不一致などの異常系を適切にハンドリングする。

使い方:
  python -m tools.youtube https://www.youtube.com/watch?v=<id>
  python -m tools.youtube <url> --lang en ja
  python -m tools.youtube <url> --json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from typing import TypedDict
from urllib.parse import parse_qs, urlparse

from youtube_transcript_api import (
    NoTranscriptFound,
    TranscriptsDisabled,
    VideoUnavailable,
    YouTubeTranscriptApi,
)
from youtube_transcript_api._transcripts import FetchedTranscript


class TranscriptSegment(TypedDict):
    """字幕の1セグメント。"""

    text: str
    start: float
    duration: float


class TranscriptResult(TypedDict):
    """字幕取得結果。"""

    video_id: str
    url: str
    text: str
    segments: list[TranscriptSegment]
    language: str
    char_count: int


class TranscriptError(Exception):
    """字幕取得失敗時の例外。"""


def extract_video_id(url: str) -> str:
    """YouTube URLからvideo_idを抽出する。

    Parameters
    ----------
    url : str
        YouTube URL (通常形式 or 短縮形式 youtu.be)

    Returns
    -------
    str
        video_id

    Raises
    ------
    TranscriptError
        video_idを抽出できない場合
    """
    parsed = urlparse(url)
    if parsed.hostname in ("youtu.be",):
        vid = parsed.path.lstrip("/").split("?")[0]
        if vid:
            return vid
    if parsed.hostname in ("www.youtube.com", "youtube.com", "m.youtube.com"):
        qs = parse_qs(parsed.query)
        ids = qs.get("v", [])
        if ids:
            return ids[0]
        match = re.search(r"/(?:embed|shorts|v)/([A-Za-z0-9_-]{11})", parsed.path)
        if match:
            return match.group(1)
    match = re.fullmatch(r"[A-Za-z0-9_-]{11}", url.strip())
    if match:
        return url.strip()
    raise TranscriptError(f"video_id を抽出できません: {url}")


def fetch_transcript(
    video_id: str,
    languages: list[str] | None = None,
) -> TranscriptResult:
    """指定video_idの字幕を取得する。

    youtube-transcript-api v1.x の api.fetch() を使用する。

    Parameters
    ----------
    video_id : str
        YouTube video ID
    languages : list[str] | None
        字幕言語の優先順位。Noneの場合は ["en", "ja"] を使用。

    Returns
    -------
    TranscriptResult
        字幕取得結果

    Raises
    ------
    TranscriptError
        字幕取得に失敗した場合
    """
    langs = languages or ["en", "ja"]
    api = YouTubeTranscriptApi()
    try:
        fetched: FetchedTranscript = api.fetch(video_id, languages=langs)
        segments: list[TranscriptSegment] = [
            {"text": snip.text, "start": snip.start, "duration": snip.duration}
            for snip in fetched
        ]
        full_text = " ".join(seg["text"] for seg in segments)
        return TranscriptResult(
            video_id=video_id,
            url=f"https://www.youtube.com/watch?v={video_id}",
            text=full_text,
            segments=segments,
            language=fetched.language_code,
            char_count=len(full_text),
        )
    except TranscriptsDisabled as e:
        raise TranscriptError(f"字幕が無効化されています: {video_id}") from e
    except VideoUnavailable as e:
        raise TranscriptError(f"動画が利用不可です: {video_id}") from e
    except NoTranscriptFound as e:
        raise TranscriptError(
            f"対応言語の字幕が見つかりません (試行言語: {langs}): {video_id}"
        ) from e
    except Exception as e:
        raise TranscriptError(f"字幕取得中に予期しないエラー: {e}") from e


def fetch_transcript_from_url(
    url: str,
    languages: list[str] | None = None,
) -> TranscriptResult:
    """YouTube URLから字幕を取得する。

    Parameters
    ----------
    url : str
        YouTube URL
    languages : list[str] | None
        字幕言語の優先順位

    Returns
    -------
    TranscriptResult
        字幕取得結果
    """
    video_id = extract_video_id(url)
    return fetch_transcript(video_id, languages=languages)


def main() -> None:
    """CLIエントリーポイント。"""
    parser = argparse.ArgumentParser(
        description="YouTube動画から字幕を取得する",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("url", help="YouTube URL または video_id")
    parser.add_argument(
        "--lang",
        nargs="+",
        default=["en", "ja"],
        metavar="LANG",
        help="字幕言語の優先順位 (デフォルト: en ja)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="output_json",
        help="セグメント含む完全なJSONを出力",
    )
    args = parser.parse_args()

    try:
        result = fetch_transcript_from_url(args.url, languages=args.lang)
    except TranscriptError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    if args.output_json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"[{result['language']}] {result['char_count']} chars | {result['url']}")
        print()
        print(result["text"])


if __name__ == "__main__":
    main()

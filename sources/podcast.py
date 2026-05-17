"""
owlclaw: Podcast/YouTube字幕ソースプラグイン。

tools/youtube.py（字幕取得）+ tools/summarize.py（要約）をラップして
BaseSource インターフェースに適合させる。

設定例 (tasks/*.yaml):
  sources:
    - type: podcast
      urls:
        - https://www.youtube.com/watch?v=VIDEO_ID
        - https://youtu.be/ANOTHER_ID
      languages: ["en", "ja"]
      context: "FDE+AI専門家視点で重要な技術的ポイントを日本語で要約してください。"
      max_char_per_video: 50000
"""

from __future__ import annotations

import sys
from datetime import datetime

from sources.base import BaseSource
from tools.summarize import SummarizeError, summarize
from tools.youtube import TranscriptError, fetch_transcript_from_url

DEFAULT_CONTEXT = (
    "あなたはFDE職+AI専門家として情報収集しています。"
    "このPodcast/YouTube動画から重要な技術的ポイントを日本語で箇条書きにまとめてください。"
)


class PodcastSource(BaseSource):
    """Podcast/YouTube字幕取得・要約ソースプラグイン。"""

    def fetch(
        self,
        config: dict,
        cutoff: datetime,
        last_seen_per_source: dict | None = None,
    ) -> tuple[str, dict]:
        """YouTube URLのリストから字幕を取得・要約してMarkdownを返す。

        Parameters
        ----------
        config : dict
            ソース設定。有効キー:
              - urls (list[str]): YouTube URL のリスト (必須)
              - languages (list[str]): 字幕言語優先順位 (デフォルト: ["en", "ja"])
              - context (str): 要約の文脈・視点
              - chunk_size (int): 要約チャンクサイズ (デフォルト: 8000)
        cutoff : datetime
            使用しない
        last_seen_per_source : dict | None
            使用しない

        Returns
        -------
        tuple[str, dict]
            (Markdownテキスト, {})
        """
        urls: list[str] = config.get("urls", [])
        languages: list[str] = config.get("languages", ["en", "ja"])
        context: str = config.get("context", DEFAULT_CONTEXT)
        chunk_size: int = int(config.get("chunk_size", 8000))

        if not urls:
            return "## Podcast/YouTube\n\n*(URLが設定されていません)*\n", {}

        print(f"  [Podcast] {len(urls)} 件処理開始", file=sys.stderr)
        lines = [f"## Podcast/YouTube ({len(urls)}件)\n"]
        success_count = 0

        for i, url in enumerate(urls, 1):
            print(f"  [Podcast] {i}/{len(urls)}: {url}", file=sys.stderr)
            try:
                transcript = fetch_transcript_from_url(url, languages=languages)
                print(
                    f"    字幕取得: {transcript['char_count']} 文字 "
                    f"[{transcript['language']}]",
                    file=sys.stderr,
                )
            except TranscriptError as e:
                print(f"    字幕取得エラー: {e}", file=sys.stderr)
                lines.append(f"### {i}. {url}")
                lines.append(f"- URL: {url}")
                lines.append(f"- Error: 字幕取得失敗 — {e}")
                lines.append("")
                continue

            try:
                summary_text = summarize(
                    transcript["text"],
                    context=context,
                    chunk_size=chunk_size,
                )
                success_count += 1
            except SummarizeError as e:
                print(f"    要約エラー: {e}", file=sys.stderr)
                lines.append(f"### {i}. {url}")
                lines.append(f"- URL: {url}")
                lines.append(f"- Language: {transcript['language']}")
                lines.append(f"- Error: 要約失敗 — {e}")
                lines.append("")
                continue

            lines.append(f"### {i}. {url}")
            lines.append(f"- URL: {url}")
            lines.append(f"- Language: {transcript['language']}")
            lines.append(f"- CharCount: {transcript['char_count']}")
            lines.append("")
            lines.append(summary_text)
            lines.append("")

        print(f"  [Podcast] {success_count}/{len(urls)} 件成功", file=sys.stderr)
        return "\n".join(lines), {}

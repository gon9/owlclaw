"""
owlclaw: Bluesky ソースプラグイン。

`tools/bluesky.py` をラップして BaseSource インターフェースに適合させる。
Starter Pack 起点で AI/ML コミュニティの handle 一覧を解決し、各 author feed を集約する。

設定例 (tasks/*.yaml):
  sources:
    - type: bluesky
      starter_packs: []         # 空なら DEFAULT_STARTER_PACKS を使用
      handles: []               # 個別ハンドルを追加（任意）
      limit: 50                 # handleあたりの最大件数
      days: 1                   # 直近N日
      min_engagement: 3         # like + repost*3 + reply*2 + quote*2
      require_paper_url: true   # arxiv/HF/OpenReview を含むポストのみ
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime, timedelta

from sources.base import BaseSource
from tools.bluesky import (
    BlueskyError,
    fetch_all_posts,
    resolve_handles,
)


class BlueskySource(BaseSource):
    """Bluesky ポスト取得ソースプラグイン。"""

    def fetch(
        self,
        config: dict,
        cutoff: datetime,
        last_seen_per_source: dict | None = None,
    ) -> tuple[str, dict]:
        """Starter Pack 起点で Bluesky ポストを取得してMarkdownを返す。

        Parameters
        ----------
        config : dict
            ソース設定。有効キー:
              - starter_packs (list[str]): 空ならデフォルト10個を使用
              - handles (list[str]): 追加で指定するハンドル
              - limit (int): handleあたりの取得件数 (デフォルト: 50)
              - days (int): 直近N日（デフォルト: 1）
              - min_engagement (int): エンゲージメントスコアの下限
              - require_paper_url (bool): 論文URLを含むポストのみ抽出
              - max_workers (int): 並列度（デフォルト: 5）
        cutoff : datetime
            グローバルカットオフ（days 未指定時に使用）
        last_seen_per_source : dict | None
            使用しない

        Returns
        -------
        tuple[str, dict]
            (Markdownテキスト, {})
        """
        starter_packs: list[str] = list(config.get("starter_packs", []) or [])
        extra_handles: list[str] = list(config.get("handles", []) or [])
        limit: int = int(config.get("limit", 50))
        days: int | None = config.get("days")
        min_engagement: int = int(config.get("min_engagement", 0))
        require_paper_url: bool = bool(config.get("require_paper_url", False))
        max_workers: int = int(config.get("max_workers", 5))

        since = (
            datetime.now(UTC) - timedelta(days=days)
            if days is not None
            else cutoff
        )

        # 1. handle 解決
        try:
            handles = resolve_handles(
                starter_packs=starter_packs if starter_packs else None,
            )
        except BlueskyError as e:
            print(f"  [Bluesky] handle 解決失敗: {e}", file=sys.stderr)
            handles = []

        # 追加 handle をマージ
        if extra_handles:
            seen = set(handles)
            for h in extra_handles:
                if h not in seen:
                    seen.add(h)
                    handles.append(h)

        if not handles:
            return "## Bluesky\n\n*(handle が解決できませんでした)*\n", {}

        # 2. 全 handle から並列取得
        print(f"  [Bluesky] {len(handles)} handles から取得中...", file=sys.stderr)
        posts = fetch_all_posts(
            handles,
            limit=limit,
            since=since,
            max_workers=max_workers,
        )
        print(f"  [Bluesky] {len(posts)} 件取得", file=sys.stderr)

        # 3. フィルタ
        if min_engagement > 0:
            before = len(posts)
            posts = [p for p in posts if p["engagement"] >= min_engagement]
            print(
                f"  [Bluesky] min_engagement={min_engagement}: {before} → {len(posts)} 件",
                file=sys.stderr,
            )

        if require_paper_url:
            before = len(posts)
            posts = [p for p in posts if p["paper_urls"]]
            print(
                f"  [Bluesky] require_paper_url: {before} → {len(posts)} 件",
                file=sys.stderr,
            )

        # エンゲージメント降順
        posts.sort(key=lambda p: p["engagement"], reverse=True)

        total = len(posts)
        label = f"Bluesky ({total}件)"
        lines = [f"## {label}\n"]

        if not posts:
            lines.append("*(該当ポストなし)*\n")
            return "\n".join(lines), {}

        for i, p in enumerate(posts, 1):
            text_short = p["text"][:120].replace("\n", " ").strip() or "(no text)"
            lines.append(f"### {i}. {text_short}")
            lines.append(f"- URL: {p['url']}")
            lines.append(f"- Author: @{p['author']} ({p['author_display']})")
            lines.append(f"- Date: {p['created_at'][:16]}")
            lines.append(
                f"- Engagement: {p['engagement']} "
                f"(❤️ {p['like_count']} 🔁 {p['repost_count']} "
                f"💬 {p['reply_count']} 💭 {p['quote_count']})"
            )
            if p["paper_urls"]:
                lines.append(f"- PaperURLs: {', '.join(p['paper_urls'])}")
            if p["external_url"] and p["external_url"] not in p["paper_urls"]:
                title = p["external_title"] or p["external_url"]
                lines.append(f"- External: [{title}]({p['external_url']})")
            if len(p["text"]) > 120:
                lines.append(f"- Excerpt: {p['text'][:400]}")
            lines.append("")

        return "\n".join(lines), {}

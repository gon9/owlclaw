"""
owlclaw: X(Twitter) ソースプラグイン。

tools/twitter.py をラップして BaseSource インターフェースに適合させる。
特定アカウントのタイムラインとキーワード検索を組み合わせて取得する。

設定例 (tasks/*.yaml):
  sources:
    - type: twitter
      accounts:
        - zakiryo1533
        - swyx
      queries:
        - "LLMエージェント lang:ja -is:retweet"
        - "AI agent FDE -is:retweet min_faves:20"
      limit: 30
      days: 1
      min_likes: 5        # いいね数フィルタ（ノイズ除去）
      min_retweets: 0     # RT数フィルタ
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime, timedelta

from sources.base import BaseSource
from tools.twitter import TwitterError, fetch_user_tweets, search_tweets


class TwitterSource(BaseSource):
    """X(Twitter) ツイート取得ソースプラグイン。"""

    def fetch(
        self,
        config: dict,
        cutoff: datetime,
        last_seen_per_source: dict | None = None,
    ) -> tuple[str, dict]:
        """指定アカウント・クエリからツイートを取得してMarkdownを返す。

        Parameters
        ----------
        config : dict
            ソース設定。有効キー:
              - accounts (list[str]): タイムライン取得するユーザー名リスト
              - queries (list[str]): 検索クエリリスト
              - limit (int): アカウント・クエリごとの最大取得件数 (デフォルト: 30)
              - days (int): 直近N日分を取得 (デフォルト: 1)
              - min_likes (int): 最低いいね数フィルタ (デフォルト: 0)
              - min_retweets (int): 最低RT数フィルタ (デフォルト: 0)
        cutoff : datetime
            グローバルカットオフ (days 未指定時に使用)
        last_seen_per_source : dict | None
            使用しない

        Returns
        -------
        tuple[str, dict]
            (Markdownテキスト, {})
        """
        accounts: list[str] = config.get("accounts", [])
        queries: list[str] = config.get("queries", [])
        limit: int = int(config.get("limit", 30))
        days: int | None = config.get("days")
        min_likes: int = int(config.get("min_likes", 0))
        min_retweets: int = int(config.get("min_retweets", 0))

        if not accounts and not queries:
            return "## X(Twitter)\n\n*(accounts も queries も設定されていません)*\n", {}

        since = (
            datetime.now(UTC) - timedelta(days=days)
            if days is not None
            else cutoff
        )

        all_tweets: list[dict] = []
        seen_ids: set[str] = set()

        for username in accounts:
            print(f"  [Twitter] @{username} タイムライン取得中...", file=sys.stderr)
            try:
                tweets = fetch_user_tweets(username, limit=limit, since=since)
                added = 0
                for t in tweets:
                    if t["tweet_id"] not in seen_ids:
                        seen_ids.add(t["tweet_id"])
                        all_tweets.append(t)
                        added += 1
                print(f"    {added} 件取得", file=sys.stderr)
            except TwitterError as e:
                print(f"    エラー: {e}", file=sys.stderr)

        for query in queries:
            print(f"  [Twitter] 検索: {query[:50]}", file=sys.stderr)
            try:
                tweets = search_tweets(query, limit=limit, since=since)
                added = 0
                for t in tweets:
                    if t["tweet_id"] not in seen_ids:
                        seen_ids.add(t["tweet_id"])
                        all_tweets.append(t)
                        added += 1
                print(f"    {added} 件取得", file=sys.stderr)
            except TwitterError as e:
                print(f"    エラー: {e}", file=sys.stderr)

        if min_likes > 0:
            before = len(all_tweets)
            all_tweets = [t for t in all_tweets if t["like_count"] >= min_likes]
            print(
                f"  [Twitter] min_likes={min_likes} フィルタ: {before} → {len(all_tweets)} 件",
                file=sys.stderr,
            )

        if min_retweets > 0:
            before = len(all_tweets)
            all_tweets = [t for t in all_tweets if t["retweet_count"] >= min_retweets]
            print(
                f"  [Twitter] min_retweets={min_retweets} フィルタ: "
                f"{before} → {len(all_tweets)} 件",
                file=sys.stderr,
            )

        all_tweets.sort(key=lambda t: t["like_count"], reverse=True)

        total = len(all_tweets)
        print(f"  [Twitter] 合計 {total} 件", file=sys.stderr)

        label = f"X(Twitter) ({total}件)"
        lines = [f"## {label}\n"]

        if not all_tweets:
            lines.append("*(取得できませんでした)*\n")
            return "\n".join(lines), {}

        for i, t in enumerate(all_tweets, 1):
            views = f" | 👁 {t['view_count']}" if t["view_count"] else ""
            lines.append(f"### {i}. {t['text'][:120].replace(chr(10), ' ')}")
            lines.append(f"- URL: {t['url']}")
            lines.append(f"- Author: @{t['author']} ({t['author_display']})")
            lines.append(f"- Date: {t['created_at'][:16]}")
            lines.append(f"- Engagement: ❤️ {t['like_count']} 🔁 {t['retweet_count']}{views}")
            if len(t["text"]) > 120:
                lines.append(f"- FullText: {t['text']}")
            lines.append("")

        return "\n".join(lines), {}

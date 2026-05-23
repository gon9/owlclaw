"""
owlclaw: X(Twitter) ツイート取得ツール。

Twitter API v2 (tweepy) を使用してユーザータイムライン・キーワード検索でツイートを取得する。
認証は Bearer Token のみ（アプリ専用読み取り）。

CLI:
  # セットアップ案内（初回のみ）
  uv run python -m tools.twitter --setup

  # ユーザータイムライン取得
  uv run python -m tools.twitter --user zakiryo1533 --limit 20 --days 1

  # キーワード検索
  uv run python -m tools.twitter --query "LLMエージェント lang:ja" --limit 20 --days 1

  # JSON 出力
  uv run python -m tools.twitter --user sama --json

認証について:
  .env に TWITTER_BEARER_TOKEN=xxx を設定する。
  Bearer Token は developer.twitter.com のアプリ設定ページで取得。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TypedDict

import tweepy

PROJ = Path(__file__).parent.parent

_TWEET_FIELDS = ["created_at", "public_metrics"]
_USER_FIELDS = ["username", "name"]


class TweetResult(TypedDict):
    """1ツイートの取得結果。"""

    tweet_id: str
    url: str
    text: str
    author: str
    author_display: str
    created_at: str
    like_count: int
    retweet_count: int
    reply_count: int
    view_count: int | None


class TwitterError(Exception):
    """Twitter取得エラー。"""


def _client() -> tweepy.Client:
    """Bearer Token で tweepy.Client を初期化する。"""
    token = os.environ.get("TWITTER_BEARER_TOKEN")
    if not token:
        raise TwitterError(
            "TWITTER_BEARER_TOKEN が未設定です。\n"
            ".env に TWITTER_BEARER_TOKEN=xxx を追加してください。\n"
            "取得方法: uv run python -m tools.twitter --setup"
        )
    return tweepy.Client(bearer_token=token, wait_on_rate_limit=False)


def _to_result(
    tweet: tweepy.Tweet,
    username: str,
    display_name: str,
) -> TweetResult:
    """tweepy.Tweet を TweetResult に変換する。"""
    metrics: dict = tweet.public_metrics or {}
    return TweetResult(
        tweet_id=str(tweet.id),
        url=f"https://x.com/{username}/status/{tweet.id}",
        text=tweet.text,
        author=username,
        author_display=display_name,
        created_at=tweet.created_at.isoformat() if tweet.created_at else "",
        like_count=metrics.get("like_count", 0),
        retweet_count=metrics.get("retweet_count", 0),
        reply_count=metrics.get("reply_count", 0),
        view_count=metrics.get("impression_count"),
    )


def fetch_user_tweets(
    username: str,
    limit: int = 20,
    since: datetime | None = None,
) -> list[TweetResult]:
    """ユーザータイムラインからツイートを取得する。

    Parameters
    ----------
    username : str
        Twitter ユーザー名 (@なし)
    limit : int
        最大取得件数
    since : datetime | None
        これより古いツイートを除外 (UTC aware)

    Returns
    -------
    list[TweetResult]
        ツイート一覧

    Raises
    ------
    TwitterError
        取得失敗時
    """
    client = _client()

    try:
        user_resp = client.get_user(username=username, user_fields=_USER_FIELDS)
    except tweepy.TweepyException as e:
        raise TwitterError(f"ユーザー情報取得失敗: @{username} — {e}") from e

    if user_resp.data is None:
        raise TwitterError(f"ユーザーが見つかりません: @{username}")

    user = user_resp.data
    kwargs: dict = {
        "id": user.id,
        "max_results": min(limit, 100),
        "tweet_fields": _TWEET_FIELDS,
        "exclude": ["retweets", "replies"],
    }
    if since:
        kwargs["start_time"] = since

    try:
        resp = client.get_users_tweets(**kwargs)
    except tweepy.TweepyException as e:
        raise TwitterError(f"タイムライン取得失敗: @{username} — {e}") from e

    if resp.data is None:
        return []

    return [_to_result(t, user.username, user.name) for t in resp.data[:limit]]


def search_tweets(
    query: str,
    limit: int = 20,
    since: datetime | None = None,
) -> list[TweetResult]:
    """キーワード検索でツイートを取得する。

    Parameters
    ----------
    query : str
        検索クエリ (Twitter 検索構文対応: lang:ja, -is:retweet など)
    limit : int
        最大取得件数
    since : datetime | None
        これより古いツイートを除外 (UTC aware)

    Returns
    -------
    list[TweetResult]
        ツイート一覧

    Raises
    ------
    TwitterError
        取得失敗時
    """
    client = _client()
    kwargs: dict = {
        "query": query + " -is:retweet",
        "max_results": min(limit, 100),
        "tweet_fields": _TWEET_FIELDS,
        "expansions": ["author_id"],
        "user_fields": _USER_FIELDS,
    }
    if since:
        kwargs["start_time"] = since

    try:
        resp = client.search_recent_tweets(**kwargs)
    except tweepy.TweepyException as e:
        raise TwitterError(f"検索失敗: {query} — {e}") from e

    if resp.data is None:
        return []

    user_map: dict[str, tweepy.User] = {}
    if resp.includes and "users" in resp.includes:
        for u in resp.includes["users"]:
            user_map[str(u.id)] = u

    results = []
    for tweet in resp.data[:limit]:
        u = user_map.get(str(tweet.author_id))
        uname = u.username if u else str(tweet.author_id)
        dname = u.name if u else uname
        results.append(_to_result(tweet, uname, dname))

    return results


if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv(PROJ / ".env")

    parser = argparse.ArgumentParser(description="X(Twitter) ツイート取得ツール (Twitter API v2)")
    parser.add_argument("--setup", action="store_true", help="Bearer Token 取得方法を表示")
    parser.add_argument("--user", metavar="USERNAME", help="タイムライン取得するユーザー名")
    parser.add_argument("--query", metavar="QUERY", help="検索クエリ")
    parser.add_argument("--limit", type=int, default=20, help="最大取得件数")
    parser.add_argument("--days", type=int, default=1, help="直近N日分を取得")
    parser.add_argument("--json", action="store_true", dest="output_json", help="JSON 出力")
    parser.add_argument("--min-likes", type=int, default=0, help="最低いいね数フィルタ")
    args = parser.parse_args()

    if args.setup:
        print("""
=== Twitter API v2 Bearer Token セットアップ ===

1. https://developer.twitter.com/en/portal/dashboard にアクセス
2. アプリを作成（または既存アプリを選択）
3. [Keys and tokens] → [Bearer Token] をコピー
4. .env に以下を追加:

   TWITTER_BEARER_TOKEN=AAAAAAAAAAAAAAAAAAAAxxx...

Free プランでも読み取り可能 (月 500k ツイートまで)。
""")
        sys.exit(0)

    since_dt = datetime.now(UTC) - timedelta(days=args.days)

    try:
        if args.user:
            tweets = fetch_user_tweets(args.user, limit=args.limit, since=since_dt)
        elif args.query:
            tweets = search_tweets(args.query, limit=args.limit, since=since_dt)
        else:
            parser.print_help()
            sys.exit(1)
    except TwitterError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    if args.min_likes:
        tweets = [t for t in tweets if t["like_count"] >= args.min_likes]

    if args.output_json:
        print(json.dumps(tweets, ensure_ascii=False, indent=2))
    else:
        for t in tweets:
            print(f"@{t['author']} ({t['created_at'][:16]})")
            print(f"  {t['text'][:200].replace(chr(10), ' ')}")
            views = f"👁 {t['view_count']}" if t["view_count"] else ""
            print(f"  ❤️ {t['like_count']}  🔁 {t['retweet_count']}  {views}")
            print(f"  {t['url']}")
            print()

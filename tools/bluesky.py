"""
owlclaw: Bluesky 公開API クライアント。

`https://public.api.bsky.app/xrpc/` の認証不要エンドポイントを叩いて、
Starter Pack 起点で AI/ML コミュニティのポストを収集する。

設計参考: shi3z/siki@844f88d

CLI:
  # デフォルト Starter Pack から handle 一覧を解決
  uv run python -m tools.bluesky --resolve

  # 特定 handle の最新ポストを表示
  uv run python -m tools.bluesky --author karpathy.bsky.social --limit 10

依存: 標準ライブラリのみ (urllib, json, concurrent.futures)
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path

PROJ = Path(__file__).parent.parent

BLUESKY_PUBLIC_API = "https://public.api.bsky.app/xrpc/"

# siki@844f88d の defaultBlueskyAIStarterPacks をそのまま流用
DEFAULT_STARTER_PACKS: list[str] = [
    "at://did:plc:bmkptaqvfcwmgom75fmo5oo6/app.bsky.graph.starterpack/3laeesmwbi62l",
    "at://did:plc:oqqpxzlqy7m7z2zqps3rjrts/app.bsky.graph.starterpack/3m2mrpgmdql2d",
    "at://did:plc:oqqpxzlqy7m7z2zqps3rjrts/app.bsky.graph.starterpack/3lbdjhpwhwa23",
    "at://did:plc:z3lil7hj3jloch4r3owljui5/app.bsky.graph.starterpack/3lcpvfls27723",
    "at://did:plc:q7tjqlj55q5j54aoipdc6r7i/app.bsky.graph.starterpack/3lawbuqz4yv27",
    "at://did:plc:5ldqhnk4quyil4mie2yjg2po/app.bsky.graph.starterpack/3llhdncyla32y",
    "at://did:plc:mptsx33lhqsobeooj5k23cqh/app.bsky.graph.starterpack/3lnsym7j76w2f",
    "at://did:plc:vtpyqvwce4x6gpa5dcizqecy/app.bsky.graph.starterpack/3lbuyxxgv432y",
    "at://did:plc:al62dnktcv4nwprgml2ryfnz/app.bsky.graph.starterpack/3lbhmp4cwl72w",
    "at://did:plc:7xmdqtvxy43625hisyy4wksb/app.bsky.graph.starterpack/3lgxxttp4u722",
]

DEFAULT_HANDLE_CACHE = PROJ / "state" / "bluesky_handles.json"

_PAPER_URL_PATTERNS = [
    re.compile(r"https?://arxiv\.org/(?:abs|pdf)/[\w./-]+", re.IGNORECASE),
    re.compile(r"https?://(?:www\.)?huggingface\.co/papers/[\w./-]+", re.IGNORECASE),
    re.compile(r"https?://openreview\.net/(?:forum|pdf)\?id=[\w-]+", re.IGNORECASE),
    re.compile(r"https?://(?:www\.)?aclanthology\.org/[\w./-]+", re.IGNORECASE),
]

_USER_AGENT = "owlclaw/0.1 (+https://github.com/)"


class BlueskyError(Exception):
    """Bluesky API 呼び出しの失敗を表す例外。"""


def _get(endpoint: str, params: dict[str, str] | None = None, timeout: float = 15.0) -> dict:
    """公開API GETヘルパ。

    Parameters
    ----------
    endpoint : str
        XRPCエンドポイント名 (例: "app.bsky.feed.getAuthorFeed")
    params : dict | None
        クエリパラメータ
    timeout : float
        タイムアウト秒数

    Returns
    -------
    dict
        パース済みJSON

    Raises
    ------
    BlueskyError
        HTTPエラー or JSONパース失敗時
    """
    url = BLUESKY_PUBLIC_API + endpoint
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(
        url,
        headers={"Accept": "application/json", "User-Agent": _USER_AGENT},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
            body = resp.read()
    except urllib.error.HTTPError as e:
        raise BlueskyError(f"HTTP {e.code} for {endpoint}: {e.reason}") from e
    except urllib.error.URLError as e:
        raise BlueskyError(f"URLError for {endpoint}: {e.reason}") from e
    try:
        return json.loads(body.decode("utf-8"))
    except json.JSONDecodeError as e:
        raise BlueskyError(f"JSON decode failed for {endpoint}: {e}") from e


def fetch_starter_pack_members(at_uri: str) -> list[str]:
    """Starter Pack から所属ハンドル一覧を取得する。

    Parameters
    ----------
    at_uri : str
        Starter Pack の AT-URI (at://did:plc:.../app.bsky.graph.starterpack/...)

    Returns
    -------
    list[str]
        ハンドル文字列のリスト（重複なし）
    """
    sp_resp = _get(
        "app.bsky.graph.getStarterPack",
        {"starterPack": at_uri},
    )
    list_uri = (
        sp_resp.get("starterPack", {}).get("list", {}).get("uri", "")
    )
    if not list_uri:
        raise BlueskyError(f"No list URI in starter pack {at_uri}")

    handles: list[str] = []
    seen: set[str] = set()
    cursor: str | None = None
    while True:
        params = {"list": list_uri, "limit": "100"}
        if cursor:
            params["cursor"] = cursor
        page = _get("app.bsky.graph.getList", params)
        items = page.get("items", [])
        for item in items:
            handle = item.get("subject", {}).get("handle", "")
            if handle and handle not in seen:
                seen.add(handle)
                handles.append(handle)
        cursor = page.get("cursor")
        if not cursor or not items:
            break
    return handles


def resolve_handles(
    starter_packs: list[str] | None = None,
    cache_path: Path | None = None,
    ttl_hours: int = 24,
    sleep_sec: float = 0.2,
) -> list[str]:
    """Starter Pack から handle 一覧を解決する（ディスクキャッシュ付き）。

    Parameters
    ----------
    starter_packs : list[str] | None
        Starter Pack の AT-URI 一覧。None なら `DEFAULT_STARTER_PACKS`。
    cache_path : Path | None
        キャッシュJSONパス。None なら `DEFAULT_HANDLE_CACHE`。
    ttl_hours : int
        キャッシュ有効時間（時間）
    sleep_sec : float
        Starter Pack 間のスリープ秒（APIマナー）

    Returns
    -------
    list[str]
        ユニークなハンドル一覧
    """
    cache_path = cache_path or DEFAULT_HANDLE_CACHE
    packs = starter_packs if starter_packs else DEFAULT_STARTER_PACKS

    # キャッシュ読み込み
    if cache_path.exists():
        try:
            cached = json.loads(cache_path.read_text(encoding="utf-8"))
            fetched_at = datetime.fromisoformat(cached.get("fetched_at", ""))
            cached_packs = cached.get("starter_packs", [])
            age_h = (datetime.now(UTC) - fetched_at).total_seconds() / 3600
            if age_h < ttl_hours and cached_packs == packs and cached.get("handles"):
                print(
                    f"  [Bluesky] handle キャッシュ利用: {len(cached['handles'])} 件 "
                    f"(age={age_h:.1f}h)",
                    file=sys.stderr,
                )
                return cached["handles"]
        except (json.JSONDecodeError, ValueError, KeyError):
            pass

    # 再解決
    all_handles: list[str] = []
    seen: set[str] = set()
    for pack_uri in packs:
        try:
            handles = fetch_starter_pack_members(pack_uri)
            for h in handles:
                if h not in seen:
                    seen.add(h)
                    all_handles.append(h)
            print(
                f"  [Bluesky] starter pack {pack_uri[-12:]}: {len(handles)} 件",
                file=sys.stderr,
            )
        except BlueskyError as e:
            print(f"  [Bluesky] starter pack {pack_uri[-12:]} 失敗: {e}", file=sys.stderr)
        time.sleep(sleep_sec)

    if all_handles:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(
            json.dumps(
                {
                    "starter_packs": packs,
                    "handles": all_handles,
                    "fetched_at": datetime.now(UTC).isoformat(),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        print(
            f"  [Bluesky] 解決完了: {len(all_handles)} unique handles "
            f"(from {len(packs)} starter packs)",
            file=sys.stderr,
        )
    return all_handles


def _extract_paper_urls(*texts: str) -> list[str]:
    """テキスト群から論文URL候補を重複なしで抽出する。"""
    found: list[str] = []
    seen: set[str] = set()
    for t in texts:
        if not t:
            continue
        for pat in _PAPER_URL_PATTERNS:
            for m in pat.findall(t):
                if m not in seen:
                    seen.add(m)
                    found.append(m)
    return found


def _post_url(uri: str, handle: str) -> str:
    """at-URI から bsky.app のWeb URLを組み立てる。"""
    rkey = uri.rsplit("/", 1)[-1] if "/" in uri else uri
    return f"https://bsky.app/profile/{handle}/post/{rkey}"


def _normalize_feed_item(item: dict) -> dict | None:
    """getAuthorFeed のfeedアイテム1件を正規化dict化する。

    Returns
    -------
    dict | None
        正規化済みポスト dict。パース不能なら None。
    """
    post = item.get("post", {})
    uri = post.get("uri", "")
    if not uri:
        return None
    author = post.get("author", {})
    handle = author.get("handle", "")
    record = post.get("record", {}) or {}
    text = record.get("text", "") if isinstance(record, dict) else ""
    created_at = record.get("createdAt", "") if isinstance(record, dict) else ""

    external_url: str | None = None
    external_title: str | None = None

    # record.embed.external
    rec_embed = record.get("embed") if isinstance(record, dict) else None
    if isinstance(rec_embed, dict):
        ext = rec_embed.get("external")
        if isinstance(ext, dict):
            external_url = ext.get("uri") or None
            external_title = ext.get("title") or None

    # post.embed (hydrated)
    post_embed = post.get("embed")
    if isinstance(post_embed, dict) and not external_url:
        ext = post_embed.get("external")
        if isinstance(ext, dict):
            external_url = ext.get("uri") or None
            external_title = ext.get("title") or None

    like_count = int(post.get("likeCount", 0) or 0)
    repost_count = int(post.get("repostCount", 0) or 0)
    reply_count = int(post.get("replyCount", 0) or 0)
    quote_count = int(post.get("quoteCount", 0) or 0)

    paper_urls = _extract_paper_urls(text, external_url or "")

    return {
        "uri": uri,
        "url": _post_url(uri, handle),
        "text": text,
        "author": handle,
        "author_display": author.get("displayName", "") or handle,
        "created_at": created_at,
        "like_count": like_count,
        "repost_count": repost_count,
        "reply_count": reply_count,
        "quote_count": quote_count,
        "engagement": engagement_score(
            like_count, repost_count, reply_count, quote_count
        ),
        "external_url": external_url,
        "external_title": external_title,
        "paper_urls": paper_urls,
    }


def engagement_score(
    like_count: int, repost_count: int, reply_count: int, quote_count: int
) -> int:
    """siki と同じエンゲージメント式: like + repost*3 + reply*2 + quote*2"""
    return like_count + repost_count * 3 + reply_count * 2 + quote_count * 2


def fetch_author_feed(
    handle: str, limit: int = 50, since: datetime | None = None
) -> list[dict]:
    """特定アカウントの直近ポストを取得して正規化リストで返す。

    Parameters
    ----------
    handle : str
        アカウントハンドル (例: "karpathy.bsky.social")
    limit : int
        最大取得件数 (1-100)
    since : datetime | None
        これより古いポストは除外（UTC aware）

    Returns
    -------
    list[dict]
        正規化済みポスト dict のリスト
    """
    resp = _get(
        "app.bsky.feed.getAuthorFeed",
        {
            "actor": handle,
            "limit": str(min(max(limit, 1), 100)),
            "filter": "posts_no_replies",
        },
    )
    posts: list[dict] = []
    for item in resp.get("feed", []):
        norm = _normalize_feed_item(item)
        if not norm:
            continue
        if since and norm["created_at"]:
            try:
                created = datetime.fromisoformat(
                    norm["created_at"].replace("Z", "+00:00")
                )
                if created < since:
                    continue
            except ValueError:
                pass
        posts.append(norm)
    return posts


def fetch_all_posts(
    handles: list[str],
    limit: int = 50,
    since: datetime | None = None,
    max_workers: int = 5,
    sleep_sec: float = 0.2,
) -> list[dict]:
    """複数 handle からポストを並列取得して URI で重複除去する。

    Parameters
    ----------
    handles : list[str]
    limit : int
        handleあたりの最大件数
    since : datetime | None
        UTC aware datetime。これより古いポストを除外
    max_workers : int
        並列数
    sleep_sec : float
        各リクエスト前のスリープ秒（APIマナー）

    Returns
    -------
    list[dict]
        正規化済みポスト dict（created_at 降順）
    """
    if not handles:
        return []

    def _task(h: str) -> list[dict]:
        time.sleep(sleep_sec)
        try:
            return fetch_author_feed(h, limit=limit, since=since)
        except BlueskyError as e:
            print(f"  [Bluesky] @{h} 取得失敗: {e}", file=sys.stderr)
            return []

    all_posts: list[dict] = []
    seen: set[str] = set()
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = {ex.submit(_task, h): h for h in handles}
        for fut in as_completed(futures):
            for p in fut.result():
                if p["uri"] not in seen:
                    seen.add(p["uri"])
                    all_posts.append(p)

    all_posts.sort(key=lambda p: p.get("created_at", ""), reverse=True)
    return all_posts


def _cli_resolve() -> None:
    """CLI: starter pack から handle 一覧を解決して表示する。"""
    handles = resolve_handles()
    print(f"\n=== {len(handles)} unique handles ===")
    for h in handles:
        print(h)


def _cli_author(handle: str, limit: int) -> None:
    """CLI: 特定 handle のポストを表示する。"""
    posts = fetch_author_feed(handle, limit=limit)
    print(f"\n=== @{handle} {len(posts)} posts ===")
    for p in posts:
        print(f"- [{p['engagement']:3d}] {p['created_at'][:16]} {p['text'][:80]}")
        if p["paper_urls"]:
            print(f"    📄 {p['paper_urls']}")


def main(argv: list[str] | None = None) -> int:
    """CLIエントリポイント。"""
    parser = argparse.ArgumentParser(description="Bluesky 公開API クライアント")
    parser.add_argument(
        "--resolve", action="store_true", help="starter pack から handle 解決"
    )
    parser.add_argument("--author", type=str, help="特定 handle のポストを取得")
    parser.add_argument("--limit", type=int, default=20, help="取得件数")
    args = parser.parse_args(argv)

    if args.resolve:
        _cli_resolve()
        return 0
    if args.author:
        _cli_author(args.author, args.limit)
        return 0
    parser.print_help()
    return 1


__all__ = [
    "BLUESKY_PUBLIC_API",
    "DEFAULT_HANDLE_CACHE",
    "DEFAULT_STARTER_PACKS",
    "BlueskyError",
    "engagement_score",
    "fetch_all_posts",
    "fetch_author_feed",
    "fetch_starter_pack_members",
    "resolve_handles",
]

if __name__ == "__main__":
    sys.exit(main())

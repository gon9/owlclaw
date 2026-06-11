"""tools/bluesky.py のユニットテスト。

公開API は呼ばず `_get` を mock 化して挙動を確認する。
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest

from tools.bluesky import (
    BlueskyError,
    _extract_paper_urls,
    _normalize_feed_item,
    _post_url,
    engagement_score,
    fetch_all_posts,
    fetch_author_feed,
    fetch_starter_pack_members,
    resolve_handles,
)


class TestEngagementScore:
    """siki@844f88d と同じ式: like + repost*3 + reply*2 + quote*2"""

    def test_basic(self) -> None:
        assert engagement_score(10, 0, 0, 0) == 10
        assert engagement_score(0, 1, 0, 0) == 3
        assert engagement_score(0, 0, 1, 0) == 2
        assert engagement_score(0, 0, 0, 1) == 2
        assert engagement_score(5, 2, 3, 1) == 5 + 6 + 6 + 2  # 19


class TestExtractPaperUrls:
    """論文URL抽出ロジック。"""

    def test_arxiv_abs(self) -> None:
        urls = _extract_paper_urls("check this https://arxiv.org/abs/2401.12345")
        assert "https://arxiv.org/abs/2401.12345" in urls

    def test_arxiv_pdf(self) -> None:
        urls = _extract_paper_urls("https://arxiv.org/pdf/2402.00001v2")
        assert urls == ["https://arxiv.org/pdf/2402.00001v2"]

    def test_huggingface_papers(self) -> None:
        urls = _extract_paper_urls("see https://huggingface.co/papers/2403.99999")
        assert urls == ["https://huggingface.co/papers/2403.99999"]

    def test_openreview(self) -> None:
        urls = _extract_paper_urls("https://openreview.net/forum?id=abcDEF123")
        assert urls == ["https://openreview.net/forum?id=abcDEF123"]

    def test_no_match(self) -> None:
        assert _extract_paper_urls("just a tweet without paper") == []

    def test_dedup(self) -> None:
        text = "https://arxiv.org/abs/2401.0001 ... https://arxiv.org/abs/2401.0001"
        urls = _extract_paper_urls(text)
        assert urls == ["https://arxiv.org/abs/2401.0001"]

    def test_multiple_sources(self) -> None:
        urls = _extract_paper_urls(
            "post body",
            "https://arxiv.org/abs/1.1 see https://huggingface.co/papers/2.2",
        )
        assert "https://arxiv.org/abs/1.1" in urls
        assert "https://huggingface.co/papers/2.2" in urls


class TestPostUrl:
    def test_basic(self) -> None:
        uri = "at://did:plc:abc/app.bsky.feed.post/3kxyz123"
        assert _post_url(uri, "alice.bsky.social") == (
            "https://bsky.app/profile/alice.bsky.social/post/3kxyz123"
        )


class TestNormalizeFeedItem:
    def test_full_record(self) -> None:
        item = {
            "post": {
                "uri": "at://did:plc:abc/app.bsky.feed.post/r1",
                "author": {"handle": "alice.bsky.social", "displayName": "Alice"},
                "record": {
                    "text": "check https://arxiv.org/abs/2401.0001",
                    "createdAt": "2026-05-28T01:00:00.000Z",
                    "embed": {
                        "external": {
                            "uri": "https://arxiv.org/abs/2401.0001",
                            "title": "Cool paper",
                        }
                    },
                },
                "likeCount": 10,
                "repostCount": 2,
                "replyCount": 1,
                "quoteCount": 0,
            }
        }
        norm = _normalize_feed_item(item)
        assert norm is not None
        assert norm["author"] == "alice.bsky.social"
        assert norm["author_display"] == "Alice"
        assert norm["like_count"] == 10
        assert norm["repost_count"] == 2
        assert norm["engagement"] == 10 + 6 + 2  # 18
        assert norm["external_url"] == "https://arxiv.org/abs/2401.0001"
        assert "https://arxiv.org/abs/2401.0001" in norm["paper_urls"]
        assert norm["url"].endswith("/post/r1")

    def test_missing_uri_returns_none(self) -> None:
        assert _normalize_feed_item({"post": {}}) is None

    def test_no_embed(self) -> None:
        item = {
            "post": {
                "uri": "at://x/y/z",
                "author": {"handle": "h"},
                "record": {"text": "plain post", "createdAt": "2026-01-01T00:00:00Z"},
                "likeCount": 0,
                "repostCount": 0,
                "replyCount": 0,
                "quoteCount": 0,
            }
        }
        norm = _normalize_feed_item(item)
        assert norm is not None
        assert norm["external_url"] is None
        assert norm["paper_urls"] == []


class TestFetchStarterPackMembers:
    @patch("tools.bluesky._get")
    def test_paginated(self, mock_get) -> None:
        # 1回目: starter pack metadata
        # 2回目: list page1 (cursor あり)
        # 3回目: list page2 (cursor なし)
        mock_get.side_effect = [
            {"starterPack": {"list": {"uri": "at://list/1"}}},
            {
                "items": [
                    {"subject": {"handle": "alice.bsky.social"}},
                    {"subject": {"handle": "bob.bsky.social"}},
                ],
                "cursor": "c1",
            },
            {
                "items": [
                    {"subject": {"handle": "carol.bsky.social"}},
                    {"subject": {"handle": "alice.bsky.social"}},  # dup
                ],
                "cursor": "",
            },
        ]
        handles = fetch_starter_pack_members("at://starter/pack")
        assert handles == [
            "alice.bsky.social",
            "bob.bsky.social",
            "carol.bsky.social",
        ]
        assert mock_get.call_count == 3

    @patch("tools.bluesky._get")
    def test_missing_list_uri(self, mock_get) -> None:
        mock_get.return_value = {"starterPack": {"list": {}}}
        with pytest.raises(BlueskyError):
            fetch_starter_pack_members("at://starter/pack")


class TestFetchAuthorFeed:
    @patch("tools.bluesky._get")
    def test_basic(self, mock_get) -> None:
        mock_get.return_value = {
            "feed": [
                {
                    "post": {
                        "uri": "at://x/y/r1",
                        "author": {"handle": "alice"},
                        "record": {
                            "text": "https://arxiv.org/abs/9999.0001",
                            "createdAt": "2026-05-28T00:00:00Z",
                        },
                        "likeCount": 5,
                        "repostCount": 1,
                        "replyCount": 0,
                        "quoteCount": 0,
                    }
                }
            ]
        }
        posts = fetch_author_feed("alice.bsky.social", limit=10)
        assert len(posts) == 1
        assert posts[0]["paper_urls"] == ["https://arxiv.org/abs/9999.0001"]

    @patch("tools.bluesky._get")
    def test_since_filter(self, mock_get) -> None:
        old = (datetime.now(UTC) - timedelta(days=7)).isoformat().replace("+00:00", "Z")
        new = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        mock_get.return_value = {
            "feed": [
                {
                    "post": {
                        "uri": "at://x/y/old",
                        "author": {"handle": "a"},
                        "record": {"text": "old", "createdAt": old},
                        "likeCount": 0,
                        "repostCount": 0,
                        "replyCount": 0,
                        "quoteCount": 0,
                    }
                },
                {
                    "post": {
                        "uri": "at://x/y/new",
                        "author": {"handle": "a"},
                        "record": {"text": "new", "createdAt": new},
                        "likeCount": 0,
                        "repostCount": 0,
                        "replyCount": 0,
                        "quoteCount": 0,
                    }
                },
            ]
        }
        since = datetime.now(UTC) - timedelta(days=1)
        posts = fetch_author_feed("a", since=since)
        assert len(posts) == 1
        assert posts[0]["uri"].endswith("/new")


class TestFetchAllPosts:
    @patch("tools.bluesky.fetch_author_feed")
    def test_dedupe_and_sort(self, mock_fetch) -> None:
        def _side(handle: str, limit: int = 50, since=None):  # noqa: ARG001
            base = {
                "like_count": 0,
                "repost_count": 0,
                "reply_count": 0,
                "quote_count": 0,
                "engagement": 0,
                "external_url": None,
                "external_title": None,
                "paper_urls": [],
                "text": "t",
                "author": handle,
                "author_display": handle,
                "url": f"u/{handle}",
            }
            if handle == "a":
                return [
                    {**base, "uri": "p1", "created_at": "2026-05-28T05:00:00Z"},
                    {**base, "uri": "p2", "created_at": "2026-05-28T03:00:00Z"},
                ]
            return [
                {**base, "uri": "p1", "created_at": "2026-05-28T05:00:00Z"},  # dup
                {**base, "uri": "p3", "created_at": "2026-05-28T07:00:00Z"},
            ]

        mock_fetch.side_effect = _side
        posts = fetch_all_posts(["a", "b"], sleep_sec=0, max_workers=2)
        uris = [p["uri"] for p in posts]
        # 重複なし & created_at 降順
        assert uris == ["p3", "p1", "p2"]

    @patch("tools.bluesky.fetch_author_feed")
    def test_handle_failure_continues(self, mock_fetch) -> None:
        def _side(handle: str, **_kwargs):
            if handle == "bad":
                raise BlueskyError("boom")
            return [
                {
                    "uri": "ok1",
                    "url": "u",
                    "text": "t",
                    "author": handle,
                    "author_display": handle,
                    "created_at": "2026-05-28T00:00:00Z",
                    "like_count": 0,
                    "repost_count": 0,
                    "reply_count": 0,
                    "quote_count": 0,
                    "engagement": 0,
                    "external_url": None,
                    "external_title": None,
                    "paper_urls": [],
                }
            ]

        mock_fetch.side_effect = _side
        posts = fetch_all_posts(["good", "bad"], sleep_sec=0)
        assert len(posts) == 1


class TestResolveHandlesCache:
    @patch("tools.bluesky.fetch_starter_pack_members")
    def test_cache_hit(self, mock_fetch, tmp_path) -> None:
        cache = tmp_path / "h.json"
        cache.write_text(
            json.dumps(
                {
                    "starter_packs": ["pack1"],
                    "handles": ["a.bsky", "b.bsky"],
                    "fetched_at": datetime.now(UTC).isoformat(),
                }
            ),
            encoding="utf-8",
        )
        handles = resolve_handles(["pack1"], cache_path=cache)
        assert handles == ["a.bsky", "b.bsky"]
        mock_fetch.assert_not_called()

    @patch("tools.bluesky.fetch_starter_pack_members")
    def test_cache_expired_refetch(self, mock_fetch, tmp_path) -> None:
        cache = tmp_path / "h.json"
        cache.write_text(
            json.dumps(
                {
                    "starter_packs": ["pack1"],
                    "handles": ["old"],
                    "fetched_at": (
                        datetime.now(UTC) - timedelta(hours=48)
                    ).isoformat(),
                }
            ),
            encoding="utf-8",
        )
        mock_fetch.return_value = ["fresh.bsky"]
        handles = resolve_handles(
            ["pack1"], cache_path=cache, ttl_hours=24, sleep_sec=0
        )
        assert handles == ["fresh.bsky"]
        # キャッシュ更新確認
        new_cache = json.loads(cache.read_text(encoding="utf-8"))
        assert new_cache["handles"] == ["fresh.bsky"]

    @patch("tools.bluesky.fetch_starter_pack_members")
    def test_pack_failure_continues(self, mock_fetch, tmp_path) -> None:
        cache = tmp_path / "h.json"

        def _side(pack):
            if pack == "bad":
                raise BlueskyError("nope")
            return ["good.bsky"]

        mock_fetch.side_effect = _side
        handles = resolve_handles(["bad", "ok"], cache_path=cache, sleep_sec=0)
        assert handles == ["good.bsky"]

"""sources/bluesky.py のユニットテスト。"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import patch

from sources.bluesky import BlueskySource


def _make_post(
    uri: str = "at://x/y/r1",
    text: str = "check https://arxiv.org/abs/2401.0001",
    author: str = "alice.bsky.social",
    like_count: int = 10,
    repost_count: int = 2,
    paper_urls: list[str] | None = None,
) -> dict:
    paper_urls = paper_urls if paper_urls is not None else ["https://arxiv.org/abs/2401.0001"]
    return {
        "uri": uri,
        "url": f"https://bsky.app/profile/{author}/post/{uri.rsplit('/', 1)[-1]}",
        "text": text,
        "author": author,
        "author_display": author,
        "created_at": "2026-05-28T00:00:00Z",
        "like_count": like_count,
        "repost_count": repost_count,
        "reply_count": 0,
        "quote_count": 0,
        "engagement": like_count + repost_count * 3,
        "external_url": None,
        "external_title": None,
        "paper_urls": paper_urls,
    }


class TestBlueskySourceFetch:
    @patch("sources.bluesky.fetch_all_posts")
    @patch("sources.bluesky.resolve_handles")
    def test_basic_markdown(self, mock_resolve, mock_fetch) -> None:
        mock_resolve.return_value = ["alice.bsky.social"]
        mock_fetch.return_value = [_make_post()]

        md, latest = BlueskySource().fetch(
            {"days": 1, "require_paper_url": True},
            datetime.now(UTC),
        )
        assert "Bluesky" in md
        assert "### 1." in md
        assert "PaperURLs:" in md
        assert "https://arxiv.org/abs/2401.0001" in md
        assert latest == {}

    @patch("sources.bluesky.fetch_all_posts")
    @patch("sources.bluesky.resolve_handles")
    def test_min_engagement_filter(self, mock_resolve, mock_fetch) -> None:
        mock_resolve.return_value = ["a"]
        mock_fetch.return_value = [
            _make_post(uri="at://x/y/hi", like_count=100, repost_count=0),
            _make_post(uri="at://x/y/lo", like_count=1, repost_count=0),
        ]
        md, _ = BlueskySource().fetch(
            {"min_engagement": 10, "require_paper_url": False},
            datetime.now(UTC),
        )
        assert "/hi" in md
        assert "/lo" not in md

    @patch("sources.bluesky.fetch_all_posts")
    @patch("sources.bluesky.resolve_handles")
    def test_require_paper_url_filter(self, mock_resolve, mock_fetch) -> None:
        mock_resolve.return_value = ["a"]
        mock_fetch.return_value = [
            _make_post(uri="at://x/y/p1", paper_urls=["https://arxiv.org/abs/1.1"]),
            _make_post(uri="at://x/y/p2", text="no paper here", paper_urls=[]),
        ]
        md, _ = BlueskySource().fetch(
            {"require_paper_url": True},
            datetime.now(UTC),
        )
        assert "/p1" in md
        assert "/p2" not in md

    @patch("sources.bluesky.fetch_all_posts")
    @patch("sources.bluesky.resolve_handles")
    def test_sorted_by_engagement(self, mock_resolve, mock_fetch) -> None:
        mock_resolve.return_value = ["a"]
        mock_fetch.return_value = [
            _make_post(uri="at://x/y/low", text="low https://arxiv.org/abs/1", like_count=5),
            _make_post(uri="at://x/y/hi", text="hi https://arxiv.org/abs/2", like_count=500),
        ]
        md, _ = BlueskySource().fetch(
            {"require_paper_url": True},
            datetime.now(UTC),
        )
        pos_hi = md.find("### 1.")
        pos_lo = md.find("### 2.")
        # hi がより上（### 1.）
        assert pos_hi < md.find("/hi") < pos_lo

    @patch("sources.bluesky.fetch_all_posts")
    @patch("sources.bluesky.resolve_handles")
    def test_no_handles_resolved(self, mock_resolve, mock_fetch) -> None:
        mock_resolve.return_value = []
        md, _ = BlueskySource().fetch({}, datetime.now(UTC))
        assert "handle が解決できませんでした" in md
        mock_fetch.assert_not_called()

    @patch("sources.bluesky.fetch_all_posts")
    @patch("sources.bluesky.resolve_handles")
    def test_extra_handles_merged(self, mock_resolve, mock_fetch) -> None:
        mock_resolve.return_value = ["a.bsky"]
        mock_fetch.return_value = []
        BlueskySource().fetch(
            {"handles": ["b.bsky", "a.bsky"]},  # a.bsky は重複
            datetime.now(UTC),
        )
        # fetch_all_posts に渡された handle 一覧を確認
        called_handles = mock_fetch.call_args[0][0]
        assert called_handles == ["a.bsky", "b.bsky"]

    @patch("sources.bluesky.fetch_all_posts")
    @patch("sources.bluesky.resolve_handles")
    def test_empty_posts_message(self, mock_resolve, mock_fetch) -> None:
        mock_resolve.return_value = ["a"]
        mock_fetch.return_value = []
        md, _ = BlueskySource().fetch({}, datetime.now(UTC))
        assert "該当ポストなし" in md

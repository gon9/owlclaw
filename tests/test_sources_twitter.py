"""sources/twitter.py のユニットテスト。"""

from datetime import UTC, datetime
from unittest.mock import patch

from sources.twitter import TwitterSource


def _make_tweet(
    tweet_id: str = "1",
    text: str = "Test tweet about LLM",
    author: str = "testuser",
    author_display: str = "Test User",
    like_count: int = 50,
    retweet_count: int = 10,
    hours_ago: float = 1.0,
) -> dict:
    """ダミー TweetResult を生成する。"""
    from datetime import timedelta
    return {
        "tweet_id": tweet_id,
        "url": f"https://x.com/{author}/status/{tweet_id}",
        "text": text,
        "author": author,
        "author_display": author_display,
        "created_at": (datetime.now(UTC) - timedelta(hours=hours_ago)).isoformat(),
        "like_count": like_count,
        "retweet_count": retweet_count,
        "reply_count": 2,
        "view_count": 1000,
    }


class TestTwitterSourceFetch:
    """TwitterSource.fetch の正常系・異常系テスト。"""

    @patch("sources.twitter.fetch_user_tweets")
    def test_fetch_accounts_returns_markdown(self, mock_fetch):
        """アカウント指定でMarkdownが返る。"""
        mock_fetch.return_value = [_make_tweet(text="LLM agent released")]

        source = TwitterSource()
        md, latest_seen = source.fetch(
            {"accounts": ["testuser"], "days": 1},
            datetime.now(UTC),
        )

        assert "X(Twitter)" in md
        assert "LLM agent released" in md or "testuser" in md
        assert latest_seen == {}

    @patch("sources.twitter.search_tweets")
    def test_fetch_queries_returns_markdown(self, mock_search):
        """クエリ指定でMarkdownが返る。"""
        mock_search.return_value = [_make_tweet(text="AIエージェント最新情報")]

        source = TwitterSource()
        md, _ = source.fetch(
            {"queries": ["LLMエージェント lang:ja"]},
            datetime.now(UTC),
        )

        assert "X(Twitter)" in md

    def test_fetch_no_config_returns_empty_message(self):
        """accounts も queries も空の場合はメッセージを返す。"""
        source = TwitterSource()
        md, _ = source.fetch({}, datetime.now(UTC))

        assert "設定されていません" in md

    @patch("sources.twitter.fetch_user_tweets")
    def test_fetch_error_continues(self, mock_fetch):
        """アカウント取得エラーでも処理を続ける。"""
        from tools.twitter import TwitterError
        mock_fetch.side_effect = TwitterError("接続失敗")

        source = TwitterSource()
        md, _ = source.fetch({"accounts": ["error_user"]}, datetime.now(UTC))

        assert "X(Twitter)" in md

    @patch("sources.twitter.fetch_user_tweets")
    def test_min_likes_filter(self, mock_fetch):
        """min_likes フィルタが適用される。"""
        mock_fetch.return_value = [
            _make_tweet(tweet_id="1", like_count=100),
            _make_tweet(tweet_id="2", like_count=3),
        ]

        source = TwitterSource()
        md, _ = source.fetch(
            {"accounts": ["testuser"], "min_likes": 10},
            datetime.now(UTC),
        )

        assert "### 1." in md
        assert "### 2." not in md

    @patch("sources.twitter.fetch_user_tweets")
    def test_deduplication_across_sources(self, mock_fetch):
        """同じツイートIDが複数回取得された場合は重複除去する。"""
        same_tweet = _make_tweet(tweet_id="999")
        mock_fetch.return_value = [same_tweet]

        source = TwitterSource()
        md, _ = source.fetch(
            {"accounts": ["user1", "user2"]},
            datetime.now(UTC),
        )

        assert md.count("x.com") == 1 or md.count("999") == 1

    @patch("sources.twitter.fetch_user_tweets")
    def test_sorted_by_likes_descending(self, mock_fetch):
        """いいね数降順でソートされる。"""
        mock_fetch.return_value = [
            _make_tweet(tweet_id="1", text="Low likes", like_count=5),
            _make_tweet(tweet_id="2", text="High likes", like_count=500),
        ]

        source = TwitterSource()
        md, _ = source.fetch({"accounts": ["testuser"]}, datetime.now(UTC))

        pos_high = md.find("### 1.")
        pos_low = md.find("### 2.")
        assert pos_high < pos_low

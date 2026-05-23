"""tools/twitter.py のユニットテスト。"""

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from tools.twitter import (
    TwitterError,
    _to_result,
    fetch_user_tweets,
    search_tweets,
)


def _make_tweepy_tweet(
    tweet_id: int = 1234567890,
    text: str = "Test tweet about LLM agents",
    like_count: int = 100,
    retweet_count: int = 20,
    reply_count: int = 5,
    impression_count: int | None = 5000,
    hours_ago: float = 1.0,
    author_id: int = 9999,
) -> MagicMock:
    """モック用 tweepy.Tweet オブジェクトを生成する。"""
    tweet = MagicMock()
    tweet.id = tweet_id
    tweet.text = text
    tweet.created_at = datetime.now(UTC) - timedelta(hours=hours_ago)
    tweet.author_id = author_id
    tweet.public_metrics = {
        "like_count": like_count,
        "retweet_count": retweet_count,
        "reply_count": reply_count,
        "impression_count": impression_count,
    }
    return tweet


def _make_tweepy_user(
    user_id: int = 9999,
    username: str = "testuser",
    name: str = "Test User",
) -> MagicMock:
    """モック用 tweepy.User オブジェクトを生成する。"""
    user = MagicMock()
    user.id = user_id
    user.username = username
    user.name = name
    return user


class TestToResult:
    """_to_result の変換テスト。"""

    def test_converts_tweet_to_result(self):
        """tweepy.Tweet を TweetResult に正しく変換する。"""
        tweet = _make_tweepy_tweet(tweet_id=9999, text="Hello LLM world", like_count=42)
        result = _to_result(tweet, "aiengineer", "AI Engineer")

        assert result["tweet_id"] == "9999"
        assert result["text"] == "Hello LLM world"
        assert result["author"] == "aiengineer"
        assert result["author_display"] == "AI Engineer"
        assert result["like_count"] == 42
        assert "created_at" in result
        assert "aiengineer/status/9999" in result["url"]

    def test_none_metrics_becomes_zero(self):
        """public_metrics が None の場合はゼロ値を返す。"""
        tweet = _make_tweepy_tweet()
        tweet.public_metrics = None
        result = _to_result(tweet, "user", "User")
        assert result["like_count"] == 0
        assert result["retweet_count"] == 0
        assert result["view_count"] is None

    def test_impression_count_maps_to_view_count(self):
        """impression_count が view_count に対応する。"""
        tweet = _make_tweepy_tweet(impression_count=12345)
        result = _to_result(tweet, "user", "User")
        assert result["view_count"] == 12345

    def test_view_count_can_be_none(self):
        """impression_count が None なら view_count も None。"""
        tweet = _make_tweepy_tweet(impression_count=None)
        result = _to_result(tweet, "user", "User")
        assert result["view_count"] is None


class TestFetchUserTweets:
    """fetch_user_tweets の正常系・異常系テスト。"""

    @patch("tools.twitter._client")
    def test_returns_tweets_for_valid_user(self, mock_client_fn):
        """有効なユーザーのツイートリストを返す。"""
        client = MagicMock()
        mock_client_fn.return_value = client

        user = _make_tweepy_user(user_id=1, username="zakiryo1533", name="ザキ")
        client.get_user.return_value = MagicMock(data=user)

        tweets = [
            _make_tweepy_tweet(tweet_id=10, text="LLM news", hours_ago=1),
            _make_tweepy_tweet(tweet_id=11, text="AI agent", hours_ago=2),
        ]
        client.get_users_tweets.return_value = MagicMock(data=tweets)

        results = fetch_user_tweets("zakiryo1533", limit=10)

        assert len(results) == 2
        assert results[0]["tweet_id"] == "10"
        assert results[0]["author"] == "zakiryo1533"

    @patch("tools.twitter._client")
    def test_user_not_found_raises(self, mock_client_fn):
        """ユーザーが見つからない場合は TwitterError を送出する。"""
        client = MagicMock()
        mock_client_fn.return_value = client
        client.get_user.return_value = MagicMock(data=None)

        with pytest.raises(TwitterError, match="ユーザーが見つかりません"):
            fetch_user_tweets("nonexistent_user")

    @patch("tools.twitter._client")
    def test_no_tweets_returns_empty_list(self, mock_client_fn):
        """ツイートがない場合は空リストを返す。"""
        client = MagicMock()
        mock_client_fn.return_value = client

        user = _make_tweepy_user()
        client.get_user.return_value = MagicMock(data=user)
        client.get_users_tweets.return_value = MagicMock(data=None)

        results = fetch_user_tweets("testuser")
        assert results == []

    @patch("tools.twitter._client")
    def test_since_passed_as_start_time(self, mock_client_fn):
        """since が start_time として API に渡される。"""
        client = MagicMock()
        mock_client_fn.return_value = client

        user = _make_tweepy_user()
        client.get_user.return_value = MagicMock(data=user)
        client.get_users_tweets.return_value = MagicMock(data=[])

        since = datetime.now(UTC) - timedelta(days=3)
        fetch_user_tweets("testuser", since=since)

        call_kwargs = client.get_users_tweets.call_args[1]
        assert call_kwargs["start_time"] == since


class TestSearchTweets:
    """search_tweets の正常系・異常系テスト。"""

    @patch("tools.twitter._client")
    def test_returns_results_with_author_info(self, mock_client_fn):
        """検索結果にauthor情報が含まれる。"""
        client = MagicMock()
        mock_client_fn.return_value = client

        tweet = _make_tweepy_tweet(tweet_id=99, author_id=42)
        user = _make_tweepy_user(user_id=42, username="airesearcher", name="AI Researcher")

        resp = MagicMock()
        resp.data = [tweet]
        resp.includes = {"users": [user]}
        client.search_recent_tweets.return_value = resp

        results = search_tweets("LLM agent lang:ja")

        assert len(results) == 1
        assert results[0]["author"] == "airesearcher"
        assert results[0]["tweet_id"] == "99"

    @patch("tools.twitter._client")
    def test_no_retweet_appended_to_query(self, mock_client_fn):
        """-is:retweet が自動付与される。"""
        client = MagicMock()
        mock_client_fn.return_value = client
        client.search_recent_tweets.return_value = MagicMock(data=None)

        search_tweets("LLM")

        call_kwargs = client.search_recent_tweets.call_args[1]
        assert "-is:retweet" in call_kwargs["query"]

    @patch("tools.twitter._client")
    def test_empty_response_returns_empty_list(self, mock_client_fn):
        """結果なしの場合は空リストを返す。"""
        client = MagicMock()
        mock_client_fn.return_value = client
        client.search_recent_tweets.return_value = MagicMock(data=None)

        assert search_tweets("no results") == []


class TestClientInit:
    """_client() の初期化テスト。"""

    def test_missing_bearer_token_raises(self):
        """TWITTER_BEARER_TOKEN 未設定時は TwitterError を送出する。"""
        from tools.twitter import _client
        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(TwitterError, match="TWITTER_BEARER_TOKEN"):
                _client()

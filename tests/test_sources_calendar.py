"""sources/calendar.py のユニットテスト。"""

from datetime import UTC, datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from sources.calendar import (
    CalendarSource,
    _has_external_attendee,
    _is_physical,
    _parse_event_dt,
    _parse_range,
)

JST = timezone(timedelta(hours=9))


def _make_event(
    event_id: str = "evt001",
    summary: str = "取引先ミーティング",
    location: str = "東京都千代田区1-1-1",
    start_offset_hours: float = 2.0,
    duration_hours: float = 1.0,
    attendees: list[dict] | None = None,
) -> dict:
    """モック用 Google Calendar イベント辞書を生成する。"""
    now = datetime.now(JST)
    start_dt = now + timedelta(hours=start_offset_hours)
    end_dt = start_dt + timedelta(hours=duration_hours)
    return {
        "id": event_id,
        "summary": summary,
        "location": location,
        "start": {"dateTime": start_dt.isoformat()},
        "end": {"dateTime": end_dt.isoformat()},
        "attendees": attendees or [],
        "description": "",
    }


class TestIsPhysical:
    """_is_physical のユニットテスト。"""

    def test_physical_address_returns_true(self):
        """物理住所はTrueを返す。"""
        assert _is_physical("東京都千代田区大手町1-1-1") is True

    def test_zoom_url_returns_false(self):
        """Zoom URLを含む場合はFalseを返す。"""
        assert _is_physical("https://zoom.us/j/12345") is False

    def test_google_meet_returns_false(self):
        """Google Meetリンクはオンライン判定。"""
        assert _is_physical("meet.google.com/abc-defg-hij") is False

    def test_teams_returns_false(self):
        """Microsoft Teamsリンクはオンライン判定。"""
        assert _is_physical("https://teams.microsoft.com/l/meetup-join/xxx") is False

    def test_empty_location_returns_false(self):
        """場所未設定はFalseを返す。"""
        assert _is_physical("") is False
        assert _is_physical(None) is False


class TestHasExternalAttendee:
    """_has_external_attendee のユニットテスト。"""

    def test_external_attendee_returns_true(self):
        """外部ドメインの参加者がいればTrueを返す。"""
        attendees = [{"email": "user@external.com"}]
        assert _has_external_attendee(attendees, "mycompany.com") is True

    def test_only_internal_returns_false(self):
        """全員内部ドメインならFalseを返す。"""
        attendees = [
            {"email": "alice@mycompany.com"},
            {"email": "bob@mycompany.com"},
        ]
        assert _has_external_attendee(attendees, "mycompany.com") is False

    def test_no_owner_domain_returns_true_if_attendees(self):
        """owner_domain未指定かつ参加者ありはTrueを返す。"""
        attendees = [{"email": "anyone@example.com"}]
        assert _has_external_attendee(attendees, None) is True

    def test_empty_attendees_returns_false(self):
        """参加者なしはFalseを返す。"""
        assert _has_external_attendee([], "mycompany.com") is False


class TestParseEventDt:
    """_parse_event_dt のユニットテスト。"""

    def test_datetime_parsed_as_utc_aware(self):
        """dateTime フィールドがある場合 UTC aware datetime を返す。"""
        now = datetime.now(JST)
        dt_obj = {"dateTime": now.isoformat()}
        result = _parse_event_dt(dt_obj)
        assert result is not None
        assert result.tzinfo is not None

    def test_all_day_event_returns_none(self):
        """終日イベント（date フィールドのみ）はNoneを返す。"""
        dt_obj = {"date": "2026-05-10"}
        assert _parse_event_dt(dt_obj) is None


class TestParseRange:
    """_parse_range のユニットテスト。"""

    def test_today_returns_today_range(self):
        """'today' は当日の 0:00〜24:00 (UTC) を返す。"""
        now = datetime.now(UTC)
        start, end = _parse_range("today", now)
        assert (end - start).total_seconds() == 86400

    def test_tomorrow_returns_tomorrow_range(self):
        """'tomorrow' は翌日の 0:00〜24:00 (UTC) を返す。"""
        now = datetime.now(UTC)
        today_start, _ = _parse_range("today", now)
        tomorrow_start, tomorrow_end = _parse_range("tomorrow", now)
        assert tomorrow_start == today_start + timedelta(days=1)
        assert (tomorrow_end - tomorrow_start).total_seconds() == 86400

    def test_n_days_returns_correct_range(self):
        """'3 days' は 3日分の範囲を返す。"""
        now = datetime.now(UTC)
        start, end = _parse_range("3 days", now)
        assert abs((end - start).total_seconds() - 3 * 86400) < 1


class TestCalendarSourceFetch:
    """CalendarSource.fetch のユニットテスト。"""

    @patch("sources.calendar._build_service")
    def test_fetch_returns_markdown_with_events(self, mock_build):
        """正常ケース: イベントが Markdown に変換される。"""
        service = MagicMock()
        mock_build.return_value = service
        event = _make_event(
            event_id="evt1",
            summary="商談 with 株式会社ABC",
            location="東京都渋谷区1-2-3",
            attendees=[{"email": "partner@abc.co.jp"}],
        )
        service.events.return_value.list.return_value.execute.return_value = {
            "items": [event]
        }

        source = CalendarSource()
        config = {"range": "today"}
        md, state = source.fetch(config, datetime.now(UTC))

        assert "商談 with 株式会社ABC" in md
        assert "evt1" in state.get("__calendar_notified_ids__", [])

    @patch("sources.calendar._build_service")
    def test_physical_filter_excludes_online(self, mock_build):
        """location_kind: physical でオンラインイベントが除外される。"""
        service = MagicMock()
        mock_build.return_value = service
        physical = _make_event(
            event_id="phys1", location="大阪市北区1-1-1",
            attendees=[{"email": "x@external.com"}],
        )
        online = _make_event(
            event_id="online1", location="https://zoom.us/j/999",
            attendees=[{"email": "y@external.com"}],
        )
        service.events.return_value.list.return_value.execute.return_value = {
            "items": [physical, online]
        }

        source = CalendarSource()
        config = {"range": "today", "filter": {"location_kind": "physical"}}
        md, state = source.fetch(config, datetime.now(UTC))

        assert "phys1" in state.get("__calendar_notified_ids__", [])
        assert "online1" not in state.get("__calendar_notified_ids__", [])

    @patch("sources.calendar._build_service")
    def test_notified_ids_are_skipped(self, mock_build):
        """既通知イベントID はスキップされる。"""
        service = MagicMock()
        mock_build.return_value = service
        event = _make_event(event_id="already_notified")
        service.events.return_value.list.return_value.execute.return_value = {
            "items": [event]
        }

        source = CalendarSource()
        config = {
            "range": "today",
            "__notified_event_ids__": ["already_notified"],
        }
        md, state = source.fetch(config, datetime.now(UTC))

        assert "already_notified" not in state.get("__calendar_notified_ids__", [])
        assert "*(対象イベントなし)*" in md

    @patch("sources.calendar._build_service")
    def test_no_events_returns_empty_message(self, mock_build):
        """イベントが 0 件の場合は空メッセージを返す。"""
        service = MagicMock()
        mock_build.return_value = service
        service.events.return_value.list.return_value.execute.return_value = {"items": []}

        source = CalendarSource()
        md, state = source.fetch({"range": "today"}, datetime.now(UTC))

        assert "*(対象イベントなし)*" in md
        assert state.get("__calendar_notified_ids__") == []

    @patch("sources.calendar._build_service")
    def test_auth_error_returns_error_md(self, mock_build):
        """認証エラー時はエラー Markdown を返す。"""
        mock_build.side_effect = RuntimeError("トークンが見つかりません")

        source = CalendarSource()
        md, state = source.fetch({"range": "today"}, datetime.now(UTC))

        assert "⚠️ 認証エラー" in md
        assert state == {}

    @patch("sources.calendar._build_service")
    def test_external_attendee_filter(self, mock_build):
        """attendees_have_external: any で参加者なしイベントが除外される。"""
        service = MagicMock()
        mock_build.return_value = service
        with_attendee = _make_event(
            event_id="with_att",
            location="東京都中央区1-1",
            attendees=[{"email": "partner@other.com"}],
        )
        without_attendee = _make_event(
            event_id="no_att",
            location="東京都中央区2-2",
            attendees=[],
        )
        service.events.return_value.list.return_value.execute.return_value = {
            "items": [with_attendee, without_attendee]
        }

        source = CalendarSource()
        config = {
            "range": "today",
            "filter": {"attendees_have_external": "any"},
        }
        md, state = source.fetch(config, datetime.now(UTC))

        ids = state.get("__calendar_notified_ids__", [])
        assert "with_att" in ids
        assert "no_att" not in ids

    @patch("sources.calendar._build_service")
    def test_physical_event_without_attendees_included(self, mock_build):
        """visit-briefing 回帰: 外部参加者フィルタなしなら参加者なしの物理外出も拾う。

        個人外出（例: ワイン会）は物理ロケーションがあっても招待参加者がいない。
        attendees_have_external を付けない場合、これらが除外されてはならない。
        """
        service = MagicMock()
        mock_build.return_value = service
        personal_outing = _make_event(
            event_id="wine_party",
            summary="ワイン会",
            location="タイムレス渋谷（Timeless Shibuya）, 東京都渋谷区神宮前5-34-10",
            attendees=[],
        )
        service.events.return_value.list.return_value.execute.return_value = {
            "items": [personal_outing]
        }

        source = CalendarSource()
        # visit-briefing.yaml と同じ filter（location_kind のみ、external 要件なし）
        config = {"range": "tomorrow", "filter": {"location_kind": "physical"}}
        md, state = source.fetch(config, datetime.now(UTC))

        assert "wine_party" in state.get("__calendar_notified_ids__", [])
        assert "ワイン会" in md

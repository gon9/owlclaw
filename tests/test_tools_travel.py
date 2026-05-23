"""tools/travel.py のユニットテスト。"""

from datetime import date

from tools.travel import (
    CHECKLIST_DAYS,
    build_context_md,
    days_until,
    get_pending_checklists,
    merge_trips,
)


def _trip(
    departure: str,
    destinations: list[str] | None = None,
    checklist_sent: dict | None = None,
    bookings: dict | None = None,
) -> dict:
    """テスト用旅程辞書を生成する。"""
    return {
        "departure_date": departure,
        "destinations": destinations or [],
        "checklist_sent": checklist_sent or {},
        "bookings": bookings or {},
    }


class TestDaysUntil:
    """days_until のユニットテスト。"""

    def test_same_day_returns_zero(self):
        """出発日当日は 0 を返す。"""
        assert days_until("2026-06-15", date(2026, 6, 15)) == 0

    def test_tomorrow_returns_one(self):
        """翌日出発は 1 を返す。"""
        assert days_until("2026-06-15", date(2026, 6, 14)) == 1

    def test_past_date_returns_negative(self):
        """過去の出発日は負の値を返す。"""
        assert days_until("2026-06-15", date(2026, 6, 16)) == -1

    def test_fourteen_days_returns_14(self):
        """14 日前は 14 を返す。"""
        assert days_until("2026-06-15", date(2026, 6, 1)) == 14


class TestGetPendingChecklists:
    """get_pending_checklists のユニットテスト。"""

    def test_d14_triggers_when_today_is_d14(self):
        """出発 14 日前に D-14 が pending になる。"""
        today = date(2026, 6, 1)
        trips = {"2026-06-osaka": _trip("2026-06-15")}
        pending = get_pending_checklists(trips, today)
        assert len(pending) == 1
        trip_id, _, d_n = pending[0]
        assert trip_id == "2026-06-osaka"
        assert d_n == 14

    def test_already_sent_is_skipped(self):
        """checklist_sent が True の場合はスキップされる。"""
        today = date(2026, 6, 1)
        trips = {
            "2026-06-osaka": _trip(
                "2026-06-15",
                checklist_sent={"D-14": True},
            )
        }
        pending = get_pending_checklists(trips, today)
        assert pending == []

    def test_non_checklist_day_returns_empty(self):
        """D-N 以外の日は空リストを返す。"""
        today = date(2026, 6, 5)  # D-10: 対象外
        trips = {"2026-06-osaka": _trip("2026-06-15")}
        pending = get_pending_checklists(trips, today)
        assert pending == []

    def test_all_checklist_days_trigger(self):
        """CHECKLIST_DAYS 全てで pending になる。"""
        for d_n in CHECKLIST_DAYS:
            departure = date(2026, 6, 1) + __import__("datetime").timedelta(days=d_n)
            trips = {"trip": _trip(departure.isoformat())}
            pending = get_pending_checklists(trips, date(2026, 6, 1))
            assert len(pending) == 1, f"D-{d_n} で pending にならなかった"

    def test_trip_without_departure_date_is_skipped(self):
        """departure_date 未設定の旅程はスキップされる。"""
        trips = {"2026-06-osaka": {"destinations": ["大阪"], "checklist_sent": {}}}
        pending = get_pending_checklists(trips, date(2026, 6, 1))
        assert pending == []


class TestMergeTrips:
    """merge_trips のユニットテスト。"""

    def test_new_trip_is_added(self):
        """新規旅程が追加される。"""
        existing = {}
        updates = {"2026-06-osaka": _trip("2026-06-15", destinations=["大阪"])}
        result = merge_trips(existing, updates)
        assert "2026-06-osaka" in result
        assert result["2026-06-osaka"]["departure_date"] == "2026-06-15"

    def test_existing_trip_is_updated(self):
        """既存旅程のフィールドが更新される。"""
        existing = {"2026-06-osaka": _trip("2026-06-15")}
        updates = {"2026-06-osaka": {"departure_date": "2026-06-16"}}
        result = merge_trips(existing, updates)
        assert result["2026-06-osaka"]["departure_date"] == "2026-06-16"

    def test_bookings_sub_dict_merged(self):
        """bookings は sub-dict レベルでマージされる（上書きではなく）。"""
        existing = {
            "2026-06-osaka": _trip(
                "2026-06-15",
                bookings={"flight": {"confirmed": True, "ref": "JL203"}},
            )
        }
        updates = {
            "2026-06-osaka": {
                "bookings": {"hotel": {"confirmed": True, "ref": "HT001"}}
            }
        }
        result = merge_trips(existing, updates)
        bookings = result["2026-06-osaka"]["bookings"]
        assert bookings["flight"]["ref"] == "JL203"
        assert bookings["hotel"]["ref"] == "HT001"

    def test_checklist_sent_sub_dict_merged(self):
        """checklist_sent も sub-dict マージされる。"""
        existing = {
            "2026-06-osaka": _trip(
                "2026-06-15",
                checklist_sent={"D-14": True},
            )
        }
        updates = {"2026-06-osaka": {"checklist_sent": {"D-7": True}}}
        result = merge_trips(existing, updates)
        sent = result["2026-06-osaka"]["checklist_sent"]
        assert sent["D-14"] is True
        assert sent["D-7"] is True

    def test_other_trips_not_affected(self):
        """更新対象外の旅程は変更されない。"""
        existing = {
            "2026-06-osaka": _trip("2026-06-15"),
            "2026-07-tokyo": _trip("2026-07-01"),
        }
        updates = {"2026-06-osaka": {"departure_date": "2026-06-16"}}
        result = merge_trips(existing, updates)
        assert result["2026-07-tokyo"]["departure_date"] == "2026-07-01"


class TestBuildContextMd:
    """build_context_md のユニットテスト。"""

    def test_empty_trips_returns_empty_message(self):
        """旅程なしは '登録済み旅程なし' を返す。"""
        md = build_context_md({})
        assert "登録済み旅程なし" in md

    def test_includes_trip_id_and_departure(self):
        """旅程IDと出発日が含まれる。"""
        trips = {"2026-06-osaka": _trip("2026-06-15", destinations=["大阪"])}
        md = build_context_md(trips, date(2026, 6, 1))
        assert "2026-06-osaka" in md
        assert "2026-06-15" in md
        assert "大阪" in md

    def test_d_n_label_included(self):
        """D-N ラベルが含まれる。"""
        trips = {"2026-06-osaka": _trip("2026-06-15")}
        md = build_context_md(trips, date(2026, 6, 1))
        assert "D-14" in md

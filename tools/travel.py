"""
owlclaw: 旅程台帳ユーティリティ。

旅程 state の D-N 計算・チェックリスト判定・旅程マージなどのヘルパー関数を提供する。
orchestrator.py および travel-checklist タスクから利用する。
"""

from __future__ import annotations

from datetime import date

CHECKLIST_DAYS = [14, 7, 3, 1]


def days_until(departure_date_str: str, today: date | None = None) -> int:
    """出発日までの残り日数を返す。過去は負の値。

    Parameters
    ----------
    departure_date_str : str
        出発日 (YYYY-MM-DD 形式)
    today : date | None
        基準日。None の場合は今日

    Returns
    -------
    int
        出発日まで (today が今日なら 0 = 当日, 1 = 明日)
    """
    if today is None:
        today = date.today()
    departure = date.fromisoformat(departure_date_str)
    return (departure - today).days


def get_pending_checklists(
    trips: dict,
    today: date | None = None,
) -> list[tuple[str, dict, int]]:
    """D-N チェックリストを送るべき旅程と D-N 値を返す。

    Parameters
    ----------
    trips : dict
        state["trips"] 辞書 (trip_id → trip_data)
    today : date | None
        基準日。None の場合は今日

    Returns
    -------
    list[tuple[str, dict, int]]
        (trip_id, trip_data, d_n) のリスト。空のこともある
    """
    if today is None:
        today = date.today()
    pending = []
    for trip_id, trip in trips.items():
        departure = trip.get("departure_date")
        if not departure:
            continue
        d_n = days_until(departure, today)
        if d_n not in CHECKLIST_DAYS:
            continue
        checklist_sent: dict = trip.get("checklist_sent", {})
        key = f"D-{d_n}"
        if checklist_sent.get(key):
            continue
        pending.append((trip_id, trip, d_n))
    return pending


def merge_trips(existing: dict, updates: dict) -> dict:
    """既存 trips と更新辞書を深いマージで合成する。

    updates の各 trip_id について:
    - 新規なら追加
    - 既存なら dict レベルで更新（checklist_sent / bookings は sub-dict マージ）

    Parameters
    ----------
    existing : dict
        現在の state["trips"]
    updates : dict
        Claude が書き出した trips_update.json の中身

    Returns
    -------
    dict
        マージ後の trips 辞書
    """
    result = dict(existing)
    for trip_id, new_data in updates.items():
        if trip_id not in result:
            result[trip_id] = new_data
            continue
        current = dict(result[trip_id])
        for key, value in new_data.items():
            if key in ("bookings", "checklist_sent") and isinstance(value, dict):
                current[key] = {**current.get(key, {}), **value}
            else:
                current[key] = value
        result[trip_id] = current
    return result


def build_context_md(trips: dict, today: date | None = None) -> str:
    """travel-checklist タスク向けに旅程一覧を Markdown で返す。

    Parameters
    ----------
    trips : dict
        state["trips"] 辞書
    today : date | None
        基準日

    Returns
    -------
    str
        Markdown テキスト
    """
    if today is None:
        today = date.today()
    if not trips:
        return "# 旅程一覧\n\n*(登録済み旅程なし)*\n"

    lines = [f"# 旅程一覧 — {today.isoformat()}", ""]
    for trip_id, trip in sorted(trips.items()):
        departure = trip.get("departure_date", "未定")
        d_n = days_until(departure, today) if departure != "未定" else None
        d_label = f"D-{d_n}" if d_n is not None else ""
        destinations = ", ".join(trip.get("destinations", []))
        lines += [
            f"## {trip_id}",
            f"- 出発日: {departure} ({d_label})" if d_label else f"- 出発日: {departure}",
            f"- 目的地: {destinations}" if destinations else "- 目的地: 未設定",
        ]
        bookings = trip.get("bookings", {})
        if bookings:
            lines.append("- 予約状況:")
            for btype, binfo in bookings.items():
                if binfo is None:
                    lines.append(f"  - {btype}: 不要")
                elif isinstance(binfo, dict):
                    confirmed = "✅" if binfo.get("confirmed") else "❌"
                    ref = binfo.get("ref", "")
                    lines.append(f"  - {btype}: {confirmed}" + (f" ({ref})" if ref else ""))
        sent = trip.get("checklist_sent", {})
        sent_list = [k for k, v in sent.items() if v]
        if sent_list:
            lines.append(f"- 送付済みチェックリスト: {', '.join(sent_list)}")
        lines.append("")
    return "\n".join(lines)

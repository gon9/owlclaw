"""
owlclaw: Google Calendar ソースプラグイン。

Google Calendar API を使い、指定期間のイベントを取得して Markdown に変換する。
物理開催フィルタ・外部参加者フィルタ・重複通知抑止をサポート。

初回認証には scripts/auth_calendar.py を先に実行しておく必要がある。
"""

from __future__ import annotations

import re
import sys
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

from sources.base import BaseSource

PROJ = Path(__file__).parent.parent
JST = timezone(datetime.now(UTC).astimezone().utcoffset())

CREDS_PATH = PROJ / "secrets" / "calendar_oauth.json"
TOKEN_PATH = PROJ / "secrets" / "calendar_token.json"
SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]

_ONLINE_PATTERN = re.compile(
    r"(zoom\.us|meet\.google|teams\.microsoft|webex|whereby|jitsi|skype)",
    re.IGNORECASE,
)


def _build_service():
    """OAuth 認証して Calendar API サービスオブジェクトを返す。"""
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    creds = None
    if TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            TOKEN_PATH.write_text(creds.to_json(), encoding="utf-8")
        else:
            raise RuntimeError(
                f"Calendar トークンが存在しないか期限切れです。"
                f"先に `uv run python scripts/auth_calendar.py` を実行してください。"
                f"（トークンパス: {TOKEN_PATH}）"
            )

    return build("calendar", "v3", credentials=creds)


def _parse_event_dt(dt_obj: dict) -> datetime | None:
    """イベントの start/end 辞書から UTC aware datetime を返す。終日イベントは None。"""
    if "dateTime" in dt_obj:
        return datetime.fromisoformat(dt_obj["dateTime"]).astimezone(UTC)
    return None


def _is_physical(location: str | None) -> bool:
    """ロケーション文字列が物理開催かどうかを判定する。

    URL・オンライン会議サービス名が含まれる場合はオンラインと判定する。
    ロケーション未設定は False を返す。
    """
    if not location:
        return False
    return not bool(_ONLINE_PATTERN.search(location))


def _has_external_attendee(attendees: list[dict], owner_domain: str | None) -> bool:
    """外部参加者（owner_domain 以外のメールドメイン）が含まれるか判定する。

    owner_domain が None の場合は参加者が 1 人以上いれば True を返す。
    """
    if not attendees:
        return False
    if owner_domain is None:
        return True
    for att in attendees:
        email = att.get("email", "")
        if email and not email.endswith(f"@{owner_domain}"):
            return True
    return False


def _parse_range(range_str: str, now: datetime) -> tuple[datetime, datetime]:
    """range 文字列 ('today' / 'tomorrow' / 'N days') を (start, end) UTC に変換する。"""
    today_start = now.astimezone(JST).replace(hour=0, minute=0, second=0, microsecond=0)
    today_start_utc = today_start.astimezone(UTC)

    if range_str == "today":
        return today_start_utc, today_start_utc + timedelta(days=1)
    if range_str == "tomorrow":
        return today_start_utc + timedelta(days=1), today_start_utc + timedelta(days=2)
    if range_str.endswith("days"):
        try:
            n = int(range_str.split()[0])
            return today_start_utc, today_start_utc + timedelta(days=n)
        except ValueError:
            pass
    return today_start_utc, today_start_utc + timedelta(days=1)


def _format_event_md(event: dict, idx: int) -> list[str]:
    """1イベントを Markdown リストとして整形する。"""
    summary = event.get("summary", "(タイトルなし)")
    location = event.get("location", "")
    description = (event.get("description") or "")[:300]

    start_dt = _parse_event_dt(event.get("start", {}))
    end_dt = _parse_event_dt(event.get("end", {}))

    if start_dt:
        start_str = start_dt.astimezone(JST).strftime("%H:%M")
        end_str = end_dt.astimezone(JST).strftime("%H:%M") if end_dt else ""
        time_str = f"{start_str}〜{end_str}" if end_str else start_str
    else:
        time_str = "終日"

    attendees = event.get("attendees", [])
    att_emails = [a.get("email", "") for a in attendees if a.get("email")]

    lines = [
        f"## {idx}. {summary}",
        f"- 時間: {time_str}",
    ]
    if location:
        lines.append(f"- 場所: {location}")
    if att_emails:
        lines.append(f"- 参加者: {', '.join(att_emails[:10])}")
    if description.strip():
        lines.append(f"- 概要: {description.strip()[:200]}")
    lines.append(f"- イベントID: `{event.get('id', '')}`")
    lines.append("")
    return lines


class CalendarSource(BaseSource):
    """Google Calendar API ソースプラグイン。"""

    def fetch(
        self,
        config: dict,
        cutoff: datetime,
        last_seen_per_source: dict | None = None,
    ) -> tuple[str, dict]:
        """
        Google Calendar からイベントを取得し (Markdown, state_patch) を返す。

        Parameters
        ----------
        config : dict
            タスク YAML の sources 要素をパースした辞書。
            - range: 'today' / 'tomorrow' / 'N days' (デフォルト 'today')
            - calendar_id: カレンダーID (デフォルト 'primary')
            - filter.location_kind: 'physical' | 'exclude_online' | 'any' (デフォルト 'any')
              'physical' = 住所など物理場所が必須, 'exclude_online' = Zoom等URLのみ除外
            - filter.attendees_have_external: 'any' | None (デフォルト None)
            - owner_domain: 外部参加者判定用の自社ドメイン
            - __notified_event_ids__: 既通知イベントIDリスト（重複抑止）
        cutoff : datetime
            これより古いイベントは除外する閾値 (UTC aware)
        last_seen_per_source : dict | None
            Calendar source では未使用 (RSS 互換引数)

        Returns
        -------
        tuple[str, dict]
            (Markdown テキスト, {"__calendar_notified_ids__": [新規イベントIDリスト]})
        """
        now = datetime.now(UTC)
        range_str: str = config.get("range", "today")
        calendar_id: str = config.get("calendar_id", "primary")
        flt: dict = config.get("filter", {})
        require_external: bool = flt.get("attendees_have_external") == "any"
        owner_domain: str | None = config.get("owner_domain")
        notified_ids: set[str] = set(config.get("__notified_event_ids__", []))

        time_start, time_end = _parse_range(range_str, now)
        date_str = time_start.astimezone(JST).strftime("%Y-%m-%d")

        try:
            service = _build_service()
        except Exception as e:
            print(f"Calendar 認証エラー: {e}", file=sys.stderr)
            return f"# Calendar — {date_str}\n\n⚠️ 認証エラー: {e}\n", {}

        try:
            result = (
                service.events()
                .list(
                    calendarId=calendar_id,
                    timeMin=time_start.isoformat(),
                    timeMax=time_end.isoformat(),
                    maxResults=50,
                    singleEvents=True,
                    orderBy="startTime",
                )
                .execute()
            )
        except Exception as e:
            print(f"Calendar API エラー: {e}", file=sys.stderr)
            return f"# Calendar — {date_str}\n\n⚠️ API エラー: {e}\n", {}

        raw_events = result.get("items", [])
        matched = []
        new_ids = []

        for event in raw_events:
            event_id = event.get("id", "")
            if event_id in notified_ids:
                continue

            location = event.get("location", "")
            attendees = event.get("attendees", [])

            location_kind = flt.get("location_kind")
            if location_kind == "physical" and not _is_physical(location):
                continue
            if location_kind == "exclude_online" and bool(_ONLINE_PATTERN.search(location or "")):
                continue
            if require_external and not _has_external_attendee(attendees, owner_domain):
                continue

            matched.append(event)
            new_ids.append(event_id)

        skipped = sum(1 for e in raw_events if e.get("id", "") in notified_ids)
        filtered_out = len(raw_events) - len(new_ids) - skipped
        print(
            f"✓ Calendar: {len(matched)} 件マッチ"
            f" (既通知 {skipped} 件スキップ, フィルタ除外 {filtered_out} 件)",
            file=sys.stderr,
        )

        lines = [
            f"# カレンダーイベント — {date_str}",
            "",
            f"期間: {time_start.astimezone(JST).strftime('%m/%d %H:%M')}"
            f"〜{time_end.astimezone(JST).strftime('%m/%d %H:%M')}",
            f"マッチ: {len(matched)} 件",
            "",
            "---",
            "",
        ]

        if not matched:
            lines.append("*(対象イベントなし)*")
            lines.append("")
        else:
            for i, event in enumerate(matched, 1):
                lines.extend(_format_event_md(event, i))

        return "\n".join(lines), {"__calendar_notified_ids__": new_ids}

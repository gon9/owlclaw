"""
owlclaw: Gmail ソースプラグイン。

Gmail API を使い、指定クエリにマッチする新着メールを取得して Markdown に変換する。
重複排除は state に保存した seen_email_ids で行う。

初回認証には scripts/auth_gmail.py を先に実行しておく必要がある。
"""

import sys
from datetime import UTC, datetime, timezone
from pathlib import Path

from sources.base import BaseSource

PROJ = Path(__file__).parent.parent
JST = timezone(datetime.now(UTC).astimezone().utcoffset())

CREDS_PATH = PROJ / "secrets" / "gmail_oauth.json"
TOKEN_PATH = PROJ / "secrets" / "gmail_token.json"
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]


def _build_service():
    """OAuth 認証して Gmail API サービスオブジェクトを返す。"""
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
                f"Gmail トークンが存在しないか期限切れです。"
                f"先に `uv run python scripts/auth_gmail.py` を実行してください。"
                f"（トークンパス: {TOKEN_PATH}）"
            )

    return build("gmail", "v1", credentials=creds)


def _extract_headers(msg: dict) -> dict:
    """メッセージペイロードから必要なヘッダーを抽出する。"""
    headers = {}
    for h in msg.get("payload", {}).get("headers", []):
        name = h.get("name", "").lower()
        if name in ("from", "subject", "date"):
            headers[name] = h.get("value", "")
    return headers


class GmailSource(BaseSource):
    """Gmail API ソースプラグイン。"""

    def fetch(
        self,
        config: dict,
        cutoff: datetime,
        last_seen_per_source: dict | None = None,
    ) -> tuple[str, dict]:
        """
        Gmail から新着メールを取得し (Markdown, state_patch) を返す。

        Parameters
        ----------
        config : dict
            タスク YAML の sources 要素をパースした辞書。
            - query: Gmail 検索クエリ文字列
            - max_results: 最大取得件数 (デフォルト 100)
            - __seen_email_ids__: オーケストレーターが注入済みメール ID リスト
        cutoff : datetime
            これより古いメールは除外する閾値 (UTC aware)
        last_seen_per_source : dict | None
            Gmail source では未使用 (RSS 互換引数)

        Returns
        -------
        tuple[str, dict]
            (Markdown テキスト, {"__gmail_seen_ids__": [新規メールIDリスト]})
        """
        query: str = config.get("query", "")
        max_results: int = int(config.get("max_results", 100))
        seen_ids: set[str] = set(config.get("__seen_email_ids__", []))

        date_str = datetime.now(UTC).astimezone(JST).strftime("%Y-%m-%d")

        try:
            service = _build_service()
        except Exception as e:
            print(f"Gmail 認証エラー: {e}", file=sys.stderr)
            error_md = (
                f"# Gmail メール — {date_str}\n\n"
                f"⚠️ 認証エラー: {e}\n"
            )
            return error_md, {}

        try:
            result = (
                service.users()
                .messages()
                .list(userId="me", q=query, maxResults=max_results)
                .execute()
            )
        except Exception as e:
            print(f"Gmail API エラー: {e}", file=sys.stderr)
            error_md = f"# Gmail メール — {date_str}\n\n⚠️ API エラー: {e}\n"
            return error_md, {}

        messages = result.get("messages", [])
        new_items = []
        new_ids = []

        for msg_ref in messages:
            email_id = msg_ref["id"]

            if email_id in seen_ids:
                continue

            try:
                msg = (
                    service.users()
                    .messages()
                    .get(
                        userId="me",
                        id=email_id,
                        format="metadata",
                        metadataHeaders=["From", "Subject", "Date"],
                    )
                    .execute()
                )
            except Exception as e:
                print(f"  メール {email_id} 取得エラー: {e}", file=sys.stderr)
                continue

            internal_date_ms = int(msg.get("internalDate", 0))
            mail_dt = datetime.fromtimestamp(internal_date_ms / 1000, tz=UTC)

            if mail_dt < cutoff:
                continue

            headers = _extract_headers(msg)
            snippet = msg.get("snippet", "")[:200]

            new_ids.append(email_id)
            new_items.append(
                {
                    "id": email_id,
                    "from": headers.get("from", ""),
                    "subject": headers.get("subject", ""),
                    "date": mail_dt.astimezone(JST).strftime("%Y-%m-%d %H:%M"),
                    "snippet": snippet,
                }
            )

        print(
            f"✓ Gmail: {len(new_items)} 件新着 (重複 {len(seen_ids)} 件スキップ)",
            file=sys.stderr,
        )

        lines = [
            f"# Gmail 決済メール — {date_str}",
            "",
            f"クエリ: `{query}`",
            f"新着: {len(new_items)} 件（既読 {len(seen_ids)} 件を除外済み）",
            "",
            "---",
            "",
        ]

        if not new_items:
            lines.append("*(新着メールなし)*")
            lines.append("")
        else:
            for i, item in enumerate(new_items, 1):
                lines.append(f"## {i}. {item['subject']}")
                lines.append(f"- From: {item['from']}")
                lines.append(f"- Date: {item['date']}")
                if item["snippet"]:
                    lines.append(f"- Snippet: {item['snippet']}")
                lines.append("")

        return "\n".join(lines), {"__gmail_seen_ids__": new_ids}

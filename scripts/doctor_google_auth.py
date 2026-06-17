#!/usr/bin/env python3
"""Google OAuth 設定の整合性を診断する。

token 本体や refresh_token は表示しない。OAuth client の project、token の scope、
API で確認できる実アカウント、疎通可否だけを表示する。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from google.auth.exceptions import RefreshError
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

PROJ = Path(__file__).parent.parent
SECRETS = PROJ / "secrets"


@dataclass(frozen=True)
class AuthTarget:
    name: str
    api_name: str
    api_version: str
    oauth_file: Path
    token_file: Path
    scopes: list[str]


TARGETS = [
    AuthTarget(
        name="gmail",
        api_name="gmail",
        api_version="v1",
        oauth_file=SECRETS / "gmail_oauth.json",
        token_file=SECRETS / "gmail_token.json",
        scopes=["https://www.googleapis.com/auth/gmail.readonly"],
    ),
    AuthTarget(
        name="calendar",
        api_name="calendar",
        api_version="v3",
        oauth_file=SECRETS / "calendar_oauth.json",
        token_file=SECRETS / "calendar_token.json",
        scopes=["https://www.googleapis.com/auth/calendar.readonly"],
    ),
    AuthTarget(
        name="drive",
        api_name="drive",
        api_version="v3",
        oauth_file=SECRETS / "drive_oauth.json",
        token_file=SECRETS / "drive_token.json",
        scopes=["https://www.googleapis.com/auth/drive.file"],
    ),
    AuthTarget(
        name="youtube",
        api_name="youtube",
        api_version="v3",
        oauth_file=SECRETS / "youtube_oauth.json",
        token_file=SECRETS / "youtube_token.json",
        scopes=["https://www.googleapis.com/auth/youtube.upload"],
    ),
]


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _oauth_summary(path: Path) -> tuple[str, str]:
    data = _read_json(path)
    if not data:
        return "missing", ""
    body = data.get("installed") or data.get("web") or data
    return str(body.get("project_id") or ""), str(body.get("client_id") or "")[:24]


def _token_summary(path: Path) -> tuple[str, list[str]]:
    data = _read_json(path)
    if not data:
        return "missing", []
    scopes = data.get("scopes") or data.get("scope") or []
    if isinstance(scopes, str):
        scopes = scopes.split()
    return str(data.get("client_id") or "")[:24], [str(scope) for scope in scopes]


def _account_probe(target: AuthTarget) -> tuple[str, str]:
    if not target.token_file.exists():
        return "missing", "token file not found"
    try:
        creds = Credentials.from_authorized_user_file(str(target.token_file), target.scopes)
        service = build(
            target.api_name,
            target.api_version,
            credentials=creds,
            cache_discovery=False,
        )
        if target.name == "gmail":
            profile = service.users().getProfile(userId="me").execute()
            return "ok", str(profile.get("emailAddress") or "")
        if target.name == "calendar":
            calendar = service.calendars().get(calendarId="primary").execute()
            summary = calendar.get("summary") or ""
            calendar_id = calendar.get("id") or ""
            return "ok", f"{calendar_id} ({summary})"
        if target.name == "drive":
            about = service.about().get(fields="user(emailAddress,displayName)").execute()
            user = about.get("user", {})
            email = user.get("emailAddress") or ""
            display = user.get("displayName") or ""
            return "ok", f"{email} ({display})"
        if target.name == "youtube":
            return "ok", "upload scope only; channel identity is not readable"
    except RefreshError as exc:
        return "invalid", str(exc)
    except HttpError as exc:
        return "api_error", str(exc)
    except Exception as exc:  # noqa: BLE001
        return "error", f"{type(exc).__name__}: {exc}"
    return "unknown", ""


def main() -> None:
    for target in TARGETS:
        oauth_project, oauth_client = _oauth_summary(target.oauth_file)
        token_client, token_scopes = _token_summary(target.token_file)
        status, account = _account_probe(target)
        print(f"[{target.name}]")
        print(f"  oauth_project: {oauth_project}")
        print(f"  oauth_client:  {oauth_client}")
        print(f"  token_client:  {token_client}")
        print(f"  token_scopes:  {', '.join(token_scopes) if token_scopes else 'missing'}")
        print(f"  status:        {status}")
        print(f"  account:       {account}")


if __name__ == "__main__":
    main()

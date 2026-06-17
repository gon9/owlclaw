#!/usr/bin/env python3
"""
owlclaw: Google Calendar OAuth 初回認証フロー。

secrets/calendar_oauth.json (GCP の OAuth クライアントシークレット) を使い、
ブラウザ認証を完了して secrets/calendar_token.json を生成する。

事前準備:
  1. GCP コンソール → API とサービス → 認証情報
     → 「OAuth 2.0 クライアント ID」を「デスクトップアプリ」で作成
     （Gmail と同一 GCP プロジェクトを使用可能）
  2. JSON をダウンロードして secrets/calendar_oauth.json として保存
  3. Google Calendar API を有効化しておく

使い方:
  uv run python scripts/auth_calendar.py
"""

import argparse
import sys
from pathlib import Path

PROJ = Path(__file__).parent.parent
CREDS_PATH = PROJ / "secrets" / "calendar_oauth.json"
TOKEN_PATH = PROJ / "secrets" / "calendar_token.json"
SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]


def main() -> None:
    """OAuth フローを実行してトークンを保存する。"""
    parser = argparse.ArgumentParser(description="Google Calendar OAuth 認証を実行")
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="ブラウザを自動起動せず、認証URLを標準出力に表示する",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=0,
        help="OAuth callback 用 localhost port。0 なら空きポートを自動選択",
    )
    parser.add_argument(
        "--login-hint",
        default=None,
        help="Google 認証画面に渡す login_hint",
    )
    parser.add_argument(
        "--prompt",
        default="select_account",
        help="Google 認証画面の prompt パラメータ (default: select_account)",
    )
    args = parser.parse_args()

    if not CREDS_PATH.exists():
        print(f"エラー: {CREDS_PATH} が見つかりません。", file=sys.stderr)
        print("GCP コンソールから OAuth クライアント JSON をダウンロードして", file=sys.stderr)
        print(f"  {CREDS_PATH}", file=sys.stderr)
        print("として保存してください。", file=sys.stderr)
        sys.exit(1)

    from google_auth_oauthlib.flow import InstalledAppFlow

    flow = InstalledAppFlow.from_client_secrets_file(str(CREDS_PATH), SCOPES)
    auth_kwargs = {"prompt": args.prompt}
    if args.login_hint:
        auth_kwargs["login_hint"] = args.login_hint
    creds = flow.run_local_server(
        port=args.port,
        open_browser=not args.no_browser,
        authorization_prompt_message="認証URLをブラウザで開いてください:\n{url}\n",
        **auth_kwargs,
    )

    TOKEN_PATH.write_text(creds.to_json(), encoding="utf-8")
    print(f"✓ トークンを保存しました: {TOKEN_PATH}", file=sys.stderr)
    print("owlclaw の Calendar source が利用できるようになりました。", file=sys.stderr)


if __name__ == "__main__":
    main()

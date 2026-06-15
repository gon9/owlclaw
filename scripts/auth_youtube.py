#!/usr/bin/env python3
"""
owlclaw: YouTube OAuth 初回認証フロー。

secrets/youtube_oauth.json (GCP の OAuth クライアントシークレット) を使い、
ブラウザ認証を完了して secrets/youtube_token.json を生成する。

スコープは youtube.upload (動画アップロードのみ) を使用。

事前準備:
  1. GCP コンソール → API とサービス → ライブラリ → YouTube Data API v3 を有効化
  2. 認証情報 → 「OAuth 2.0 クライアント ID」を「デスクトップアプリ」で作成
     （Drive/Calendar/Gmail と同一 GCP プロジェクトの同一クライアント ID を流用可能）
  3. JSON をダウンロードして secrets/youtube_oauth.json として保存

使い方:
  uv run python scripts/auth_youtube.py
  → ブラウザが開く → 認証 → secrets/youtube_token.json が生成される
"""

import argparse
import sys
from pathlib import Path

PROJ = Path(__file__).parent.parent
CREDS_PATH = PROJ / "secrets" / "youtube_oauth.json"
TOKEN_PATH = PROJ / "secrets" / "youtube_token.json"
SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


def main() -> None:
    """OAuth フローを実行してトークンを保存する。"""
    parser = argparse.ArgumentParser(description="YouTube OAuth 認証を実行")
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
        print("として保存してください。Drive 用と同じ JSON を流用しても OK。", file=sys.stderr)
        sys.exit(1)

    from google_auth_oauthlib.flow import InstalledAppFlow  # noqa: PLC0415

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
    print("owlclaw の YouTube upload が利用できるようになりました。", file=sys.stderr)


if __name__ == "__main__":
    main()

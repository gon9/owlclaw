#!/usr/bin/env python3
"""
owlclaw: Gmail OAuth 初回認証フロー。

secrets/gmail_oauth.json (GCP の OAuth クライアントシークレット) を使い、
ブラウザ認証を完了して secrets/gmail_token.json を生成する。

事前準備:
  1. GCP コンソール → API とサービス → 認証情報
     → 「OAuth 2.0 クライアント ID」を「デスクトップアプリ」で作成
  2. JSON をダウンロードして secrets/gmail_oauth.json として保存
  3. Gmail API を有効化しておく

使い方:
  uv run python scripts/auth_gmail.py
"""

import sys
from pathlib import Path

PROJ = Path(__file__).parent.parent
CREDS_PATH = PROJ / "secrets" / "gmail_oauth.json"
TOKEN_PATH = PROJ / "secrets" / "gmail_token.json"
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]


def main() -> None:
    """OAuth フローを実行してトークンを保存する。"""
    if not CREDS_PATH.exists():
        print(f"エラー: {CREDS_PATH} が見つかりません。", file=sys.stderr)
        print("GCP コンソールから OAuth クライアント JSON をダウンロードして", file=sys.stderr)
        print(f"  {CREDS_PATH}", file=sys.stderr)
        print("として保存してください。", file=sys.stderr)
        sys.exit(1)

    from google_auth_oauthlib.flow import InstalledAppFlow

    flow = InstalledAppFlow.from_client_secrets_file(str(CREDS_PATH), SCOPES)
    creds = flow.run_local_server(port=0)

    TOKEN_PATH.write_text(creds.to_json(), encoding="utf-8")
    print(f"✓ トークンを保存しました: {TOKEN_PATH}", file=sys.stderr)
    print("owlclaw の Gmail source が利用できるようになりました。", file=sys.stderr)


if __name__ == "__main__":
    main()

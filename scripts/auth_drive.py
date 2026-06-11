#!/usr/bin/env python3
"""
owlclaw: Google Drive OAuth 初回認証フロー。

secrets/drive_oauth.json (GCP の OAuth クライアントシークレット) を使い、
ブラウザ認証を完了して secrets/drive_token.json を生成する。

スコープは drive.file (アプリが作成したファイルのみアクセス可能) を使用。
これにより既存ユーザーファイルへのアクセス権は持たず、最小権限で動画 upload のみ可能。

事前準備:
  1. GCP コンソール → API とサービス → 認証情報
     → 「OAuth 2.0 クライアント ID」を「デスクトップアプリ」で作成
     （Calendar/Gmail と同一 GCP プロジェクトを使用可能）
  2. JSON をダウンロードして secrets/drive_oauth.json として保存
  3. Google Drive API を有効化しておく

使い方:
  uv run python scripts/auth_drive.py
  → ブラウザが開く → 認証 → secrets/drive_token.json が生成される
"""

import argparse
import sys
from pathlib import Path

PROJ = Path(__file__).parent.parent
CREDS_PATH = PROJ / "secrets" / "drive_oauth.json"
TOKEN_PATH = PROJ / "secrets" / "drive_token.json"
SCOPES = ["https://www.googleapis.com/auth/drive.file"]


def main() -> None:
    """OAuth フローを実行してトークンを保存する。"""
    parser = argparse.ArgumentParser(description="Google Drive OAuth 認証を実行")
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="ブラウザを自動起動せず、認証URLを標準出力に表示する",
    )
    args = parser.parse_args()

    if not CREDS_PATH.exists():
        print(f"エラー: {CREDS_PATH} が見つかりません。", file=sys.stderr)
        print("GCP コンソールから OAuth クライアント JSON をダウンロードして", file=sys.stderr)
        print(f"  {CREDS_PATH}", file=sys.stderr)
        print("として保存してください。Calendar 用と同じ JSON を流用しても OK。", file=sys.stderr)
        sys.exit(1)

    from google_auth_oauthlib.flow import InstalledAppFlow

    flow = InstalledAppFlow.from_client_secrets_file(str(CREDS_PATH), SCOPES)
    creds = flow.run_local_server(
        port=0,
        open_browser=not args.no_browser,
        authorization_prompt_message="認証URLをブラウザで開いてください:\n{url}\n",
    )

    TOKEN_PATH.write_text(creds.to_json(), encoding="utf-8")
    print(f"✓ トークンを保存しました: {TOKEN_PATH}", file=sys.stderr)
    print("owlclaw の Drive upload が利用できるようになりました。", file=sys.stderr)


if __name__ == "__main__":
    main()

"""YouTube Data API v3 で動画をアップロードするユーティリティ。

owlclaw の video-digest で生成した MP4 を YouTube にアップロードし、
Google Home から「OK Google, YouTube で owlclaw を再生」で聴取可能にする。

主な API:
    - upload_to_youtube(local_path, title, description, ...) -> dict (id, url)
    - 内部で OAuth トークン (secrets/youtube_token.json) を読み込み、必要なら refresh

依存:
    google-api-python-client, google-auth-oauthlib (pyproject.toml で導入済み)
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJ = Path(__file__).parent.parent
TOKEN_PATH = PROJ / "secrets" / "youtube_token.json"
CREDS_PATH = PROJ / "secrets" / "youtube_oauth.json"
SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


def _build_service():
    """認証済み YouTube API service を返す。"""
    from google.auth.transport.requests import Request  # noqa: PLC0415
    from google.oauth2.credentials import Credentials  # noqa: PLC0415
    from googleapiclient.discovery import build  # noqa: PLC0415

    if not TOKEN_PATH.exists():
        raise RuntimeError(
            f"{TOKEN_PATH} が無い。"
            "先に `uv run python scripts/auth_youtube.py` で認証してください。"
        )

    creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)
    if not creds.valid:
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            TOKEN_PATH.write_text(creds.to_json(), encoding="utf-8")
        else:
            raise RuntimeError(
                "YouTube token が失効。"
                " `uv run python scripts/auth_youtube.py` を再実行してください。"
            )

    return build("youtube", "v3", credentials=creds, cache_discovery=False)


def upload_to_youtube(
    local_path: Path,
    title: str,
    description: str = "",
    tags: list[str] | None = None,
    category_id: str = "25",
    privacy_status: str = "public",
) -> dict:
    """ローカルの MP4 を YouTube にアップロードする。

    Parameters
    ----------
    local_path : Path
        アップロード対象の mp4
    title : str
        動画タイトル (例: "owlclaw AI Digest 2026-06-11")
    description : str
        動画の説明文
    tags : list[str] | None
        タグリスト (デフォルト: owlclaw 関連タグ)
    category_id : str
        YouTube カテゴリ ID (25 = News & Politics)
    privacy_status : str
        公開設定 (public / unlisted / private)

    Returns
    -------
    dict
        {"id": video_id, "url": watch_url}
    """
    from googleapiclient.http import MediaFileUpload  # noqa: PLC0415

    if not local_path.exists():
        raise FileNotFoundError(local_path)

    service = _build_service()

    if tags is None:
        tags = ["owlclaw", "AI", "ニュース", "テック", "SaaS", "AIダイジェスト"]

    body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": tags,
            "categoryId": category_id,
            "defaultLanguage": "ja",
        },
        "status": {
            "privacyStatus": privacy_status,
            "selfDeclaredMadeForKids": False,
        },
    }

    media = MediaFileUpload(
        str(local_path),
        mimetype="video/mp4",
        resumable=True,
    )
    request = service.videos().insert(
        part="snippet,status",
        body=body,
        media_body=media,
    )

    print(f"  YouTube upload 開始: {local_path.name}", file=sys.stderr)
    response = None
    while response is None:
        _, response = request.next_chunk()

    video_id = response["id"]
    url = f"https://www.youtube.com/watch?v={video_id}"
    print(f"  YouTube upload 完了: {url}", file=sys.stderr)
    return {"id": video_id, "url": url}


def main() -> None:
    """CLI: ファイルパスとタイトルを引数に取って upload。"""
    import argparse  # noqa: PLC0415

    parser = argparse.ArgumentParser(description="YouTube に動画を upload")
    parser.add_argument("file", help="upload 対象の MP4 ファイル")
    parser.add_argument("--title", required=True, help="動画タイトル")
    parser.add_argument("--description", default="", help="動画の説明文")
    parser.add_argument(
        "--privacy",
        default="public",
        choices=["public", "unlisted", "private"],
        help="公開設定 (default: public)",
    )
    args = parser.parse_args()

    result = upload_to_youtube(
        Path(args.file),
        title=args.title,
        description=args.description,
        privacy_status=args.privacy,
    )
    print(result["url"])


if __name__ == "__main__":
    main()

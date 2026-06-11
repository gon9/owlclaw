"""Google Drive 上に動画をアップロードして共有 URL を返すユーティリティ。

owlclaw の video-digest など、生成物を remote から閲覧可能にする用途。
スコープは drive.file (アプリが作成したファイルのみ) を使う最小権限実装。

主な API:
    - upload_to_drive(local_path, folder_name) -> dict (id, webViewLink)
    - 内部で OAuth トークン (secrets/drive_token.json) を読み込み、必要なら refresh

依存:
    google-api-python-client, google-auth-oauthlib (pyproject.toml で導入済み)
"""

from __future__ import annotations

import mimetypes
import sys
from pathlib import Path

PROJ = Path(__file__).parent.parent
TOKEN_PATH = PROJ / "secrets" / "drive_token.json"
CREDS_PATH = PROJ / "secrets" / "drive_oauth.json"
SCOPES = ["https://www.googleapis.com/auth/drive.file"]


def _build_service():
    """認証済み Drive API service を返す。"""
    from google.auth.transport.requests import Request  # noqa: PLC0415
    from google.oauth2.credentials import Credentials  # noqa: PLC0415
    from googleapiclient.discovery import build  # noqa: PLC0415

    if not TOKEN_PATH.exists():
        raise RuntimeError(
            f"{TOKEN_PATH} が無い。先に `uv run python scripts/auth_drive.py` で認証してください。"
        )

    creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)
    if not creds.valid:
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            TOKEN_PATH.write_text(creds.to_json(), encoding="utf-8")
        else:
            raise RuntimeError(
                "Drive token が失効。 `uv run python scripts/auth_drive.py` を再実行してください。"
            )

    return build("drive", "v3", credentials=creds, cache_discovery=False)


def _ensure_folder(service, name: str, parent_id: str | None = None) -> str:
    """指定名のフォルダを取得 or 作成して folder ID を返す (idempotent)。

    drive.file スコープの制約で、アプリが作成したフォルダのみ検索対象。
    """
    query_parts = [
        f"name = '{name}'",
        "mimeType = 'application/vnd.google-apps.folder'",
        "trashed = false",
    ]
    if parent_id:
        query_parts.append(f"'{parent_id}' in parents")
    query = " and ".join(query_parts)

    results = service.files().list(q=query, fields="files(id, name)").execute()
    files = results.get("files", [])
    if files:
        return files[0]["id"]

    metadata = {
        "name": name,
        "mimeType": "application/vnd.google-apps.folder",
    }
    if parent_id:
        metadata["parents"] = [parent_id]
    folder = service.files().create(body=metadata, fields="id").execute()
    return folder["id"]


def upload_to_drive(
    local_path: Path,
    folder_path: str = "owlclaw/video-digest",
    share_anyone: bool = True,
) -> dict:
    """ローカルのファイルを Google Drive にアップロードする。

    Parameters
    ----------
    local_path : Path
        アップロード対象の mp4 など
    folder_path : str
        Drive 上の保存先フォルダ。スラッシュ区切りで階層を表現 (例: "owlclaw/video-digest")
    share_anyone : bool
        True なら "リンクを知っている人は閲覧可能" の共有設定を付与する

    Returns
    -------
    dict
        {"id", "webViewLink", "webContentLink"} を含む辞書
    """
    from googleapiclient.http import MediaFileUpload  # noqa: PLC0415

    if not local_path.exists():
        raise FileNotFoundError(local_path)

    service = _build_service()

    # フォルダ階層を作成 (idempotent)
    parent_id: str | None = None
    for segment in folder_path.split("/"):
        if not segment:
            continue
        parent_id = _ensure_folder(service, segment, parent_id)

    # 同名既存ファイルがあれば削除 (再 upload 時の重複回避)
    existing_query = (
        f"name = '{local_path.name}' and "
        f"'{parent_id}' in parents and trashed = false"
    )
    existing = service.files().list(q=existing_query, fields="files(id)").execute()
    for f in existing.get("files", []):
        service.files().delete(fileId=f["id"]).execute()

    mimetype = mimetypes.guess_type(local_path.name)[0] or "application/octet-stream"
    media = MediaFileUpload(
        str(local_path),
        mimetype=mimetype,
        resumable=local_path.stat().st_size > 5 * 1024 * 1024,  # 5MB 超は resumable
    )
    metadata = {
        "name": local_path.name,
        "parents": [parent_id] if parent_id else [],
    }
    file = service.files().create(
        body=metadata,
        media_body=media,
        fields="id, webViewLink, webContentLink",
    ).execute()

    if share_anyone:
        service.permissions().create(
            fileId=file["id"],
            body={"type": "anyone", "role": "reader"},
        ).execute()

    return {
        "id": file["id"],
        "webViewLink": file.get("webViewLink"),
        "webContentLink": file.get("webContentLink"),
    }


def main() -> None:
    """CLI: ファイルパスを引数に取って upload + 共有 URL 出力。"""
    import argparse  # noqa: PLC0415

    parser = argparse.ArgumentParser(description="Google Drive にファイル upload")
    parser.add_argument("file", help="upload 対象ファイル")
    parser.add_argument(
        "--folder",
        default="owlclaw/video-digest",
        help="Drive 上の保存先フォルダ (default: owlclaw/video-digest)",
    )
    parser.add_argument(
        "--no-share",
        action="store_true",
        help="リンク共有を付与しない",
    )
    args = parser.parse_args()

    result = upload_to_drive(
        Path(args.file),
        folder_path=args.folder,
        share_anyone=not args.no_share,
    )
    print(f"id: {result['id']}")
    print(f"webViewLink: {result['webViewLink']}")
    print(f"webContentLink: {result['webContentLink']}")


if __name__ == "__main__":
    sys.exit(main())

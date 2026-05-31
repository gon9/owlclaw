# Google Drive 連携セットアップ

video-digest の mp4 を Google Drive にアップロードして Slack に共有 URL を貼る機能の初期設定。

## アーキテクチャ

```
remote (gon9a-book)
  └─ video-digest task
        └─ tools/upload_drive.py
              └─ drive.file scope (アプリが作成したファイルのみアクセス可)
                    └─ My Drive/owlclaw/video-digest/digest_YYYYMMDD.mp4
                          └─ "リンクを知っている人は閲覧可" 共有設定
                                └─ Slack に webViewLink を投稿
```

スコープ `drive.file` を使うので、**owlclaw が upload したファイル以外は一切見えない**最小権限構成。

## セットアップ手順

### 1. GCP コンソールで Drive API を有効化

Calendar/Gmail と同じ GCP プロジェクトに対して：

1. https://console.cloud.google.com/apis/library/drive.googleapis.com を開く
2. プロジェクトを選択して「有効にする」をクリック

### 2. OAuth クライアント JSON を準備

既に `secrets/calendar_oauth.json` がある場合は **そのまま流用可能**：

```bash
# calendar 用クライアントを drive にもコピー
cp secrets/calendar_oauth.json secrets/drive_oauth.json
```

新規に作る場合：GCP コンソール → 認証情報 → 「OAuth 2.0 クライアント ID」を **デスクトップアプリ** で作成 → JSON ダウンロード → `secrets/drive_oauth.json` として保存。

### 3. ローカルで OAuth 認証 (ブラウザ必須)

remote (SSH) ではブラウザが開けないので、**ローカル Mac で認証** してトークンを生成し、scp で remote にコピーする。

```bash
# ローカルで認証
uv run python scripts/auth_drive.py
# → ブラウザが開く → Google アカウントを選択 → 「許可」
# → secrets/drive_token.json が生成される
```

### 4. Token を remote にコピー

```bash
# secrets/drive_token.json と drive_oauth.json を remote へ
scp secrets/drive_oauth.json gon9a-book:~/workspace/ai-agent/owlclaw/secrets/
scp secrets/drive_token.json gon9a-book:~/workspace/ai-agent/owlclaw/secrets/
```

### 5. 動作確認

```bash
ssh gon9a-book
cd ~/workspace/ai-agent/owlclaw

# 既存の mp4 を Drive にアップロードしてみる
~/.local/bin/uv run python -m tools.upload_drive tmp/video-digest/digest_20260529.mp4

# 出力例:
# id: 1ABC...
# webViewLink: https://drive.google.com/file/d/1ABC.../view?usp=drivesdk
# webContentLink: https://drive.google.com/uc?id=1ABC...&export=download
```

webViewLink をブラウザで開いて再生できれば OK。

## 動作

`tasks/video-digest.yaml` で `drive_upload: true` を有効化済みなので、次回 video-digest 実行時から自動的に：

1. mp4 を生成
2. Drive にアップロード（同名ファイルがあれば上書き）
3. 「リンクを知っている人は閲覧可」を付与
4. Slack 通知に webViewLink を埋め込む

## トラブルシューティング

### `Drive token が失効しました`

`drive_token.json` の refresh token が無効化されている。再認証：

```bash
# ローカルで再実行 → token を remote にコピー
uv run python scripts/auth_drive.py
scp secrets/drive_token.json gon9a-book:~/workspace/ai-agent/owlclaw/secrets/
```

### `insufficient_scope` エラー

`drive.file` スコープしか付いていないので **既存の Drive ファイルは触れない**。
それは仕様 (最小権限)。新規 upload + 自分が upload したファイルの操作はできる。

### 同名ファイルが重複する

`upload_drive.py` 内で同名既存ファイルは削除してから upload しているので
通常は重複しない。手動 upload や別ツール経由で作ったファイルがあると
そちらが残る場合あり (drive.file スコープでは検索不可なため)。

### Drive 容量

mp4 は 1 本 ~2MB 程度。`retention_days: 7` でローカルは自動削除されるが
**Drive 側は自動削除されない**ので、必要に応じて Drive 上のフォルダを定期掃除する。
将来的に `tools/upload_drive.py` に古いファイル削除機能を追加することも可能。

## セキュリティ注意

- `secrets/drive_token.json` は **refresh token を含むので秘匿** (.gitignore 済み)
- `secrets/drive_oauth.json` も client secret を含むので秘匿
- "リンクを知っている人は閲覧可" 設定なので URL を漏らせばだれでも見られる
  → 機密情報を含む動画は作らない、または `share_anyone=False` で運用する

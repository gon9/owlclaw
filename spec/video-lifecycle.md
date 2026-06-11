# 動画生成成果物のライフサイクル仕様

本仕様は `video-digest` タスクで生成される動画（および中間生成物）のライフサイクルを定義し、実装がこのライフサイクルを必ず満たすことを目的とする。

## 対象

- タスク: `tasks/video-digest.yaml`
- オーケストレーター: `scripts/orchestrator.py` (`output.type == "video"`)
- スライド生成: `scripts/render_slides.py`
- 音声生成: `scripts/render_audio.py`
- 動画合成: `scripts/compose_video.py`
- Drive アップロード: `tools/upload_drive.py`

## ディレクトリと成果物

`video-digest` の作業ディレクトリは `tmp/video-digest/` とする。

- `tmp/video-digest/slides.json`
- `tmp/video-digest/slides/*.png`
- `tmp/video-digest/slides/*.html`
- `tmp/video-digest/slides/*.codex*.log`
- `tmp/video-digest/audio/*.wav`
- `tmp/video-digest/_segments/*.mp4`
- `tmp/video-digest/digest_YYYYMMDD.mp4`
- `tmp/video-digest/slack_video.txt`（Slack 通知用の一時ファイル）

## ライフサイクル（フェーズ）

1. 生成
   - 入力: `slides.json`
   - 出力: `slides/*.png`

2. 検証
   - `slides.json` のスキーマ検証
   - `slides/*.png` の存在・サイズ検証

3. 音声生成
   - 出力: `audio/*.wav`

4. 動画合成
   - 出力: `digest_YYYYMMDD.mp4`
   - `_segments/` は合成のための中間ディレクトリ

5. 配信
   - Drive アップロード（オプション）
   - Slack 通知（オプション）

6. 保持・削除
   - `retention_days` を超えた成果物・中間ファイルはタスク実行時に削除される

## ルール

### 同日付は上書き

- 出力 MP4 は `digest_YYYYMMDD.mp4` の固定名とし、同日付の再実行は上書きを許可する。
- Drive アップロードは同名ファイルがある場合、削除して再アップロードする。

### リトライ

- 以下の処理は例外発生時に最大3回のリトライを行う。
  - `render_slides.py`
  - `render_audio.py`
  - `compose_video.py`
  - Drive アップロード

- リトライは指数バックオフで待機する（例: 5秒, 10秒, 20秒）。

環境変数:

- `OWLCLAW_VIDEO_RETRY_MAX_ATTEMPTS`（既定: 3）
- `OWLCLAW_VIDEO_RETRY_BASE_DELAY_SECONDS`（既定: 5）

### 中間ファイルも同一ライフサイクル

- `_segments/` は合成成功後に削除する。
- `slides/` および `audio/` のファイルは、`retention_days` を超えたものをタスク実行時に削除する。

### retention_days

- `tasks/video-digest.yaml` の `outputs[].retention_days` を採用する（既定: 7）。
- `retention_days <= 0` の場合は削除を行わない。

### エラー時の挙動

- 生成や合成に失敗した場合は例外として扱い、当該タスクの実行は失敗とする。
- Drive アップロードに失敗した場合は警告を出し、Slack 通知はローカルファイルパスでフォールバックする。

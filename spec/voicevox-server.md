# VOICEVOX ヘッドレスサーバー運用ガイド

owlclaw を SSH 先 (例: `gon9a-book` = Intel Mac, macOS 12.7.6) で運用するための、
**GUI なし・バックグラウンド常駐** の VOICEVOX セットアップ手順。

## 前提

- VOICEVOX 本体（GUI アプリ）には HTTP API サーバーが組み込まれているが、起動するとウィンドウが立ち上がる
- **VOICEVOX Engine** という GUI なしの公式 HTTP API サーバ単体配布版がある
- これを launchd で常駐化すれば、ヘッドレス + バックグラウンド + 自動起動が達成できる

## 配布形態の選択

| 方法 | Mac (Intel) 適性 | 備考 |
|---|---|---|
| **VOICEVOX Engine 直バイナリ** | ◎ 推奨 | GitHub Releases から zip 配布、依存なし |
| Docker (`voicevox/voicevox_engine:cpu-latest`) | △ | Docker Desktop 必要、Mac は重い |
| GUI 版を `--no-gui` で起動 | × | 公式は非対応 |

→ **直バイナリ + launchd** が最もシンプルかつ軽量。

## セットアップ手順（remote: gon9a-book）

### 1. ダウンロード

GitHub Releases ページから macOS x64 (Intel) 用エンジンを取得：

```bash
ssh gon9a-book

# 作業ディレクトリ
mkdir -p ~/voicevox && cd ~/voicevox

# 最新版確認: https://github.com/VOICEVOX/voicevox_engine/releases
# 例: v0.24.x の macOS x64 CPU 版
LATEST_TAG=$(curl -s https://api.github.com/repos/VOICEVOX/voicevox_engine/releases/latest | grep tag_name | cut -d '"' -f 4)
echo "Latest: $LATEST_TAG"

# CPU x64 zip をダウンロード（macOS は分割ダウンロードが必要）
# 詳細手順は releases ページを参照
```

> **注**: VOICEVOX Engine の macOS リリースは `7z.001`, `7z.002`... のように分割されることがある。
> ダウンロード後 `7zz x voicevox_engine.7z.001` で結合・展開。
> `7zz` は `brew install sevenzip` で導入。

### 2. 動作確認（フォアグラウンド）

```bash
cd ~/voicevox/voicevox_engine_macos_x64
./run --host 127.0.0.1 --port 50021
# 別ターミナルから
curl http://127.0.0.1:50021/version
```

バージョン文字列が返れば OK。Ctrl+C で停止。

### 3. launchd で常駐化

`~/Library/LaunchAgents/com.voicevox.engine.plist` を作成：

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.voicevox.engine</string>

    <key>ProgramArguments</key>
    <array>
        <string>/Users/gon9a/voicevox/voicevox_engine_macos_x64/run</string>
        <string>--host</string>
        <string>127.0.0.1</string>
        <string>--port</string>
        <string>50021</string>
    </array>

    <key>WorkingDirectory</key>
    <string>/Users/gon9a/voicevox/voicevox_engine_macos_x64</string>

    <key>RunAtLoad</key>
    <true/>

    <key>KeepAlive</key>
    <true/>

    <key>StandardOutPath</key>
    <string>/Users/gon9a/voicevox/engine.out.log</string>

    <key>StandardErrorPath</key>
    <string>/Users/gon9a/voicevox/engine.err.log</string>
</dict>
</plist>
```

ロード：

```bash
launchctl load -w ~/Library/LaunchAgents/com.voicevox.engine.plist
launchctl list | grep voicevox     # 確認
sleep 30                            # 起動待ち
curl http://127.0.0.1:50021/version # 動作確認
```

アンロード（停止）:
```bash
launchctl unload -w ~/Library/LaunchAgents/com.voicevox.engine.plist
```

### 4. owlclaw 側の設定

`render_audio.py` は環境変数 `VOICEVOX_URL` で接続先を上書きできる。
remote 上で実行する場合は既定値（`http://127.0.0.1:50021`）でそのまま動く。

別ホストの VOICEVOX を使う場合は `.env` に追加：

```bash
# .env
VOICEVOX_URL=http://127.0.0.1:50021   # 既定でも OK、明示しても可
```

## トラブルシューティング

### Gatekeeper で起動拒否される

初回起動時に「開発元を確認できないため開けません」が出たら：
1. Finder で `run` バイナリを右クリック → 開く → 警告を承認
2. または `xattr -d com.apple.quarantine ~/voicevox/voicevox_engine_macos_x64/run`

### launchd でエラー終了する

`~/voicevox/engine.err.log` を確認。よくある原因：
- 実行権限なし → `chmod +x run`
- ポート既使用 → `lsof -i :50021` で確認、`--port 50022` 等に変更

### macOS 12.7.6 サポート

VOICEVOX Engine v0.24+ は macOS 12 で動作する。最新版で動かない場合は v0.22 系まで戻す。

## 動画パイプラインとの連携

```
┌─ remote: gon9a-book ──────────────────────┐
│  launchd: VOICEVOX Engine (常駐)           │
│      ↓ http://127.0.0.1:50021              │
│  owlclaw: video-digest タスク              │
│      ↓ render_audio.py                     │
│      ↓ render_slides.py                    │
│      ↓ compose_video.py                    │
│  tmp/video-digest/digest_YYYYMMDD.mp4      │
└────────────────────────────────────────────┘
```

video-digest を Claude Code スケジューラ or launchd で 7:30 JST に起動すれば、
完全自動で日次動画が生成される。

# Project Rules — owlclaw

AIニュースダイジェストパイプライン。RSSフェッチ → LLMキュレーション → Obsidian保存 + Slack通知。

## ⚠️ 実行環境（最重要・調査前に必ず確認）

**スケジュールタスク（launchd plist `com.gon9a.owlclaw-*`）の実運用は SSH 先ホスト `gon9a-book` 上で動いている。** 開発に使うこのローカル Mac には plist が導入されておらず、`tmp/` の中間ファイルも古い。

- 「タスクが動いていない / 通知が来ない」系の調査では、ローカルの `launchctl list` や `~/Library/LaunchAgents/`・`tmp/` を見ても**実態は分からない**。`ssh gon9a-book` 上の launchd・ログ（`tmp/launchd-<task-id>.log`）を確認すること。
- ローカルは config / prompt / コードの編集とテスト用。デプロイは `gon9a-book` への反映が必要。
- 朝7:00 枠（`departure-time`）はレート制限で実行されないことがある。翌日リマインドは夜20:00 の `visit-briefing` が信頼できる枠。

## コマンド

```bash
# フルパイプライン実行（スケジューラー用）
bash scripts/run_full.sh

# 任意タスクの手動実行
bash scripts/oneshot.sh <task-id>
bash scripts/oneshot.sh daily-digest
bash scripts/oneshot.sh blog-watch
```

## ディレクトリ構造

```
config/sources.yaml     # RSSソース定義
prompts/                # Claude向けプロンプト
scripts/                # パイプラインスクリプト
secrets/                # Slack Webhook URL (gitignore済み)
tmp/                    # 中間ファイル (gitignore済み)
```

## 境界 (Boundaries)

### Always
- シェルスクリプトは `set -euo pipefail` を先頭に記述
- Python は型ヒントを使用

### Never
- `secrets/` をGitにコミット
- `tmp/` をGitにコミット

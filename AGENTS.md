# Project Rules — owlclaw

AIニュースダイジェストパイプライン。RSSフェッチ → LLMキュレーション → Obsidian保存 + Slack通知。

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

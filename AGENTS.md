# Project Rules — owlclaw

AIニュースダイジェストパイプライン。RSSフェッチ → LLMキュレーション → Obsidian保存 + Slack通知。

## コマンド

```bash
# フルパイプライン実行
bash scripts/run_full.sh

# 個別ステップ
uv run python scripts/fetch_rss.py          # RSSフェッチ
bash scripts/run.sh post YYYY-MM-DD         # Obsidian保存 + Slack通知
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

# owlclaw vision — FDE+AI情報Hub確立

最終更新: 2026-05-06

---

## 1. ゴール

**FDE職+AI専門家として、社内外で「AI情報Hub」と認知される存在になる。**

RSSを読むだけでなく、発信までループを閉じることで価値を生む。

| 発信チャネル | 目的 |
|---|---|
| 社内Slack | 週次/日次でAIトレンドまとめを流し「AIのことはあの人」と認知 |
| 顧客提案 | 最新事例・モデル比較・ROI議論を即引き出せる知識DBを持つ |
| 対外発信 | Zenn/X/ブログで自分の意見を発信、社外でもAI専門家として認知 |

---

## 2. 情報レイヤー設計

| レイヤー | 内容 | 主なソース | 優先度 |
|---|---|---|---|
| L1: 速報・トレンド | 業界ニュース | TechCrunch, HN, TLDR AI | 高 |
| L2: 技術深堀り | 実装・アーキテクチャ | Pragmatic Engineer, Latent Space, arXiv | 高 |
| L3: ビジネス・戦略 | 投資・組織・FDE事例 | a16z, SaaStr, Palantir Blog | 高 |
| L4: 海外モデル動向 | LLM各社の動向 | OpenAI/Anthropic/Google Blog, HuggingFace | 高 |
| L5: 音声・対談 | Podcast・講演 | Latent Space Podcast, No Priors, Lex Fridman | 中 |
| L6: 論文 | 研究最前線 | arXiv cs.AI/cs.CL | 中 |

---

## 3. アーキテクチャ（目指す姿）

```
Multi-Source Ingest
  ├── RSS (既存)
  ├── YouTube/Podcast  ← tools/youtube.py  [youtube-transcript-api]
  ├── arXiv論文        ← tools/arxiv.py    [langchain-community]
  └── X(Twitter)       ← 将来: RSSHub経由
           │
           ▼
    重要度スコアリング  ← tools/score.py    [Claude CLI --print]
           │
    Top N 選出
           │
    要約生成          ← tools/summarize.py [Claude CLI --print + LangChain Splitter]
           │
    ┌──────┴───────┐
    ▼              ▼
 知識DB蓄積      Slack/Obsidian配信
(embedding Phase 3)  (既存パイプライン)
```

### LLM戦略（ハイブリッド）

| 用途 | 手段 | コスト |
|---|---|---|
| 要約・スコアリング・キュレーション | `claude --print` (Claude CLI) | Pro/Max定額 |
| embedding・ベクトル検索 | OpenAI API `text-embedding-3-small` | 従量（Phase 3） |
| インタラクティブ作業 | Windsurf Cascade | Windsurf予算 |

---

## 4. toolsモジュール仕様

### 設計原則

- **独立実行可能**: `python -m tools.youtube <url>` のようにCLIとして動く
- **ライブラリとしてimport可能**: orchestratorから `from tools.youtube import fetch_transcript_from_url` で使える
- **疎結合**: 各ツールはI/O以外に依存しない。パイプラインへの組み込みは後工程で行う

---

### tools/youtube.py

**目的**: YouTube動画から字幕テキストを取得する

```
入力: YouTube URL (str)
出力: TranscriptResult (TypedDict)
  - video_id: str
  - url: str
  - text: str          # 全字幕を結合したフルテキスト
  - segments: list     # [{text, start, duration}, ...]
  - language: str      # 実際に取得できた言語コード
  - char_count: int
```

**ライブラリ**: `youtube-transcript-api`

**CLI**:
```bash
python -m tools.youtube https://www.youtube.com/watch?v=<id>
python -m tools.youtube <url> --lang en ja --json
```

**考慮事項**:
- 字幕なし動画 → `TranscriptNotAvailable` を適切に補足
- 自動生成字幕 / 手動字幕を両方試みる
- 言語優先順位: CLI引数 → デフォルト `["en", "ja"]`

---

### tools/arxiv.py

**目的**: arXivから論文メタデータ+Abstractを取得する

```
入力: クエリ文字列 or arXiv ID (str)
出力: list[PaperResult (TypedDict)]
  - paper_id: str        # 例: "2401.00001"
  - title: str
  - authors: list[str]
  - published: str       # ISO日付
  - abstract: str
  - url: str             # https://arxiv.org/abs/<id>
  - pdf_url: str
  - categories: list[str]
```

**ライブラリ**: `langchain-community` (`ArxivLoader`) + `arxiv`

**CLI**:
```bash
python -m tools.arxiv "LLM agent reasoning" --max-results 5
python -m tools.arxiv --paper-id 2312.00001
python -m tools.arxiv "GPT" --categories cs.AI cs.CL --days 7
```

**考慮事項**:
- デフォルトカテゴリ: `cs.AI`, `cs.CL`, `cs.LG`
- `--days N` オプションで直近N日に絞り込み
- APIレート制限: 連続リクエスト間に0.5秒スリープ

---

### tools/summarize.py

**目的**: 長文テキストをClaude CLIで要約する

```
入力:
  text: str          # 要約対象テキスト
  context: str       # 要約の文脈・視点 (オプション)
  max_tokens: int    # チャンクサイズ上限 (デフォルト: 8000文字)

出力: str (要約テキスト)
```

**ライブラリ**: `langchain-text-splitters` (RecursiveCharacterTextSplitter) + `claude --print`

**処理フロー**:
1. テキストが`max_tokens`以内 → Claude CLIに直接渡して要約
2. テキストが`max_tokens`超 → LangChainで分割 → 各チャンクをClaude CLIで要約 → 最終統合

**CLI**:
```bash
python -m tools.summarize < transcript.txt
cat transcript.txt | python -m tools.summarize --context "FDE視点で要点を3行で"
```

---

### tools/score.py

**目的**: コンテンツのFDE+AI専門家視点での重要度を1-10でスコアリングする

```
入力: ContentItem (TypedDict)
  - title: str
  - text: str          # Abstract or Excerpt
  - url: str           # オプション
  - source: str        # オプション

出力: ScoreResult (TypedDict)
  - score: int          # 1-10
  - reason: str         # スコアの根拠（1文）
  - tags: list[str]     # 関連タグ (例: ["LLM", "FDE", "海外モデル"])
  - priority: str       # "high" | "medium" | "low"
```

**ライブラリ**: `claude --print` (JSON出力プロンプト)

**スコアリング基準**（プロンプトに埋め込む）:
- 10: FDE業務への直接的インパクト or 重大モデル発表
- 7-9: AI専門家として知っておくべき重要トレンド
- 4-6: 参考になるが即時アクション不要
- 1-3: ノイズ・既報の焼き直し

**CLI**:
```bash
echo '{"title": "GPT-5 released", "text": "..."}' | python -m tools.score
python -m tools.score --batch items.json
```

---

## 5. ロードマップ

### Phase A: ツール基盤（本フェーズ）

- [x] spec/vision.md 作成
- [ ] tools/youtube.py
- [ ] tools/arxiv.py
- [ ] tools/summarize.py
- [ ] tools/score.py
- [ ] 各ツールのユニットテスト

### Phase B: パイプライン組み込み

- [ ] `score.py` を既存 `daily-digest` パイプラインに組み込み（Top N選出）
- [ ] `youtube.py` + `summarize.py` をPodcast取り込みとして `sources/podcast.py` に実装
- [ ] `arxiv.py` を `sources/arxiv.py` として組み込み
- [ ] `tasks/podcast-digest.yaml` 新規作成

### Phase C: 知識DB化（ベクトル検索）

- [ ] `tools/embed.py` (OpenAI `text-embedding-3-small`)
- [ ] ベクトルストア選定（ChromaDB or sqlite-vec）
- [ ] セマンティック検索CLI
- [ ] MCPサーバー化 (Claude Desktopから直接クエリ)

### Phase D: X(Twitter)ソース

- [ ] RSSHub経由 or Nitter経由でXのフィード取得
- [ ] フォローリスト設計（AIリサーチャー30人）

---

## 6. 環境変数

```bash
# .env (gitignore済み)
OBSIDIAN_VAULT=/path/to/vault    # 既存
OPENAI_API_KEY=sk-...            # Phase C から使用
```

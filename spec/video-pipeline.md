# 動画ダイジェストパイプライン設計

owlclaw の出力（Markdown 中心）に加えて **ニュース番組風の MP4 動画** を生成するパイプライン。

## ゴール

- 1日の AI ダイジェストを **3〜5分の MP4 動画** にする
- 720p、ニュース番組風スライドショー
- **完全ローカル + 既存サブスク内** で完結（追加API課金 ¥0）
- 個人アーカイブ用途（Obsidian/iCloud に保存）

## PoC 結果サマリー（2026-05-28）

PoC 完了。`scripts/poc_video.sh` で以下が動作することを確認：

| 要素 | ツール | 結果 |
|---|---|---|
| 画像生成 | Codex CLI `$imagegen` (gpt-image-2) | ◎ 高品質、24-50k tokens/枚 |
| 音声合成 | VOICEVOX (青山龍星 id=13) | ◎ ニュース調、即時生成、無料 |
| 動画合成 | ffmpeg (libx264 + AAC) | ◎ 1280x720 mp4、ファイルサイズ適正 |

詳細は PoC 期間の `tmp/poc/findings.md` 参照（gitignored）。

## アーキテクチャ

### スライド種別とレンダラ（ハイブリッド方式）

```
slides.json (single source of truth)
  ├─ slide.type == "hero"      → gpt-image-2 (Codex CLI)
  ├─ slide.type == "concept"   → gpt-image-2
  ├─ slide.type == "data"      → HTML テンプレート + Puppeteer
  └─ slide.type == "summary"   → HTML テンプレート + Puppeteer
```

| 種別 | レンダラ | 用途 | 理由 |
|---|---|---|---|
| `hero` | gpt-image-2 | オープニング/クロージング | 装飾的、再利用可能 |
| `concept` | gpt-image-2 | 概念図解、メタファー | 抽象表現が得意 |
| `data` | HTML/Puppeteer | インフォグラフィック、KPIサマリー | 数字100%正確、再現性◎ |
| `summary` | HTML/Puppeteer | アジェンダ、インデックス | テキスト主体、再現性◎ |

### パイプライン全体フロー

```
[RSS sources fetch]
       ↓
[events.md]
       ↓
[Claude --print (prompts/video-script.md)]
       ↓
[slides.json + narration.txt]   ← Claude が生成する中間表現
       ↓
[render_slides.py] ─→ [tmp/video-digest/slides/seg{N}.png]
       ↓
[render_audio.py (VOICEVOX)] ─→ [tmp/video-digest/audio/seg{N}.wav]
       ↓
[compose_video.py (ffmpeg)] ─→ [tmp/video-digest/digest.mp4]
       ↓
[Output dispatch] ─→ Obsidian (パス通知 only) + Slack
```

## slides.json スキーマ

`tools/slide_schema.py` に Pydantic で定義する。

```jsonc
{
  "title": "OWLCLAW NEWS — 2026-05-28",
  "date": "2026-05-28",
  "slides": [
    {
      "id": "seg1",
      "type": "hero",
      "image_prompt": "A modern AI newsroom scene...",
      "narration": "おはようございます。アウルクロウ NEWS です..."
    },
    {
      "id": "seg2",
      "type": "data",
      "template": "kpi_three_col",
      "data": {
        "headline": "OpenRouter $1.3B 調達",
        "subtitle": "1年でバリュエーション2倍超",
        "columns": [
          {"label": "資金調達", "value": "$113M", "caption": "CapitalG主導"},
          {"label": "バリュエーション", "value": "$1.3B", "caption": "1年で2倍超"},
          {"label": "Usage成長", "value": "5倍", "caption": "6ヶ月で達成"}
        ],
        "insights": [
          "単一LLMベンダー依存はリスク化",
          "ルーティング層自体が独立した競争領域に"
        ],
        "source": "TechCrunch (2026-05-26)"
      },
      "narration": "続いてのニュースです。OpenRouter は..."
    }
  ]
}
```

## ディレクトリ構成（追加分）

```
owlclaw/
├── spec/video-pipeline.md          # 本ドキュメント
├── tasks/video-digest.yaml         # NEW: 動画ダイジェストタスク
├── prompts/video-script.md         # NEW: digest → slides.json 変換指示
├── scripts/
│   ├── poc_video.sh                # PoC 残置 (参考実装)
│   ├── render_slides.py            # NEW: ディスパッチャ (image/html)
│   ├── render_audio.py             # NEW: VOICEVOX 音声生成
│   ├── compose_video.py            # NEW: ffmpeg 合成
│   └── render_html.js              # NEW: Puppeteer ラッパー
├── templates/                      # NEW: Jinja2 + HTML テンプレ
│   ├── kpi_three_col.html.j2
│   └── summary.html.j2
└── tools/
    └── slide_schema.py             # NEW: Pydantic スキーマ
```

## orchestrator.py への変更

`outputs:` に `type: video` を追加対応：

```yaml
outputs:
  - type: video
    output_dir: tmp/video-digest
    obsidian_subdir: owlclaw/video  # Google Drive同期対象のVaultへmp4をコピー
    slack_notify: true
```

`_dispatch_outputs` で `video` タイプを検知し、`render_slides.py` → `render_audio.py` → `compose_video.py` を順次呼ぶ。

## MVP スコープ

**Phase 1 (本実装): 最小動作する動画パイプライン**

- ✅ 1タスク (`video-digest`) 動作
- ✅ スライド数 3〜5枚（hero 1 + data 2-3 + summary 1）
- ✅ 音声: 単一スピーカー (青山龍星 id=13)
- ✅ 動画: 1280x720, mp4, ローカル保存
- ✅ Slack に MP4 のローカルパス通知

**Phase 2 (後回し)**

- pptx 出力（pptxgenjs 経由）
- 複数スピーカー切り替え
- BGM、効果音
- 下部テロップ overlay
- 章タイトルカード、トランジション

## ベストプラクティス（PoC からの学び）

### gpt-image-2 プロンプト

- **抽象概念にはメタファーを明示指定**（"単一→複数" → "天秤", "リスク" → "ゲージ"）
- **busy/content-rich/dense と明言**（"clean" は簡素化されすぎる）
- **要素を6-8個並べる**（タイトル/サブ/左右図/表/示唆/出典）
- **ハンドドローン スタイル指定**で視覚的統一感

### HTML/Puppeteer

- **Hiragino Sans / Yu Gothic** 等システムフォントで日本語安定
- **deviceScaleFactor: 2** でレンダリング、出力時に1280x720に圧縮
- **ニュース本文は3ノードのインフォグラフィックを既定**にして、左から右へ「起点 → 変化 → 意味」を読める構成にする
- **Chart.js / Lucide アイコン**は将来導入（MVP では emoji + 簡易 SVG）

### VOICEVOX

- 起動から API 利用可能まで **30〜60秒** かかる（健康チェックループ必須）
- 初回 macOS Gatekeeper 警告 → 右クリック「開く」で回避
- 推奨スピーカー: **青山龍星 (id=13)** ニュース調に最適

### ffmpeg

- 静止画 + WAV → mp4 は `-loop 1 -i img -i wav -shortest` で完結
- 複数セグメント結合は **concat demuxer** が安全（再エンコード不要なら `-c copy`）
- `Too many bits ... clamping to max` 警告は無害

## トークン消費見積もり

| 構成 | gpt-image-2 枚数 | 推定トークン |
|---|---|---|
| MVP (5スライド: hero1 + data3 + summary1) | 2枚 | 約60-100k tokens |
| フル版 (10スライド: hero1 + concept2 + data6 + summary1) | 3枚 | 約100-150k tokens |

ChatGPT Plus 月次クォータ内で **日次実行可能**な水準。

## 失敗時の挙動

- VOICEVOX 未起動 → エラー終了 + Slack 通知
- Codex CLI クォータ超過 → 当該スライドだけ HTML フォールバックで継続
- ffmpeg 失敗 → スライド単位 mp4 だけ残してエラー報告

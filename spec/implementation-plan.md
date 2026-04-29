# owlclaw 自立稼働化 実装計画書 (v2)

最終更新: 2026-04-23
作成: Devin / 依頼: Atsushi
対象 repo: gon9/owlclaw (Python 3.12 + uv + Bash + Claude Code CLI)
対象ユースケース: `usecases.md` v2 の UC1〜UC6

> **v1 からの変更**: 想定基盤を openclaw/openclaw（公開 OSS）から **gon9/owlclaw** に修正。owlclaw の現行構造を起点に「何を足すか」を再設計。

---

## 1. owlclaw の現状（出発点）

```
config/sources.yaml          ← RSS source 定義 + digest 設定
prompts/
  daily_digest.md            ← Claude へのキュレーション指示
  claude_task.md             ← run_full.sh から渡すタスク指示
scripts/
  fetch_rss.py               ← RSS → tmp/digest_input.md
  run.sh                     ← pre/post サブコマンド
  run_full.sh                ← フルパイプライン (1日1回)
  write_obsidian.sh          ← Obsidian へ保存
  slack_notify.sh            ← Slack Webhook 送信
secrets/slack_webhook.txt
tmp/                         ← 実行中ファイル
```

**長所** (これを壊さない):
- 単機能で動いていて、Bash + Python + Claude CLI の組合せが軽い
- Claude Code CLI を LLM ドライバとして使う割り切りが正しい（自前の agent loop を書かない）
- Obsidian + Slack の出力経路がシンプル
- 設定が YAML 1 枚で見通しが効く
- uv / ruff の規律あり

**現状の限界** (UC を支えるため拡張が必要):
- Task は 1 種類（daily-digest）のみ。複数 Task の並走概念がない
- Source は RSS 1 種類のみ
- 永続 state なし（送信済み記事 ID、累計、通知済み予定など）
- Schedule は外部依存（Claude Code スケジューラ entry 1 行）。多段 / 動的登録なし
- プロファイル（誕生日・住所・予算など）の構造化なし

---

## 2. 目指すアーキテクチャ

```
┌─────────────────────────────────────────────────────────────┐
│ profile.yaml                                                │
│   ユーザー固有データ (誕生日, 住所, 月予算, アクティブ時間)  │
└──────────────────────────┬──────────────────────────────────┘
                           │ 読み込み
                           ▼
┌─────────────────────────────────────────────────────────────┐
│ tasks/<task-id>.yaml         ← Task = 1 個の自律プログラム  │
│   id, schedule, sources, prompt, outputs,                   │
│   state_namespace, standing_order_md_path                   │
└──────────────────────────┬──────────────────────────────────┘
                           │ orchestrator.py が dispatch
                           ▼
┌─────────────────────────────────────────────────────────────┐
│ Source plugins (sources/<type>.py)                          │
│   rss.py (既存) / gmail.py / calendar.py / webhook.py       │
│   → 統一フォーマット (events.md) を tmp/<task>/ に出力      │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│ Claude Code CLI 実行                                        │
│   - prompts/<task-id>.md + 共通 standing-order.md          │
│   - state: state/<namespace>.json (Read 可)                │
│   - output: tmp/<task>/result.md, slack.txt                │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│ Output dispatchers (outputs/<type>.sh)                      │
│   slack_notify.sh (既存) / write_obsidian.sh (既存)         │
│   state_writer.py (新規, 累計やフラグを更新)                │
└─────────────────────────────────────────────────────────────┘
```

主な追加要素:
1. `tasks/` ディレクトリ — 1 タスク 1 ファイルの YAML 定義
2. `sources/` モジュール — type ごとの fetcher
3. `state/` ディレクトリ — JSON 永続化（namespace 分離）
4. `profile.yaml` — ユーザー個人情報の構造化
5. `prompts/standing-order.md` — 全タスク共通の上位指示
6. `orchestrator.py` — task 1 個を pipeline 走らせる統一エントリ

---

## 3. 設計原則

1. **既存パイプを壊さない**: 現行の `run_full.sh` は `tasks/daily-digest.yaml` 経由で動くようにマイグレーションする（同じ動作を保証）
2. **Stack 中立にしない（owlclaw に揃える）**: Python 3.12 + Bash + Claude Code CLI を貫く。フレームワーク追加は最小限
3. **段階的移行**: 各 Phase で価値を出し、ロールバック可能
4. **可逆**: ファイルベース永続化（YAML/MD/JSON）のみ。SQLite は Phase 2 で必要になれば検討
5. **失敗してもうるさくない**: 通知ゼロが正常状態。エラーは 1 日 1 回ダイジェスト
6. **Claude Code CLI 任せ**: LLM 推論部分は CLI に丸投げ、Python は前後処理に徹する

---

## 4. フェーズ計画

### Phase 0: 環境棚卸しと前提整理（1〜2 時間, コード変更 0）

**作業**:
- `secrets/` の Webhook URL 確認
- Claude Code CLI のスケジューラ機構を確認（mac の launchd / Claude Code 内部スケジューラのどちら?）
- Obsidian vault のパス確認、書き込み権限テスト
- 現行 `run_full.sh` を 1 回手動実行して動作再現
- 必要な追加 API 鍵を整理
  - Google API: Gmail / Calendar 用 OAuth クライアント
  - （オプション）Google Maps Directions API 鍵（UC1 用）

**成果物**:
- 棚卸しメモ（このプランの "実環境ノート" として個別管理）
- 現行動作の動画 / ログ（後の比較用）

**完了判定**:
- `bash scripts/run_full.sh` が今日の Slack 通知 + Obsidian ファイルを正しく生成
- 必要な API 鍵が `secrets/` に揃っている（コミットしない）

---

### Phase 1: 基盤拡張 — Task / Source / State 抽象化（2〜4 日）

**目的**: 既存の単一パイプラインを「Task 抽象」に乗せ替える。1 個の Task（既存 daily-digest）が新基盤で動くまでがゴール。後続の Phase で Task を増やすだけで UC を実装できる状態を作る。

**追加 / 変更ファイル**:

```
config/profile.yaml             ← 新規
tasks/
  daily-digest.yaml             ← 新規 (既存動作の YAML 化)
sources/
  __init__.py                   ← 新規
  base.py                       ← 新規 (Source プロトコル定義)
  rss.py                        ← 既存 fetch_rss.py を移植
state/
  .gitkeep                      ← state JSON 置き場 (gitignore)
prompts/
  standing-order.md             ← 新規 (全タスク共通の上位指示)
  daily-digest.md               ← 既存 daily_digest.md をリネーム
scripts/
  orchestrator.py               ← 新規 (タスク1個を pipeline 実行)
  state.py                      ← 新規 (state get/set helper)
  run_task.sh                   ← 新規 (orchestrator.py のラッパ)
  run_full.sh                   ← 既存維持 (orchestrator.py を呼ぶラッパに薄く)
```

**Task YAML スキーマ案**（最小）:

```yaml
# tasks/daily-digest.yaml
id: daily-digest
description: AI ニュース日次ダイジェスト
schedule:
  type: cron
  expr: "0 9 * * *"           # 毎朝 9:00 (Phase 1 では参考情報。実起動は外部 cron)
sources:
  - type: rss
    config_ref: config/sources.yaml   # 既存 yaml を参照
prompt:
  task_md: prompts/daily-digest.md
state:
  namespace: daily-digest
outputs:
  - type: obsidian
    subdir: owlclaw/daily
  - type: slack
```

**orchestrator.py 擬似コード**:

```python
def run(task_id: str):
    task = load_task(f"tasks/{task_id}.yaml")
    profile = load_yaml("config/profile.yaml")

    # 1) sources を順に fetch して events.md にまとめる
    events_md = ""
    for s in task["sources"]:
        events_md += dispatch_source(s, namespace=task["state"]["namespace"])

    # 2) state ロード (Claude が Read で見られるように tmp に置く)
    state = state_load(task["state"]["namespace"])
    write(f"tmp/{task_id}/events.md", events_md)
    write(f"tmp/{task_id}/state.json", json.dumps(state))
    write(f"tmp/{task_id}/profile.yaml", yaml.dump(profile))

    # 3) Claude Code CLI 起動 (prompt + 入力ファイル参照)
    invoke_claude(
        task_md=task["prompt"]["task_md"],
        standing_md="prompts/standing-order.md",
        cwd=f"tmp/{task_id}",
        allowed_tools="Read,Write",
    )

    # 4) outputs を dispatch
    for o in task["outputs"]:
        dispatch_output(o, task_dir=f"tmp/{task_id}")

    # 5) state を更新 (Claude が出力した state.next.json があればマージ)
    state_save(task["state"]["namespace"], merge=True)
```

**完了判定**:
- `bash scripts/run_task.sh daily-digest` が現行 `run_full.sh` と同じ Slack 通知 + Obsidian 書き込みを再現
- `state/daily-digest.json` に最終配信タイムスタンプが記録される
- ruff lint clean

**リスク / 回避**:
- 既存挙動の差分が出る → Phase 0 のログと突き合わせて regression test を 1 本書く
- profile.yaml の値漏れ → Phase 1 では誕生日と最低限のフィールドだけで OK

---

### Phase 2: UC6 + UC4 を新基盤で実装（半日〜1 日）

**目的**: コードを増やさずに、Task YAML + Standing Order だけで価値を出す体験を最速で得る

**UC6 (ブログ巡回 — 既存 RSS の自然拡張)**:
- 新規 `tasks/blog-watch.yaml` を `sources.yaml` のサブセット参照で作成
- `prompts/blog-watch.md` を `daily-digest.md` から派生（差分は出力フォーマットのみ）
- 「初回フルスキャン → 以降は前回送信以降の新着のみ」を `state` に last_seen_per_source として保存
- 「ブログ読んで」と Slack で言われたら 1 回走らせる手動コマンドを `scripts/oneshot.sh` で用意

**UC4 (誕生月)**:
- 新規 `tasks/birthday-month.yaml`
  - `schedule.expr: "0 8 1 <birthMonth> *"` （birthMonth は profile.yaml から）
- 新規 `prompts/birthday-month.md` （誕生月チェックリスト生成プロンプト）
- Source は無し（profile + Web 検索のみ）
- 完了履歴を `state/birthday-month.json` に記録

**完了判定**:
- ドライランで `run_task.sh blog-watch` が新着のみを通知
- `run_task.sh birthday-month --simulate-date=2026-XX-01` で誕生月通知が再現

---

### Phase 3: UC3 — Gmail source + 月次支払いウォッチ（2〜3 日）

**目的**: Gmail source プラグインを新設し、メール駆動 Task の型を確立する

**追加ファイル**:

```
sources/gmail.py                ← 新規 (Gmail API + フィルタ条件)
secrets/gmail_oauth.json        ← gitignore
secrets/gmail_token.json        ← OAuth トークン (gitignore)
tasks/payment-watch.yaml        ← 新規
prompts/payment-watch.md        ← 新規 (決済メール集計プロンプト)
prompts/payment-summary-weekly.md ← 新規 (週次サマリ用)
prompts/payment-alert-threshold.md ← 新規 (しきい値アラート用)
scripts/state.py                ← Phase 1 helper を拡張 (累計/カテゴリ集計)
```

**Gmail source 実装方針**:
- google-api-python-client + google-auth-httplib2 を依存に追加
- 初回 OAuth フローは別スクリプト `scripts/auth_gmail.py` で完了
- task YAML 側で `query` を渡し、`messages.list` の Gmail 検索構文で絞り込み

```yaml
# tasks/payment-watch.yaml
id: payment-watch
schedule:
  type: cron
  expr: "0 21 * * 0"            # 日曜 21:00 サマリ
sources:
  - type: gmail
    query: "from:(rakuten OR amazon OR paypay OR apple) newer_than:7d"
    max_results: 200
    fields: [id, snippet, internalDate, payload.headers]
prompt:
  task_md: prompts/payment-watch.md
state:
  namespace: payment-watch
outputs:
  - type: slack
```

**3 つのサブタスクをどう構成するか**:
- 即時カウント（メール受信時）は今回は省略 → 週次 + 月次のみ
- 週次サマリ task: 上記 YAML
- しきい値アラート task: 別 YAML、frequent cron（毎時）で state を読んでエッジ判定だけする
- 月末レポート task: 別 YAML、月末日に走る cron

**state スキーマ**:

```json
{
  "namespace": "payment-watch",
  "monthly": {
    "2026-04": {
      "total_jpy": 87500,
      "by_category": {"food": 12000, "subscription": 4500, "other": 71000},
      "items": [
        {"email_id": "abc", "amount": 1200, "category": "food", "ts": "2026-04-15T..."}
      ]
    }
  },
  "thresholds_fired": {"2026-04": ["50", "80"]}  // 100 はまだ未通知
}
```

**完了判定**:
- 4 週連続で日曜 21:00 にサマリが届く
- テスト用に大きな決済を追加して 80% アラート発火を確認
- 二重カウント率 < 5%

**リスク / 回避**:
- Gmail OAuth 初回フローが複雑 → setup ドキュメントを README に追記
- カテゴリ推定の精度 → Phase 3 では Claude プロンプトで分類、不正確なら次月に Standing Order を改善
- 個人情報 state 保管 → メール本文は state に残さず、id + 抽出済み構造化データのみ

---

### Phase 4: UC1 + UC5 — Calendar source（3〜5 日）

**目的**: カレンダー駆動の event-driven 型 Task を実装

**追加ファイル**:

```
sources/calendar.py             ← 新規 (Google Calendar API)
secrets/google_oauth.json       ← Phase 3 と統合可能
tasks/departure-time.yaml       ← UC1
tasks/visit-briefing.yaml       ← UC5
prompts/departure-time.md       ← UC1 プロンプト
prompts/visit-briefing.md       ← UC5 プロンプト
scripts/cron_register.sh        ← 新規 (one-shot cron 登録 helper)
```

**Calendar source の責務**:
- 設定範囲（例: 今日〜+3 日）の予定を fetch
- 各予定をフィルタ（ドメイン、場所、参加者）して構造化イベントに変換
- task YAML 側でフィルタ条件を宣言

```yaml
# tasks/departure-time.yaml
schedule:
  type: cron
  expr: "0 7 * * *"             # 毎朝 7:00 当日予定スキャン
sources:
  - type: calendar
    range: today
    filter:
      location_kind: physical    # オンライン除外
      attendees_have_external: any
prompt:
  task_md: prompts/departure-time.md
state:
  namespace: departure-time
outputs:
  - type: slack
post_actions:
  - type: register_cron         # Claude が出した出発時刻 -30m に再通知 cron 登録
    script: scripts/cron_register.sh
```

**重複通知抑止**:
- state に `notified_event_ids: ["evt_abc", ...]` を保存
- 当日 7:00 のスキャンでは notified に含まれる予定をスキップ
- 通知済みは翌日 0:00 にクリア（または当日中だけ保持）

**UC5 訪問先ブリーフィング**:
- 別 task YAML で前日 20:00 cron
- フィルタ条件: 外部ドメイン参加者あり + location が物理住所
- Source は Calendar、Web fetch は Claude Code CLI のツール経由
- 出力: Slack + `Obsidian/Briefings/<date>-<company>.md`

**Calendar push 連携 (オプション)**:
- Google Calendar の Push Notifications を webhook で受け、登録/更新時に即時 task を走らせる
- 初期は cron スキャン (毎朝 7:00) を fallback とし、Push 連携は後日加点

**完了判定**:
- UC1: 1 週間連続で物理外出予定に通知、リモート予定では出ない
- UC5: 外部予定 5 件で連続成功、ソース URL が必ず併記

---

### Phase 5: UC2 — 旅程台帳（3〜5 日, Phase 3 + 4 完了後）

**目的**: Gmail (UC3 流用) + Calendar (UC4 流用) + 旅程台帳の合わせ技で多段 cron を完走させる

**追加要素**:
- `tasks/travel-watch.yaml` — メール検知 + 旅程登録
- `tasks/travel-checklist-d14/d7/d3/d1.yaml` — 段階チェックリスト
- 旅程台帳: `Obsidian/Travel/<YYYY-MM-name>.md`（自動メンテ）
- state namespace: `travel`、各旅程ごとに `trip_id` で分離

**state スキーマ**:

```json
{
  "trips": {
    "2026-05-osaka": {
      "departure_date": "2026-05-15",
      "destinations": ["Osaka"],
      "bookings": {
        "flight": {"confirmed": true, "ref": "JAL001"},
        "hotel": {"confirmed": false},
        "rental_car": null
      },
      "checklist_sent": {"D-14": true, "D-7": false, "D-3": false, "D-1": false}
    }
  }
}
```

**完了判定**:
- 1 旅程で D-14/D-7/D-3/D-1 通知が時系列で届く
- 既予約項目は重複チェックされない

---

### Phase 6: 計測と振り返り（継続）

**作業**:
- 週次レビュー task を追加
  - 今週の Task 実行回数、エラー件数、ユーザー反応の少ない通知の特定
- Standing Order の改訂サイクル（月 1 回）
- 不要 task の削除 / sleep 化
- ログ集約: 各 task の last_run / status を `state/_health.json` に集約

**指標**:
- 通知のうち「役立った」率
- false-positive 通知率
- 通知 / 日 の中央値（うるささ代理指標）
- Standing Order 更新回数

**完了判定**:
- 月 1 回の振り返りで Standing Order が 1 個以上更新される

---

## 5. 推奨マイルストーン

```
W1     Phase 0 (環境棚卸し)
W1-W2  Phase 1 (基盤拡張: Task/Source/State 抽象化) ← MVP の前提
W2     Phase 2 (UC6 ブログ + UC4 誕生月)
W3-W4  Phase 3 (UC3 支払いウォッチ) ← 体感価値の本命
W5-W6  Phase 4 (UC1 出発時刻 + UC5 ブリーフィング)
W7+    Phase 5 (UC2 旅行) → Phase 6 (継続運用)
```

最初の 2 週間で「Task 抽象 + 既存挙動の保証 + 軽い 2 タスク」、その後 1 ヶ月で MVP を完成。

---

## 6. コード変更ボリューム見積り

| Phase | 主な追加ファイル | 推定 Python LOC | 推定 Bash LOC |
|-------|-----------------|----------------|---------------|
| Phase 0 | （ドキュメントのみ） | 0 | 0 |
| Phase 1 | orchestrator.py, base source, state.py, profile.yaml | 300〜500 | 50 |
| Phase 2 | tasks 2 本 + prompts 2 本 | 0 | 30 |
| Phase 3 | gmail.py, auth_gmail.py, payment task 群 | 200〜400 | 50 |
| Phase 4 | calendar.py, cron_register.sh, task 2 本 | 200〜400 | 100 |
| Phase 5 | travel task 群 | 100〜200 | 30 |
| Phase 6 | health 集約 task | 50〜100 | 30 |

合計で Python 約 1,000 行 + Bash 300 行 + 設定 / プロンプト類。owlclaw 本体の規模を 2〜3 倍にする規模感。

---

## 7. リスクと回避策（横断）

| リスク | 影響 | 回避策 |
|-------|------|--------|
| Phase 1 で既存挙動が壊れる | 高 | 移行前のフルログを Phase 0 で取得し、移行後 1 週間は両系並走 |
| Gmail / Calendar OAuth 切れ | 高 | 起動時にトークン有効性をチェック、切れたら Slack に即通知 |
| 通知過多でユーザーが嫌になる | 中 | 各 task に `quiet_hours` (22:00-7:00) を必ず設定 |
| ハルシネーション (UC5) | 中-高 | プロンプトで「ソース URL 無しの情報は載せない」を強制 |
| プライバシー漏洩 | 高 | state にメール本文/個人情報を残さない。raw データは tmp/ で逐次破棄 |
| Schedule 取りこぼし (mac スリープ等) | 中 | 起動時に `last_run` を見て missed を 1 回だけ catchup |
| Standing Order の暗黙化 | 中 | `tasks/` と `prompts/standing-order.md` を git 管理し、変更履歴を残す |
| Claude Code CLI の挙動変更 | 中 | CLI 呼び出しを 1 関数に隔離して、変更時に 1 箇所修正で済む構造に |

---

## 8. owlclaw リポジトリへの取り込み方針

- 各 Phase ごとに **separate PR** にする（Phase 1 だけは大きいので 2-3 PR に分割可）
- ブランチ命名: `devin/<phase>-<short-desc>` 例: `devin/phase1-task-abstraction`
- 既存 `run_full.sh` は Phase 1 完了時点で deprecation コメントを付け、Phase 2 完了後に削除
- README に進捗表を追記し、各 Phase の状態が一目で分かるように

---

## 9. 次の意思決定ポイント

実装を進めるにあたり、以下を決めたい:

1. **MVP 対象**: UC4 + UC6 + UC3 の 3 つで MVP とする? UC1/UC5 まで含める?
2. **通知先**: Slack を引き続きメイン? Telegram / Discord / iMessage を併用?
3. **ホスト先**: mac local（launchd）? VPS（systemd）? — 安定性に直結
4. **Calendar push 連携**: Phase 4 で初期から実装? それとも fallback の cron スキャンのみで MVP を完成?
5. **state 永続化形式**: JSON ファイルで開始（Phase 1〜3）、SQLite に切り替えるかは Phase 4 で再評価?
6. **Windsurf で既に着手している実装**: 上記の Phase 構成と整合する? 別構成で進んでいる?

---

## 10. v1 仕様書からの主な差分

| 項目 | v1 (openclaw/openclaw 想定) | v2 (owlclaw 想定) |
|------|----------------------------|-------------------|
| 基盤 | TypeScript 640k LOC の OSS | Python + Bash + Claude CLI の自前 repo |
| 駒の出処 | 既存 extension を流用 | ほぼ全部新規実装 |
| Phase 1 | 「設定だけで動く」 | 「Task 抽象化の足場を作る」 |
| LLM ドライバ | openclaw の agent loop | Claude Code CLI に丸投げ |
| State | memory-core extension | JSON ファイル（後で SQLite 検討） |
| Schedule | `src/cron` service | mac launchd or systemd |
| Standing Order | `AGENTS.md` 直書き | `prompts/standing-order.md` + 各 task prompt |
| 推定 LOC | コア変更ほぼ 0 | Python 約 1,000 + Bash 約 300 |

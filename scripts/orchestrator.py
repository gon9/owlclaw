#!/usr/bin/env python3
"""
owlclaw: タスクオーケストレーター。

tasks/<task-id>.yaml を読み込み、以下のパイプラインを実行する:
  1. Sources fetch → tmp/<task-id>/events.md
  2. State / profile を tmp/<task-id>/ に配置
  3. Claude Code CLI を stdin 経由で呼び出し
  4. Outputs dispatch (Obsidian / Slack 等)
  5. State の last_run / last_seen_per_source を更新

使い方:
  uv run python scripts/orchestrator.py <task-id> [--simulate-date YYYY-MM-DD]
"""

import argparse
import json
import subprocess
import sys
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import yaml

PROJ = Path(__file__).parent.parent
sys.path.insert(0, str(PROJ))  # sources.* のインポートに必要

JST = timezone(timedelta(hours=9))


def _load_task(task_id: str) -> dict:
    """タスク定義 YAML を読み込む。"""
    path = PROJ / "tasks" / f"{task_id}.yaml"
    if not path.exists():
        print(f"Error: tasks/{task_id}.yaml が見つかりません。", file=sys.stderr)
        sys.exit(1)
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _load_profile() -> dict:
    """ユーザープロファイル YAML を読み込む。存在しない場合は空辞書を返す。"""
    path = PROJ / "config" / "profile.yaml"
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _dispatch_source(
    source_cfg: dict,
    global_cutoff: datetime,
    now: datetime,
    current_state: dict,
) -> tuple[str, dict]:
    """ソース設定に基づいて fetch し、(Markdown, latest_seen_dict) を返す。"""
    src_type = source_cfg.get("type")
    if src_type == "rss":
        from sources.rss import RssSource
        config_path = PROJ / source_cfg.get("config_ref", "config/sources.yaml")
        config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        if "source_filter" in source_cfg:
            config["source_filter"] = source_cfg["source_filter"]
        cutoff = (
            now - timedelta(hours=source_cfg["lookback_hours"])
            if "lookback_hours" in source_cfg
            else global_cutoff
        )
        last_seen = current_state.get("last_seen_per_source", {})
        return RssSource().fetch(config, cutoff, last_seen_per_source=last_seen)
    if src_type == "gmail":
        from sources.gmail import GmailSource
        config = dict(source_cfg)  # コピーして注入
        config["__seen_email_ids__"] = current_state.get("seen_email_ids", [])
        cutoff = (
            now - timedelta(hours=source_cfg["lookback_hours"])
            if "lookback_hours" in source_cfg
            else global_cutoff
        )
        return GmailSource().fetch(config, cutoff)
    if src_type == "arxiv":
        from sources.arxiv import ArxivSource
        return ArxivSource().fetch(source_cfg, global_cutoff)
    if src_type == "podcast":
        from sources.podcast import PodcastSource
        return PodcastSource().fetch(source_cfg, global_cutoff)
    if src_type == "twitter":
        from sources.twitter import TwitterSource
        return TwitterSource().fetch(source_cfg, global_cutoff)
    if src_type == "calendar":
        from sources.calendar import CalendarSource
        config = dict(source_cfg)
        config["__notified_event_ids__"] = current_state.get("notified_event_ids", [])
        return CalendarSource().fetch(config, global_cutoff)
    raise ValueError(f"未対応の source タイプ: {src_type}")


def _score_events_md(events_md: str, scoring_cfg: dict) -> str:
    """events.md の各アイテムを score.py でスコアリングして注釈を付与する。

    Parameters
    ----------
    events_md : str
        ソースfetch後のMarkdown文字列
    scoring_cfg : dict
        スコアリング設定。有効キー:
          - top_n (int): スコア上位N件のみ残す (0=全件保持, デフォルト: 0)

    Returns
    -------
    str
        スコア注釈付き Markdown
    """
    import re

    from tools.score import ScoreError, score_item

    top_n: int = int(scoring_cfg.get("top_n", 0))

    pattern = re.compile(
        r"(### \d+\.\s+)(.+?)\n((?:- .+\n)*)",
        re.MULTILINE,
    )
    scored: list[tuple[int, str, str]] = []

    def _annotate(m: re.Match) -> str:
        prefix = m.group(1)
        title = m.group(2).strip()
        details = m.group(3)
        url = ""
        excerpt = ""
        for line in details.splitlines():
            if line.startswith("- URL:"):
                url = line[6:].strip()
            elif line.startswith("- Excerpt:") or line.startswith("- Abstract:"):
                excerpt = line.split(":", 1)[1].strip()
        try:
            result = score_item({"title": title, "text": excerpt or title, "url": url})
            score = result["score"]
            prio = result["priority"].upper()
            annotation = f"[Score:{score}/10|{prio}] "
        except ScoreError as e:
            print(f"  [scoring] スコアリング失敗: {e}", file=sys.stderr)
            score = 0
            annotation = "[Score:?/10] "
        full_block = f"{prefix}{annotation}{title}\n{details}"
        scored.append((score, title, full_block))
        return full_block

    annotated_md = pattern.sub(_annotate, events_md)

    if top_n > 0 and scored:
        sorted_blocks = sorted(scored, key=lambda x: x[0], reverse=True)
        top_titles = {title for _, title, _ in sorted_blocks[:top_n]}
        keep_pattern = re.compile(
            r"(### \d+\.\s+(?:\[Score:\S+\s+)?(?:.*?)\n(?:- .+\n)*)",
            re.MULTILINE,
        )

        def _keep_top(m: re.Match) -> str:
            block = m.group(0)
            title_match = re.search(r"### \d+\.\s+(?:\[\S+\s+)?(.+?)\n", block)
            if title_match and title_match.group(1).strip() in top_titles:
                return block
            return ""

        filtered = keep_pattern.sub(_keep_top, annotated_md)
        header_lines = []
        for line in annotated_md.splitlines():
            if line.startswith("###"):
                break
            header_lines.append(line)
        footer_note = (
            f"\n\n---\n*スコアリング: {len(scored)}件中上位{top_n}件を表示*\n"
        )
        return "\n".join(header_lines) + "\n" + filtered.strip() + footer_note

    return annotated_md


def _build_claude_prompt(task: dict, task_dir: Path) -> str:
    """Claude Code CLI に渡すタスクプロンプトを動的生成する。"""
    task_md = PROJ / task["prompt"]["task_md"]
    standing_md = PROJ / task["prompt"].get("standing_order_md", "prompts/standing-order.md")
    outputs = {o["type"] for o in task.get("outputs", [])}

    # 入力ファイル名は input.file 指定があればそれを優先
    input_cfg: dict = task.get("input") or {}
    input_file = input_cfg.get("file", "events.md")

    lines = [
        "以下を順番に実行してください。",
        "",
        f"1. Read `{task_dir / input_file}` (入力イベント一覧)",
        f"2. Read `{task_dir / 'profile.yaml'}` (ユーザープロファイル)",
        f"3. Read `{standing_md}` の共通ルールを確認",
        f"4. Read `{task_md}` の指示に従いキュレーション・要約",
    ]

    # video.top_n が定義されていれば Claude にピックアップ件数を明示
    video_cfg: dict = task.get("video") or {}
    if "top_n" in video_cfg:
        lines.append(
            f"   ※ このタスクでは **top_n = {video_cfg['top_n']}** 件を選定して"
            "動画スライドに変換すること"
        )
    if "visual_mode" in video_cfg:
        lines.append(
            f"   ※ visual_mode = `{video_cfg['visual_mode']}`。"
            "ニュース本文スライドの表現方式はこの設定を優先すること"
        )
    step = 5
    if "obsidian" in outputs:
        lines.append(f"{step}. Write `{task_dir / 'note_draft.md'}` にObsidianノート本文を書く")
        step += 1
    if "slack" in outputs:
        lines.append(
            f"{step}. Write `{task_dir / 'slack.txt'}` にSlackメッセージを書く"
            " （新着なければ何も書かない）"
        )
        step += 1
    if "video" in outputs:
        lines.append(
            f"{step}. Write `{task_dir / 'slides.json'}` に動画台本（slides.jsonスキーマ準拠）"
            "を書く"
        )
    lines += ["", "完了したら '完了' とだけ出力してください。"]
    return "\n".join(lines)


def _invoke_claude(prompt: str, allowed_tools: str = "Read,Write") -> None:
    """Claude Code CLI を stdin 経由で呼び出す。"""
    subprocess.run(
        ["claude", "--print", "--allowedTools", allowed_tools],
        input=prompt,
        text=True,
        check=True,
    )


def _resolve_obsidian_dest(output: dict, date: str) -> str:
    """Obsidian出力設定からVault内の相対保存先を組み立てる。"""
    path_template = output.get("path_template")
    if path_template:
        try:
            return str(path_template).format(date=date)
        except KeyError as e:
            raise ValueError(f"未解決の path_template 変数: {e.args[0]}") from e
    subdir = str(output.get("subdir", "owlclaw/daily")).rstrip("/")
    return f"{subdir}/{date}.md"


def _dispatch_outputs(task: dict, task_dir: Path, date: str) -> None:
    """task.outputs の定義に従って成果物を配信する。ファイル不在・空ならスキップ。"""
    scripts_dir = PROJ / "scripts"
    for output in task.get("outputs", []):
        out_type = output.get("type")
        if out_type == "obsidian":
            note_path = task_dir / "note_draft.md"
            if not note_path.exists() or note_path.stat().st_size == 0:
                print("  note_draft.md なし/空 — Obsidian 書き込みスキップ", file=sys.stderr)
                continue
            relative_dest = _resolve_obsidian_dest(output, date)
            subprocess.run(
                [
                    "bash",
                    str(scripts_dir / "write_obsidian.sh"),
                    date,
                    str(note_path),
                    relative_dest,
                ],
                check=True,
            )
        elif out_type == "slack":
            slack_path = task_dir / "slack.txt"
            if not slack_path.exists() or slack_path.stat().st_size == 0:
                print("  slack.txt なし/空 — Slack 通知スキップ", file=sys.stderr)
                continue
            subprocess.run(
                ["bash", str(scripts_dir / "slack_notify.sh"), str(slack_path)],
                check=True,
            )
        elif out_type == "video":
            _dispatch_video_output(output, task_dir, date)
        else:
            print(f"Warning: 未対応の output タイプ: {out_type}", file=sys.stderr)


def _purge_old_videos(video_dir: Path, retention_days: int) -> int:
    """retention_days より古い digest_*.mp4 を削除し、削除件数を返す。"""
    if retention_days <= 0:
        return 0
    cutoff = datetime.now(UTC) - timedelta(days=retention_days)
    purged = 0
    for mp4 in video_dir.glob("digest_*.mp4"):
        mtime = datetime.fromtimestamp(mp4.stat().st_mtime, tz=UTC)
        if mtime < cutoff:
            print(f"  cleanup: 古い動画を削除 ({mtime.date()}): {mp4.name}", file=sys.stderr)
            mp4.unlink()
            purged += 1
    return purged


def _dispatch_video_output(output: dict, task_dir: Path, date: str) -> None:
    """動画出力ディスパッチャ。slides.json から MP4 を生成する。

    Parameters
    ----------
    output : dict
        task.outputs の 1 要素（type=video）
    task_dir : Path
        当該タスクの作業ディレクトリ（slides.json が配置済み）
    date : str
        実行日（YYYY-MM-DD）
    """
    slides_json = task_dir / "slides.json"
    if not slides_json.exists() or slides_json.stat().st_size == 0:
        print("  slides.json なし/空 — 動画生成スキップ", file=sys.stderr)
        return

    # 古い動画を先に削除（ストレージ圧迫対策、既定: 7日）
    retention_days = int(output.get("retention_days", 7))
    _purge_old_videos(task_dir, retention_days)

    slides_dir = task_dir / "slides"
    audio_dir = task_dir / "audio"
    out_mp4 = task_dir / f"digest_{date.replace('-', '')}.mp4"

    scripts_dir = PROJ / "scripts"
    # 既に uv 環境内で実行中なので sys.executable (.venv の python) を直接使う
    py = sys.executable
    print(f"  動画生成: {out_mp4}", file=sys.stderr)
    subprocess.run(
        [py, str(scripts_dir / "render_slides.py"), str(slides_json), str(slides_dir)],
        check=True,
    )
    subprocess.run(
        [py, str(scripts_dir / "render_audio.py"), str(slides_json), str(audio_dir)],
        check=True,
    )
    subprocess.run(
        [py, str(scripts_dir / "compose_video.py"), str(slides_json),
         str(slides_dir), str(audio_dir), str(out_mp4)],
        check=True,
    )

    # Google Drive upload (オプション)
    drive_url: str | None = None
    if output.get("drive_upload"):
        try:
            from tools.upload_drive import upload_to_drive  # noqa: PLC0415
            folder = output.get("drive_folder", "owlclaw/video-digest")
            print(f"  Drive upload: {out_mp4.name} → {folder}/", file=sys.stderr)
            result = upload_to_drive(out_mp4, folder_path=folder)
            drive_url = result.get("webViewLink")
            print(f"  Drive URL: {drive_url}", file=sys.stderr)
        except Exception as e:  # noqa: BLE001
            print(f"  Warning: Drive upload 失敗: {e}", file=sys.stderr)

    # Slack 通知
    if output.get("slack_notify"):
        if drive_url:
            slack_msg = (
                f":movie_camera: *動画ダイジェスト生成完了* `{date}`\n"
                f":link: <{drive_url}|Google Drive で再生>\n"
                f":file_folder: `{out_mp4.name}`"
            )
        else:
            slack_msg = (
                f":movie_camera: *動画ダイジェスト生成完了* `{date}`\n"
                f":file_folder: `{out_mp4}`\n"
                f":memo: `open '{out_mp4}'` で再生"
            )
        slack_txt = task_dir / "slack_video.txt"
        slack_txt.write_text(slack_msg, encoding="utf-8")
        subprocess.run(
            ["bash", str(scripts_dir / "slack_notify.sh"), str(slack_txt)],
            check=False,  # Slack 失敗で動画は守る
        )


def main() -> None:
    """メインエントリーポイント。"""
    parser = argparse.ArgumentParser(description="owlclaw タスクオーケストレーター")
    parser.add_argument("task_id", help="タスクID (tasks/<task-id>.yaml)")
    parser.add_argument(
        "--simulate-date",
        default=None,
        metavar="YYYY-MM-DD",
        help="テスト用: 実行日付を上書き (例: 2026-10-01)",
    )
    args = parser.parse_args()
    task_id = args.task_id

    task = _load_task(task_id)
    profile = _load_profile()

    if args.simulate_date:
        now = (
            datetime.fromisoformat(args.simulate_date)
            .replace(hour=8, minute=0, second=0)
            .astimezone(UTC)
        )
        print(f"=== [simulate-date] {args.simulate_date} として実行 ===", file=sys.stderr)
    else:
        now = datetime.now(UTC)

    date = now.astimezone(JST).strftime("%Y-%m-%d")

    # birthday_guard: 誕生月以外はスキップ
    if task.get("birthday_guard"):
        birthday_str = profile.get("birthday", "")
        if birthday_str:
            birth_month = int(birthday_str.split("-")[1])
            current_month = now.astimezone(JST).month
            if current_month != birth_month:
                print(
                    f"=== [{task_id}] 誕生月ではないためスキップ"
                    f" ({current_month}月 ≠ {birth_month}月) ===",
                    file=sys.stderr,
                )
                sys.exit(0)
        else:
            print(
                f"Warning: [{task_id}] profile.yaml の birthday が未設定。"
                "birthday_guard をスキップ。",
                file=sys.stderr,
            )

    sources_cfg_path = PROJ / "config" / "sources.yaml"
    sources_cfg = yaml.safe_load(sources_cfg_path.read_text(encoding="utf-8"))
    lookback_hours: int = sources_cfg.get("digest", {}).get("lookback_hours", 24)
    global_cutoff = now - timedelta(hours=lookback_hours)

    task_dir = PROJ / "tmp" / task_id
    task_dir.mkdir(parents=True, exist_ok=True)

    import state as state_mod  # noqa: PLC0415  (scripts/state.py)
    current_state = state_mod.load(task["state"]["namespace"])

    print(f"=== [{task_id}] 1/4 sources fetch ===", file=sys.stderr)
    src_list = task.get("sources") or []
    input_cfg: dict = task.get("input") or {}
    all_latest_seen: dict[str, str] = {}
    if src_list:
        events_parts = []
        for src in src_list:
            md, latest_seen = _dispatch_source(src, global_cutoff, now, current_state)
            events_parts.append(md)
            all_latest_seen.update(latest_seen)
        events_md = "\n".join(events_parts)
        (task_dir / "events.md").write_text(events_md, encoding="utf-8")
    elif input_cfg.get("from_task"):
        # 別タスクの成果物を入力として読み込む（例: video-digest が daily-digest を取り込む）
        src_task = input_cfg["from_task"]
        src_file = input_cfg.get("file", "note_draft.md")
        src_path = PROJ / "tmp" / src_task / src_file
        if not src_path.exists():
            print(
                f"Error: input source {src_path} が見つかりません。"
                f"先に {src_task} を実行してください。",
                file=sys.stderr,
            )
            sys.exit(1)
        content = src_path.read_text(encoding="utf-8")
        events_md = (
            f"# 入力: {src_task} の成果物 ({src_file})\n"
            f"# 取得元: {src_path}\n\n{content}"
        )
        # input.file の名前で保存（プロンプト整合）
        (task_dir / src_file).write_text(events_md, encoding="utf-8")
    else:
        events_md = (
            f"# タスク実行コンテキスト — {date}\n\n"
            "このタスクには外部ソースがありません。\n"
            "profile.yaml を参照し、必要に応じて WebFetch で最新情報を補完してください。\n"
        )
        (task_dir / "events.md").write_text(events_md, encoding="utf-8")

    scoring_cfg: dict = task.get("scoring", {})
    if scoring_cfg.get("enabled"):
        print(f"=== [{task_id}] 2/5 scoring ===", file=sys.stderr)
        events_md = _score_events_md(events_md, scoring_cfg)
        (task_dir / "events.md").write_text(events_md, encoding="utf-8")
        steps = "5"
    else:
        steps = "4"

    step_state = 3 if scoring_cfg.get("enabled") else 2
    print(f"=== [{task_id}] {step_state}/{steps} state / profile 配置 ===", file=sys.stderr)
    (task_dir / "state.json").write_text(
        json.dumps(current_state, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (task_dir / "profile.yaml").write_text(
        yaml.dump(profile, allow_unicode=True), encoding="utf-8"
    )

    # travel-checklist 向け: context.md (D-N 判定済み旅程一覧) を生成
    if task_id == "travel-checklist":
        from tools.travel import build_context_md, get_pending_checklists
        trips = current_state.get("trips", {})
        pending = get_pending_checklists(trips, now.astimezone(JST).date())
        if not pending:
            print(
                f"=== [{task_id}] 本日 D-N 対象旅程なし — スキップ ===",
                file=sys.stderr,
            )
            state_mod.save(task["state"]["namespace"], current_state)
            return
        (task_dir / "context.md").write_text(
            build_context_md(trips, now.astimezone(JST).date()),
            encoding="utf-8",
        )

    step_claude = 4 if scoring_cfg.get("enabled") else 3
    print(f"=== [{task_id}] {step_claude}/{steps} claude --print ===", file=sys.stderr)
    allowed_tools = task.get("allowed_tools", "Read,Write")
    prompt = _build_claude_prompt(task, task_dir)
    _invoke_claude(prompt, allowed_tools=allowed_tools)

    step_out = 5 if scoring_cfg.get("enabled") else 4
    print(f"=== [{task_id}] {step_out}/{steps} outputs dispatch ===", file=sys.stderr)
    _dispatch_outputs(task, task_dir, date)

    # state 更新: last_run + last_seen_per_source + seen_email_ids + notified_event_ids をマージ
    current_state["last_run"] = now.isoformat()
    last_seen_updates: dict[str, str] = {}
    new_seen_ids: list[str] = []
    new_notified_ids: list[str] = []
    for key, value in all_latest_seen.items():
        if key == "__gmail_seen_ids__" and isinstance(value, list):
            new_seen_ids.extend(value)
        elif key == "__calendar_notified_ids__" and isinstance(value, list):
            new_notified_ids.extend(value)
        else:
            last_seen_updates[key] = value
    if last_seen_updates:
        current_state["last_seen_per_source"] = {
            **current_state.get("last_seen_per_source", {}),
            **last_seen_updates,
        }
    if new_seen_ids:
        existing_ids: set[str] = set(current_state.get("seen_email_ids", []))
        current_state["seen_email_ids"] = list(existing_ids | set(new_seen_ids))
    if new_notified_ids:
        existing_notified: set[str] = set(current_state.get("notified_event_ids", []))
        current_state["notified_event_ids"] = list(existing_notified | set(new_notified_ids))
    # travel: trips_update.json をマージ
    trips_update_path = task_dir / "trips_update.json"
    if trips_update_path.exists() and trips_update_path.stat().st_size > 0:
        from tools.travel import merge_trips
        try:
            updates = json.loads(trips_update_path.read_text(encoding="utf-8"))
            current_state["trips"] = merge_trips(
                current_state.get("trips", {}), updates
            )
            print(
                f"✓ trips_update: {list(updates.keys())} をマージしました",
                file=sys.stderr,
            )
        except Exception as e:
            print(f"Warning: trips_update.json のマージ失敗: {e}", file=sys.stderr)
    state_mod.save(task["state"]["namespace"], current_state)

    print(f"=== [{task_id}] 完了 ({date}) ===", file=sys.stderr)


if __name__ == "__main__":
    main()

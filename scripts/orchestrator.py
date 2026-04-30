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
        # source_filter を config に注入
        if "source_filter" in source_cfg:
            config["source_filter"] = source_cfg["source_filter"]
        # per-source lookback_hours オーバーライド
        cutoff = (
            now - timedelta(hours=source_cfg["lookback_hours"])
            if "lookback_hours" in source_cfg
            else global_cutoff
        )
        last_seen = current_state.get("last_seen_per_source", {})
        return RssSource().fetch(config, cutoff, last_seen_per_source=last_seen)
    raise ValueError(f"未対応の source タイプ: {src_type}")


def _build_claude_prompt(task: dict, task_dir: Path) -> str:
    """Claude Code CLI に渡すタスクプロンプトを動的生成する。"""
    task_md = PROJ / task["prompt"]["task_md"]
    standing_md = PROJ / task["prompt"].get("standing_order_md", "prompts/standing-order.md")
    outputs = {o["type"] for o in task.get("outputs", [])}

    lines = [
        "以下を順番に実行してください。",
        "",
        f"1. Read `{task_dir / 'events.md'}` (入力イベント一覧)",
        f"2. Read `{task_dir / 'profile.yaml'}` (ユーザープロファイル)",
        f"3. Read `{standing_md}` の共通ルールを確認",
        f"4. Read `{task_md}` の指示に従いキュレーション・要約",
    ]
    step = 5
    if "obsidian" in outputs:
        lines.append(f"{step}. Write `{task_dir / 'note_draft.md'}` にObsidianノート本文を書く")
        step += 1
    if "slack" in outputs:
        lines.append(
            f"{step}. Write `{task_dir / 'slack.txt'}` にSlackメッセージを書く"
            " （新着なければ何も書かない）"
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
            subprocess.run(
                ["bash", str(scripts_dir / "write_obsidian.sh"), date, str(note_path)],
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
        else:
            print(f"Warning: 未対応の output タイプ: {out_type}", file=sys.stderr)


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
    all_latest_seen: dict[str, str] = {}
    if src_list:
        events_parts = []
        for src in src_list:
            md, latest_seen = _dispatch_source(src, global_cutoff, now, current_state)
            events_parts.append(md)
            all_latest_seen.update(latest_seen)
        events_md = "\n".join(events_parts)
    else:
        events_md = (
            f"# タスク実行コンテキスト — {date}\n\n"
            "このタスクには外部ソースがありません。\n"
            "profile.yaml を参照し、必要に応じて WebFetch で最新情報を補完してください。\n"
        )
    (task_dir / "events.md").write_text(events_md, encoding="utf-8")

    print(f"=== [{task_id}] 2/4 state / profile 配置 ===", file=sys.stderr)
    (task_dir / "state.json").write_text(
        json.dumps(current_state, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (task_dir / "profile.yaml").write_text(
        yaml.dump(profile, allow_unicode=True), encoding="utf-8"
    )

    print(f"=== [{task_id}] 3/4 claude --print ===", file=sys.stderr)
    allowed_tools = task.get("allowed_tools", "Read,Write")
    prompt = _build_claude_prompt(task, task_dir)
    _invoke_claude(prompt, allowed_tools=allowed_tools)

    print(f"=== [{task_id}] 4/4 outputs dispatch ===", file=sys.stderr)
    _dispatch_outputs(task, task_dir, date)

    # state 更新: last_run + last_seen_per_source をマージ
    current_state["last_run"] = now.isoformat()
    if all_latest_seen:
        current_state["last_seen_per_source"] = {
            **current_state.get("last_seen_per_source", {}),
            **all_latest_seen,
        }
    state_mod.save(task["state"]["namespace"], current_state)

    print(f"=== [{task_id}] 完了 ({date}) ===", file=sys.stderr)


if __name__ == "__main__":
    main()

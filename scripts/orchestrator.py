#!/usr/bin/env python3
"""
owlclaw: タスクオーケストレーター。

tasks/<task-id>.yaml を読み込み、以下のパイプラインを実行する:
  1. Sources fetch → tmp/<task-id>/events.md
  2. State / profile を tmp/<task-id>/ に配置
  3. Claude Code CLI を stdin 経由で呼び出し
  4. Outputs dispatch (Obsidian / Slack 等)
  5. State の last_run を更新

使い方:
  uv run python scripts/orchestrator.py <task-id>
"""

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


def _dispatch_source(source_cfg: dict, cutoff: datetime) -> str:
    """ソース設定に基づいて fetch し、Markdown 文字列を返す。"""
    src_type = source_cfg.get("type")
    if src_type == "rss":
        from sources.rss import RssSource
        config_path = PROJ / source_cfg.get("config_ref", "config/sources.yaml")
        config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        return RssSource().fetch(config, cutoff)
    raise ValueError(f"未対応の source タイプ: {src_type}")


def _build_claude_prompt(task: dict, task_dir: Path) -> str:
    """Claude Code CLI に渡すタスクプロンプトを動的生成する。"""
    task_md = PROJ / task["prompt"]["task_md"]
    standing_md = PROJ / task["prompt"].get("standing_order_md", "prompts/standing-order.md")
    note_path = task_dir / "note_draft.md"
    slack_path = task_dir / "slack.txt"

    lines = [
        "以下を順番に実行してください。",
        "",
        f"1. Read `{task_dir / 'events.md'}` (入力イベント一覧)",
        f"2. Read `{standing_md}` の共通ルールを確認",
        f"3. Read `{task_md}` の指示に従いキュレーション・要約",
        f"4. Write `{note_path}` にObsidianノート本文を書く",
        f"5. Write `{slack_path}` にSlackメッセージを書く",
        "",
        "完了したら '完了' とだけ出力してください。",
    ]
    return "\n".join(lines)


def _invoke_claude(prompt: str) -> None:
    """Claude Code CLI を stdin 経由で呼び出す。"""
    subprocess.run(
        ["claude", "--print", "--allowedTools", "Read,Write"],
        input=prompt,
        text=True,
        check=True,
    )


def _dispatch_outputs(task: dict, task_dir: Path, date: str) -> None:
    """task.outputs の定義に従って成果物を配信する。"""
    scripts_dir = PROJ / "scripts"
    for output in task.get("outputs", []):
        out_type = output.get("type")
        if out_type == "obsidian":
            note_path = task_dir / "note_draft.md"
            subprocess.run(
                ["bash", str(scripts_dir / "write_obsidian.sh"), date, str(note_path)],
                check=True,
            )
        elif out_type == "slack":
            slack_path = task_dir / "slack.txt"
            subprocess.run(
                ["bash", str(scripts_dir / "slack_notify.sh"), str(slack_path)],
                check=True,
            )
        else:
            print(f"Warning: 未対応の output タイプ: {out_type}", file=sys.stderr)


def main() -> None:
    """メインエントリーポイント。"""
    if len(sys.argv) < 2:
        print("Usage: orchestrator.py <task-id>", file=sys.stderr)
        sys.exit(1)

    task_id = sys.argv[1]
    task = _load_task(task_id)
    profile = _load_profile()

    now = datetime.now(UTC)
    date = now.astimezone(JST).strftime("%Y-%m-%d")

    sources_cfg_path = PROJ / "config" / "sources.yaml"
    sources_cfg = yaml.safe_load(sources_cfg_path.read_text(encoding="utf-8"))
    lookback_hours: int = sources_cfg.get("digest", {}).get("lookback_hours", 24)
    cutoff = now - timedelta(hours=lookback_hours)

    task_dir = PROJ / "tmp" / task_id
    task_dir.mkdir(parents=True, exist_ok=True)

    print(f"=== [{task_id}] 1/4 sources fetch ===", file=sys.stderr)
    events_parts = []
    for src in task.get("sources", []):
        events_parts.append(_dispatch_source(src, cutoff))
    events_md = "\n".join(events_parts)
    (task_dir / "events.md").write_text(events_md, encoding="utf-8")

    print(f"=== [{task_id}] 2/4 state / profile 配置 ===", file=sys.stderr)
    import state as state_mod  # noqa: PLC0415  (scripts/state.py)
    current_state = state_mod.load(task["state"]["namespace"])
    (task_dir / "state.json").write_text(
        json.dumps(current_state, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (task_dir / "profile.yaml").write_text(
        yaml.dump(profile, allow_unicode=True), encoding="utf-8"
    )

    print(f"=== [{task_id}] 3/4 claude --print ===", file=sys.stderr)
    prompt = _build_claude_prompt(task, task_dir)
    _invoke_claude(prompt)

    print(f"=== [{task_id}] 4/4 outputs dispatch ===", file=sys.stderr)
    _dispatch_outputs(task, task_dir, date)

    current_state["last_run"] = now.isoformat()
    state_mod.save(task["state"]["namespace"], current_state)

    print(f"=== [{task_id}] 完了 ({date}) ===", file=sys.stderr)


if __name__ == "__main__":
    main()

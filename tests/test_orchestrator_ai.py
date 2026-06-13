"""orchestrator の AI provider/model ルーティングのテスト。"""

from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path

import pytest

PROJ = Path(__file__).parent.parent


def _load_orchestrator():
    spec = importlib.util.spec_from_file_location(
        "orchestrator_ai_test",
        PROJ / "scripts" / "orchestrator.py",
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


orchestrator = _load_orchestrator()


def test_invoke_claude_adds_model_argument(monkeypatch) -> None:
    """ai.model 指定時は Claude CLI に --model を渡す。"""
    captured: dict[str, object] = {}

    def fake_run(cmd, **kwargs):  # noqa: ANN001
        captured["cmd"] = cmd
        captured["kwargs"] = kwargs

    monkeypatch.setattr(orchestrator.subprocess, "run", fake_run)

    orchestrator._invoke_ai(
        "prompt",
        allowed_tools="Read,Write",
        ai_config={"provider": "claude", "model": "fable"},
    )

    assert captured["cmd"] == [
        "claude",
        "--print",
        "--allowedTools",
        "Read,Write",
        "--model",
        "fable",
    ]
    assert captured["kwargs"] == {"input": "prompt", "text": True, "check": True}


def test_invoke_antigravity_uses_agy_print(monkeypatch: pytest.MonkeyPatch) -> None:
    """antigravity provider は agy CLI の print mode に流す。"""
    captured: dict[str, object] = {}

    def fake_run(cmd, **kwargs):  # noqa: ANN001
        captured["cmd"] = cmd
        captured["kwargs"] = kwargs

    monkeypatch.setattr(orchestrator.subprocess, "run", fake_run)

    orchestrator._invoke_ai(
        "prompt",
        allowed_tools="Read,Write",
        ai_config={"provider": "antigravity", "model": "Gemini 3.5 Flash (High)"},
    )

    assert captured["cmd"] == [
        "agy",
        "--print",
        "--dangerously-skip-permissions",
        "--model",
        "Gemini 3.5 Flash (High)",
    ]
    assert captured["kwargs"] == {"input": "prompt", "text": True, "check": True}


def test_agy_provider_alias_uses_antigravity_defaults() -> None:
    """agy alias も Antigravity として扱い、HTMLスライドを既定にする。"""
    ai_config = {"provider": "agy", "model": None}

    assert orchestrator._format_ai_label(ai_config) == "agy --print"
    assert orchestrator._default_visual_mode_for_ai(ai_config) == "html"


def test_antigravity_model_agy_is_treated_as_cli_alias() -> None:
    """model: agy はモデル名ではなくCLI alias として無視する。"""
    task = {"ai": {"provider": "antigravity", "model": "agy"}}

    assert orchestrator._resolve_ai_config(task) == {
        "provider": "antigravity",
        "model": None,
    }


def test_anthropic_label_uses_claude_cli() -> None:
    """anthropic provider の実行ログは実体の claude CLI 名にする。"""
    assert (
        orchestrator._format_ai_label({"provider": "anthropic", "model": "sonnet"})
        == "claude --print --model sonnet"
    )


def test_invoke_ai_rejects_unsupported_provider() -> None:
    """未対応 provider は誤って Claude に流さず失敗させる。"""
    with pytest.raises(ValueError, match="未対応の ai.provider"):
        orchestrator._invoke_ai(
            "prompt",
            allowed_tools="Read,Write",
            ai_config={"provider": "openai", "model": "gpt-5"},
        )


def test_resolve_ai_attempts_adds_fallback_models() -> None:
    """ai.fallback_models は primary model の後続候補として解決される。"""
    task = {"ai": {"provider": "claude", "model": "fable", "fallback_models": ["opus"]}}

    assert orchestrator._resolve_ai_attempts(task) == [
        {"provider": "claude", "model": "fable"},
        {"provider": "claude", "model": "opus"},
    ]


def test_invoke_ai_with_fallback_tries_next_model(monkeypatch: pytest.MonkeyPatch) -> None:
    """primary model の CLI 実行が失敗したら fallback model を試す。"""
    calls: list[list[str]] = []

    def fake_run(cmd, **_kwargs):  # noqa: ANN001
        calls.append(cmd)
        if cmd[-1] == "fable":
            raise subprocess.CalledProcessError(returncode=1, cmd=cmd)

    monkeypatch.setattr(orchestrator.subprocess, "run", fake_run)

    orchestrator._invoke_ai_with_fallback(
        "prompt",
        allowed_tools="Read,Write",
        ai_attempts=[
            {"provider": "claude", "model": "fable"},
            {"provider": "claude", "model": "opus"},
        ],
    )

    assert calls == [
        ["claude", "--print", "--allowedTools", "Read,Write", "--model", "fable"],
        ["claude", "--print", "--allowedTools", "Read,Write", "--model", "opus"],
    ]


def test_video_digest_sets_fable_model() -> None:
    """video-digest は slides.json 生成モデルとして fable を指定する。"""
    import yaml

    task = yaml.safe_load((PROJ / "tasks" / "video-digest.yaml").read_text(encoding="utf-8"))

    assert orchestrator._resolve_ai_config(task) == {
        "provider": "claude",
        "model": "fable",
    }


def test_video_digest_sets_opus_fallback_model() -> None:
    """video-digest は fable 失敗時に opus へ fallback する。"""
    import yaml

    task = yaml.safe_load((PROJ / "tasks" / "video-digest.yaml").read_text(encoding="utf-8"))

    assert orchestrator._resolve_ai_attempts(task) == [
        {"provider": "claude", "model": "fable"},
        {"provider": "claude", "model": "opus"},
    ]


def test_fable_defaults_to_html_visual_mode() -> None:
    """Claude fable は本文ニュースを直接HTMLスライドとして作る既定にする。"""
    assert orchestrator._default_visual_mode_for_ai(
        {"provider": "claude", "model": "fable"}
    ) == "html"


def test_video_digest_uses_html_visual_mode(tmp_path: Path) -> None:
    """video-digest のプロンプトには html モードを明示する。"""
    import yaml

    task = yaml.safe_load((PROJ / "tasks" / "video-digest.yaml").read_text(encoding="utf-8"))
    task_dir = tmp_path / "video-digest"

    assert orchestrator._resolve_visual_mode(task) == "html"
    prompt = orchestrator._build_claude_prompt(task, task_dir)
    assert "visual_mode = `html`" in prompt


def test_video_digest_reads_daily_digest_events_reference(tmp_path: Path) -> None:
    """video-digest は daily-digest の note と元フィード一覧を読む。"""
    import yaml

    task = yaml.safe_load((PROJ / "tasks" / "video-digest.yaml").read_text(encoding="utf-8"))
    task_dir = tmp_path / "video-digest"

    prompt = orchestrator._build_claude_prompt(task, task_dir)

    assert f"Read `{task_dir / 'note_draft.md'}`" in prompt
    assert f"Read `{task_dir / 'events.md'}`" in prompt


def test_copy_from_task_inputs_copies_primary_and_extra(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """from_task 入力は主ファイルと extra_files を task_dir に配置する。"""
    monkeypatch.setattr(orchestrator, "PROJ", tmp_path)
    src_dir = tmp_path / "tmp" / "daily-digest"
    src_dir.mkdir(parents=True)
    (src_dir / "note_draft.md").write_text("# Daily note\n", encoding="utf-8")
    (src_dir / "events.md").write_text(
        "# Raw events\n- URL: https://example.com\n",
        encoding="utf-8",
    )
    task_dir = tmp_path / "tmp" / "video-digest"
    task_dir.mkdir(parents=True)

    content = orchestrator._copy_from_task_inputs(
        {
            "from_task": "daily-digest",
            "file": "note_draft.md",
            "extra_files": ["events.md"],
        },
        task_dir,
    )

    assert "# 入力: daily-digest の成果物 (note_draft.md)" in content
    assert (task_dir / "note_draft.md").read_text(encoding="utf-8").endswith("# Daily note\n")
    assert "https://example.com" in (task_dir / "events.md").read_text(encoding="utf-8")


def test_clear_stale_ai_outputs_removes_video_but_keeps_inputs(tmp_path: Path) -> None:
    """AI 実行前に古い slides.json を消し、入力ファイルは残す。"""
    task = {
        "input": {
            "from_task": "daily-digest",
            "file": "note_draft.md",
            "extra_files": ["events.md"],
        },
        "outputs": [{"type": "video"}],
    }
    task_dir = tmp_path / "video-digest"
    task_dir.mkdir()
    (task_dir / "note_draft.md").write_text("input note", encoding="utf-8")
    (task_dir / "events.md").write_text("input events", encoding="utf-8")
    (task_dir / "slides.json").write_text('{"old": true}', encoding="utf-8")

    orchestrator._clear_stale_ai_outputs(task, task_dir)

    assert (task_dir / "note_draft.md").exists()
    assert (task_dir / "events.md").exists()
    assert not (task_dir / "slides.json").exists()

"""Obsidian出力先の分離に関するテスト。"""

from __future__ import annotations

import importlib.util
import os
import subprocess
from pathlib import Path

import pytest

PROJ = Path(__file__).parent.parent
WRITE_OBSIDIAN = PROJ / "scripts" / "write_obsidian.sh"


def _load_orchestrator():
    spec = importlib.util.spec_from_file_location(
        "orchestrator",
        PROJ / "scripts" / "orchestrator.py",
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


orchestrator = _load_orchestrator()


def _run_write_obsidian(
    vault: Path,
    draft: Path,
    relative_dest: str,
) -> subprocess.CompletedProcess:
    env = {**os.environ, "OBSIDIAN_VAULT": str(vault)}
    return subprocess.run(
        ["bash", str(WRITE_OBSIDIAN), "2026-05-30", str(draft), relative_dest],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )


def test_write_obsidian_uses_relative_destination(tmp_path: Path) -> None:
    draft = tmp_path / "note.md"
    draft.write_text("# arXiv Digest\n", encoding="utf-8")

    result = _run_write_obsidian(tmp_path, draft, "owlclaw/arxiv/2026-05-30.md")

    assert result.returncode == 0
    note = tmp_path / "docs_obsidian" / "20_news" / "owlclaw" / "arxiv" / "2026-05-30.md"
    assert note.read_text(encoding="utf-8") == "# arXiv Digest\n"
    assert not (tmp_path / "docs_obsidian" / "20_news" / "owlclaw" / "daily").exists()


def test_write_obsidian_rejects_parent_directory_escape(tmp_path: Path) -> None:
    draft = tmp_path / "note.md"
    draft.write_text("# Unsafe\n", encoding="utf-8")

    result = _run_write_obsidian(tmp_path, draft, "../escape.md")

    assert result.returncode == 1
    assert "Vault内の相対パス" in result.stderr
    assert not (tmp_path / "docs_obsidian" / "escape.md").exists()


@pytest.mark.parametrize(
    ("output", "expected"),
    [
        ({"type": "obsidian", "subdir": "owlclaw/daily"}, "owlclaw/daily/2026-05-30.md"),
        ({"type": "obsidian", "subdir": "owlclaw/arxiv"}, "owlclaw/arxiv/2026-05-30.md"),
        (
            {"type": "obsidian", "path_template": "Briefings/{date}-visit-briefing.md"},
            "Briefings/2026-05-30-visit-briefing.md",
        ),
    ],
)
def test_resolve_obsidian_dest(output: dict, expected: str) -> None:
    assert orchestrator._resolve_obsidian_dest(output, "2026-05-30") == expected


def test_resolve_obsidian_dest_rejects_unknown_template_variable() -> None:
    with pytest.raises(ValueError, match="未解決の path_template 変数: trip_id"):
        orchestrator._resolve_obsidian_dest(
            {"type": "obsidian", "path_template": "Travel/{trip_id}.md"},
            "2026-05-30",
        )

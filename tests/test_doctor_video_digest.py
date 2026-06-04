"""scripts/doctor_video_digest.py の単体テスト。"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

PROJ = Path(__file__).parent.parent


def _load_doctor_video_digest():
    spec = importlib.util.spec_from_file_location(
        "doctor_video_digest",
        PROJ / "scripts" / "doctor_video_digest.py",
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["doctor_video_digest"] = module
    spec.loader.exec_module(module)
    return module


def test_check_executable_reports_missing_required_binary(monkeypatch) -> None:
    doctor = _load_doctor_video_digest()
    monkeypatch.setattr(
        doctor,
        "find_executable",
        lambda name: (_ for _ in ()).throw(RuntimeError(f"missing {name}")),
    )

    result = doctor.check_executable("codex")

    assert not result.ok
    assert result.label == "executable: codex"
    assert "missing codex" in result.detail


def test_check_generated_images_reports_unwritable_directory(monkeypatch, tmp_path: Path) -> None:
    doctor = _load_doctor_video_digest()
    target = tmp_path / "generated_images"

    def fail_named_temporary_file(*_, **__):
        raise OSError("permission denied")

    monkeypatch.setattr(doctor.tempfile, "NamedTemporaryFile", fail_named_temporary_file)

    result = doctor.check_generated_images(target)

    assert not result.ok
    assert result.label == "generated_images writable"
    assert "permission denied" in result.detail

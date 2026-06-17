"""scripts/render_audio.py の単体テスト。"""

from __future__ import annotations

import importlib.util
from pathlib import Path

from tools.slide_schema import ImageSlide, SlideDeck

PROJ = Path(__file__).parent.parent


def _load_render_audio():
    spec = importlib.util.spec_from_file_location(
        "render_audio",
        PROJ / "scripts" / "render_audio.py",
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_normalize_pronunciation_replaces_known_names_case_insensitively() -> None:
    render_audio = _load_render_audio()

    replacements = render_audio.load_pronunciation_replacements()
    assert replacements["salesforce"] == "セールスフォース"

    normalized = render_audio.normalize_pronunciation(
        "Anthropicの発表とanthoropic、Salesforce連携、OWLCLAWニュース、Obsidianで確認。"
    )

    assert normalized == (
        "アンソロピックの発表とアンソロピック、"
        "セールスフォース連携、"
        "アウルクロウニュース、オブシディアンで確認。"
    )


def test_find_unregistered_latin_terms_ignores_known_terms_and_acronyms() -> None:
    render_audio = _load_render_audio()

    terms = render_audio.find_unregistered_latin_terms(
        "Salesforce と Databricks と API と GPT を比較する。",
        render_audio.load_pronunciation_replacements(),
    )

    assert terms == ["Databricks"]


def test_render_audio_synthesizes_normalized_narration(tmp_path: Path, monkeypatch) -> None:
    render_audio = _load_render_audio()
    captured: list[str] = []

    class HealthyResponse:
        def raise_for_status(self) -> None:
            pass

    class HealthyClient:
        def __init__(self, *_, **__) -> None:
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_) -> None:
            pass

        def get(self, *_):
            return HealthyResponse()

    def synthesize(text: str, _speaker: int, out_wav: Path) -> None:
        captured.append(text)
        out_wav.write_bytes(b"wav")

    monkeypatch.setattr(render_audio.httpx, "Client", HealthyClient)
    monkeypatch.setattr(render_audio, "synthesize", synthesize)
    deck = SlideDeck(
        title="Test",
        date="2026-06-01",
        slides=[
            ImageSlide(
                id="seg1",
                type="hero",
                image_prompt="An AI newsroom",
                narration="Anthropic のニュースです。",
            ),
            ImageSlide(
                id="seg2",
                type="closing",
                image_prompt="A closing scene",
                narration="OWLCLAW でした。Salesforce と Obsidian で確認できます。",
            ),
        ],
    )

    wavs = render_audio.render_audio(deck, tmp_path)

    assert captured == [
        "アンソロピック のニュースです。",
        "アウルクロウ でした。セールスフォース と オブシディアン で確認できます。",
    ]
    assert wavs == [tmp_path / "seg1.wav", tmp_path / "seg2.wav"]

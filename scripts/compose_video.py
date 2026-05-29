#!/usr/bin/env python3
"""PNG + WAV のスライド群を ffmpeg で 1 本の MP4 に合成する。

使い方:
    uv run python scripts/compose_video.py <slides.json> <slides_dir> <audio_dir> <output_mp4>

各スライドごとに「静止画 + WAV」の中間 mp4 を生成し、最後に concat demuxer で結合する。
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

PROJ = Path(__file__).parent.parent
sys.path.insert(0, str(PROJ))

from tools.slide_schema import SlideDeck, load_deck  # noqa: E402

PAD_SECONDS = 0.5  # 各スライド末尾に挿入する無音の余韻


def _find_executable(name: str) -> str:
    """PATH に無い launchd/SSH 環境でも見つかるように、代表的な場所を探す。"""
    import os as _os  # noqa: PLC0415
    found = shutil.which(name)
    if found:
        return found
    extra = [
        f"{_os.path.expanduser('~')}/.local/bin/{name}",
        f"/opt/homebrew/bin/{name}",
        f"/usr/local/bin/{name}",
    ]
    for p in extra:
        if _os.path.exists(p) and _os.access(p, _os.X_OK):
            return p
    raise RuntimeError(f"executable not found: {name} (PATH と {extra} を確認)")


def _segment_duration(wav_path: Path) -> float:
    """ffprobe で WAV の長さ（秒）を取得する。"""
    out = subprocess.check_output(
        [
            _find_executable("ffprobe"),
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "csv=p=0",
            str(wav_path),
        ],
        text=True,
    )
    return float(out.strip())


def _build_segment_mp4(png: Path, wav: Path, out_mp4: Path) -> None:
    """1スライド分の mp4（PNG + WAV + 余韻）を生成する。"""
    duration = _segment_duration(wav) + PAD_SECONDS
    subprocess.run(
        [
            _find_executable("ffmpeg"),
            "-y",
            "-loglevel",
            "warning",
            "-loop",
            "1",
            "-i",
            str(png),
            "-i",
            str(wav),
            "-c:v",
            "libx264",
            "-tune",
            "stillimage",
            "-preset",
            "medium",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-t",
            f"{duration:.3f}",
            "-pix_fmt",
            "yuv420p",
            "-vf",
            "scale=1280:720:force_original_aspect_ratio=decrease,"
            "pad=1280:720:(ow-iw)/2:(oh-ih)/2",
            str(out_mp4),
        ],
        check=True,
    )


def compose(deck: SlideDeck, slides_dir: Path, audio_dir: Path, out_mp4: Path) -> Path:
    """スライド群を結合して 1 本の MP4 を作る。"""
    work_dir = out_mp4.parent / "_segments"
    work_dir.mkdir(parents=True, exist_ok=True)

    seg_mp4s: list[Path] = []
    for slide in deck.slides:
        png = slides_dir / f"{slide.id}.png"
        wav = audio_dir / f"{slide.id}.wav"
        if not png.exists():
            raise FileNotFoundError(f"PNG not found: {png}")
        if not wav.exists():
            raise FileNotFoundError(f"WAV not found: {wav}")
        seg_mp4 = work_dir / f"{slide.id}.mp4"
        print(f"  [{slide.id}] mp4 セグメント生成中", file=sys.stderr)
        _build_segment_mp4(png, wav, seg_mp4)
        seg_mp4s.append(seg_mp4)

    # concat demuxer 用リスト
    concat_txt = work_dir / "concat.txt"
    concat_txt.write_text(
        "\n".join(f"file '{p.name}'" for p in seg_mp4s) + "\n",
        encoding="utf-8",
    )

    print(f"  concat → {out_mp4}", file=sys.stderr)
    subprocess.run(
        [
            _find_executable("ffmpeg"),
            "-y",
            "-loglevel",
            "warning",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_txt),
            "-c",
            "copy",
            str(out_mp4),
        ],
        check=True,
    )
    # concat 成功後、中間ファイル _segments/ を削除（容量節約）
    shutil.rmtree(work_dir, ignore_errors=True)
    print(f"  cleanup: {work_dir} を削除", file=sys.stderr)
    return out_mp4


def main() -> None:
    """CLI エントリポイント。"""
    parser = argparse.ArgumentParser(description="PNG+WAV スライド群を MP4 合成")
    parser.add_argument("slides_json")
    parser.add_argument("slides_dir")
    parser.add_argument("audio_dir")
    parser.add_argument("out_mp4")
    args = parser.parse_args()

    deck = load_deck(args.slides_json)
    out = compose(
        deck,
        Path(args.slides_dir),
        Path(args.audio_dir),
        Path(args.out_mp4),
    )
    print(f"✓ 動画生成完了: {out}", file=sys.stderr)


if __name__ == "__main__":
    main()

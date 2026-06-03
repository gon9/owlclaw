"""launchd/SSH 非インタラクティブ環境でも実行ファイルを発見するためのユーティリティ。

PATH が `/usr/bin:/bin:/usr/sbin:/sbin` 程度に痩せている環境（launchd の plist 既定 PATH や
非ログインの SSH セッション）でも、Homebrew (Intel/ARM) や `~/.local/bin` に置かれた
codex / ffmpeg / node などの実行バイナリを発見できるようにする。
"""

from __future__ import annotations

import os
import shutil

_DEFAULT_EXTRA_DIRS: tuple[str, ...] = (
    "~/.local/bin",
    "/opt/homebrew/bin",
    "/usr/local/bin",
)


def find_executable(name: str, extra_dirs: tuple[str, ...] = _DEFAULT_EXTRA_DIRS) -> str:
    """指定された実行ファイルを PATH および ``extra_dirs`` から探して絶対パスを返す。

    Args:
        name: 実行ファイル名（例: ``"ffmpeg"``）。
        extra_dirs: PATH で見つからなかったときに追加で探すディレクトリ。

    Returns:
        実行ファイルの絶対パス。

    Raises:
        RuntimeError: どこにも見つからなかった場合。
    """
    found = shutil.which(name)
    if found:
        return found
    expanded = [os.path.expanduser(d) for d in extra_dirs]
    for d in expanded:
        candidate = os.path.join(d, name)
        if os.path.exists(candidate) and os.access(candidate, os.X_OK):
            return candidate
    raise RuntimeError(f"executable not found: {name} (PATH と {expanded} を確認)")

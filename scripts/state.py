"""
owlclaw: stateファイルのget/set ヘルパー。

state/<namespace>.json を読み書きする薄いラッパー。
"""

import json
from pathlib import Path

_STATE_DIR = Path(__file__).parent.parent / "state"


def load(namespace: str) -> dict:
    """
    指定 namespace の state を辞書として返す。ファイルが存在しない場合は空辞書を返す。

    Parameters
    ----------
    namespace : str
        タスクの namespace（例: "daily-digest"）

    Returns
    -------
    dict
        state データ
    """
    path = _STATE_DIR / f"{namespace}.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def save(namespace: str, data: dict) -> None:
    """
    指定 namespace の state を JSON ファイルに書き出す。

    Parameters
    ----------
    namespace : str
        タスクの namespace（例: "daily-digest"）
    data : dict
        保存するstate データ
    """
    _STATE_DIR.mkdir(parents=True, exist_ok=True)
    path = _STATE_DIR / f"{namespace}.json"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

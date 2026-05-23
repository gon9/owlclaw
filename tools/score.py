"""
owlclaw tools: コンテンツ重要度スコアリングツール。

Claude CLI (claude --print) を使い、FDE+AI専門家視点でコンテンツの重要度を
1-10でスコアリングする。出力はJSONで、score/reason/tags/priority を含む。

使い方:
  echo '{"title": "GPT-5 released", "text": "..."}' | python -m tools.score
  python -m tools.score --item '{"title": "...", "text": "...", "url": "..."}'
  python -m tools.score --batch items.json
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from typing import TypedDict


class ContentItem(TypedDict, total=False):
    """スコアリング対象のコンテンツ。"""

    title: str
    text: str
    url: str
    source: str


class ScoreResult(TypedDict):
    """スコアリング結果。"""

    score: int
    reason: str
    tags: list[str]
    priority: str


class ScoreError(Exception):
    """スコアリング失敗時の例外。"""


SCORE_PROMPT_TEMPLATE = """\
あなたはFDE（Forward Deployed Engineer）職 兼 AI専門家です。
以下のコンテンツを評価し、**JSONのみ**を出力してください（前後に説明文を書かない）。

【評価基準】
- 10: FDE業務への直接的インパクト or 重大モデル発表（GPT-5/Claude 4等）
- 7-9: AI専門家として必須の重要トレンド（業界構造変化・主要モデル動向）
- 4-6: 参考になるが即時アクション不要（一般的な技術解説・事例）
- 1-3: ノイズ・既報の焼き直し・関連性低い

【コンテンツ】
タイトル: {title}
ソース: {source}
URL: {url}
本文:
{text}

【出力形式】
JSONのみ出力すること。余分なテキスト・コードブロックは不要。

{{
  "score": <1-10の整数>,
  "reason": "<スコアの根拠を1文で>",
  "tags": ["<関連タグ1>", "<関連タグ2>"],
  "priority": "<high|medium|low>"
}}

priorityの基準: score 7以上→high, 4-6→medium, 1-3→low"""


def _invoke_claude(prompt: str) -> str:
    """Claude CLI を呼び出してテキストを返す。

    Parameters
    ----------
    prompt : str
        Claude に渡すプロンプト

    Returns
    -------
    str
        Claude の出力テキスト

    Raises
    ------
    ScoreError
        Claude CLI の呼び出しに失敗した場合
    """
    try:
        result = subprocess.run(
            ["claude", "--print", "--allowedTools", ""],
            input=prompt,
            text=True,
            capture_output=True,
            check=True,
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        raise ScoreError(
            f"Claude CLI 呼び出しに失敗しました (exit={e.returncode}): {e.stderr}"
        ) from e
    except FileNotFoundError as e:
        raise ScoreError(
            "claude コマンドが見つかりません。"
            "Claude CLI がインストールされているか確認してください。"
        ) from e


def _parse_json_output(raw: str) -> dict:
    """Claude出力からJSONを抽出・パースする。

    コードブロックや前後のテキストを除去してJSONのみを取り出す。

    Parameters
    ----------
    raw : str
        Claude の出力テキスト（JSON以外が混入していても許容）

    Returns
    -------
    dict
        パース済み辞書

    Raises
    ------
    ScoreError
        JSON抽出・パースに失敗した場合
    """
    cleaned = re.sub(r"```(?:json)?|```", "", raw).strip()
    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if not match:
        raise ScoreError(f"JSONを抽出できませんでした。出力:\n{raw}")
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError as e:
        raise ScoreError(f"JSONパースに失敗しました: {e}\n出力:\n{raw}") from e


def score_item(item: ContentItem) -> ScoreResult:
    """1件のコンテンツをスコアリングする。

    Parameters
    ----------
    item : ContentItem
        スコアリング対象

    Returns
    -------
    ScoreResult
        スコアリング結果

    Raises
    ------
    ScoreError
        スコアリング失敗時
    """
    raw_title = item.get("title")
    raw_text = item.get("text")
    if not raw_title and not raw_text:
        raise ScoreError("title または text のどちらかは必須です。")

    title = raw_title or "（タイトルなし）"
    text = raw_text or ""
    url = item.get("url", "")
    source = item.get("source", "")

    excerpt = text[:2000] if len(text) > 2000 else text
    prompt = SCORE_PROMPT_TEMPLATE.format(
        title=title,
        source=source or "不明",
        url=url or "なし",
        text=excerpt,
    )
    raw = _invoke_claude(prompt)
    data = _parse_json_output(raw)

    score = int(data.get("score", 5))
    score = max(1, min(10, score))
    priority = data.get("priority", "medium")
    if priority not in ("high", "medium", "low"):
        priority = "high" if score >= 7 else ("medium" if score >= 4 else "low")

    return ScoreResult(
        score=score,
        reason=str(data.get("reason", "")),
        tags=[str(t) for t in data.get("tags", [])],
        priority=priority,
    )


def score_batch(items: list[ContentItem]) -> list[dict]:
    """複数コンテンツをまとめてスコアリングする。

    Parameters
    ----------
    items : list[ContentItem]
        スコアリング対象リスト

    Returns
    -------
    list[dict]
        入力itemにscoreフィールドをマージしたリスト
    """
    results = []
    for i, item in enumerate(items, 1):
        print(f"スコアリング {i}/{len(items)}: {item.get('title', '?')[:50]}...", file=sys.stderr)
        try:
            score_result = score_item(item)
            results.append({**item, **score_result})
        except ScoreError as e:
            print(f"  WARNING: スコアリング失敗 — {e}", file=sys.stderr)
            results.append({**item, "score": 0, "reason": str(e), "tags": [], "priority": "low"})
    return results


def main() -> None:
    """CLIエントリーポイント。"""
    parser = argparse.ArgumentParser(
        description="コンテンツの重要度をFDE+AI専門家視点でスコアリングする",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--item",
        "-i",
        default=None,
        metavar="JSON",
        help='スコアリング対象のJSON文字列 (例: \'{"title": "...", "text": "..."}\')',
    )
    group.add_argument(
        "--batch",
        "-b",
        default=None,
        metavar="FILE",
        help="バッチスコアリング用JSONファイル (ContentItemのリスト)",
    )
    args = parser.parse_args()

    if args.batch:
        try:
            with open(args.batch, encoding="utf-8") as f:
                items = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            print(f"ERROR: バッチファイルの読み込みに失敗: {e}", file=sys.stderr)
            sys.exit(1)
        results = score_batch(items)
        print(json.dumps(results, ensure_ascii=False, indent=2))
        return

    if args.item:
        try:
            item = json.loads(args.item)
        except json.JSONDecodeError as e:
            print(f"ERROR: JSON パースに失敗: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        raw = sys.stdin.read().strip()
        if not raw:
            print(
                "ERROR: stdin が空です。--item または --batch を指定するか、"
                "stdinにJSONを渡してください。",
                file=sys.stderr,
            )
            sys.exit(1)
        try:
            item = json.loads(raw)
        except json.JSONDecodeError as e:
            print(f"ERROR: JSON パースに失敗: {e}", file=sys.stderr)
            sys.exit(1)

    try:
        result = score_item(item)
    except ScoreError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

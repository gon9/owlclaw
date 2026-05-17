"""
owlclaw tools: テキスト要約ツール。

Claude CLI (claude --print) を使って長文テキストを要約する。
テキストが長い場合は LangChain の RecursiveCharacterTextSplitter で分割し、
map-reduce パターンで要約を統合する。

使い方:
  python -m tools.summarize < transcript.txt
  cat transcript.txt | python -m tools.summarize --context "FDE視点で要点を3行で"
  python -m tools.summarize --file transcript.txt --context "Podcast要約"
"""

from __future__ import annotations

import argparse
import subprocess
import sys

from langchain_text_splitters import RecursiveCharacterTextSplitter

CHUNK_SIZE = 8000
CHUNK_OVERLAP = 200
DEFAULT_CONTEXT = (
    "あなたはFDE職+AI専門家として情報収集しています。"
    "要点を日本語で簡潔に要約してください。"
)
MAP_PROMPT_TEMPLATE = """\
以下のテキストを要約してください。

【文脈・視点】
{context}

【テキスト】
{text}

---
要点を箇条書きで3〜5点にまとめてください。日本語で出力すること。"""

REDUCE_PROMPT_TEMPLATE = """\
以下は長文テキストを複数チャンクに分割して要約したものです。
これらをまとめて最終的な要約を作成してください。

【文脈・視点】
{context}

【各チャンクの要約】
{summaries}

---
最終的な要約を日本語で出力してください（300字以内が目安）。"""


class SummarizeError(Exception):
    """要約失敗時の例外。"""


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
    SummarizeError
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
        raise SummarizeError(
            f"Claude CLI 呼び出しに失敗しました (exit={e.returncode}): {e.stderr}"
        ) from e
    except FileNotFoundError as e:
        raise SummarizeError(
            "claude コマンドが見つかりません。"
            "Claude CLI がインストールされているか確認してください。"
        ) from e


def summarize(
    text: str,
    context: str = DEFAULT_CONTEXT,
    chunk_size: int = CHUNK_SIZE,
) -> str:
    """テキストを要約する。

    テキストが chunk_size 以内なら直接要約、超えた場合は
    map-reduce パターンでチャンク分割→各チャンク要約→統合する。

    Parameters
    ----------
    text : str
        要約対象テキスト
    context : str
        要約の文脈・視点（プロンプトに埋め込まれる）
    chunk_size : int
        チャンクサイズ上限（文字数）

    Returns
    -------
    str
        要約テキスト

    Raises
    ------
    SummarizeError
        要約失敗時
    """
    if not text.strip():
        raise SummarizeError("テキストが空です。")

    if len(text) <= chunk_size:
        prompt = MAP_PROMPT_TEMPLATE.format(context=context, text=text)
        return _invoke_claude(prompt)

    overlap = min(CHUNK_OVERLAP, chunk_size // 4)
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=overlap,
        separators=["\n\n", "\n", "。", ".", " ", ""],
    )
    chunks = splitter.split_text(text)

    print(
        f"テキストを {len(chunks)} チャンクに分割して要約します ({len(text)} 文字)...",
        file=sys.stderr,
    )

    chunk_summaries: list[str] = []
    for i, chunk in enumerate(chunks, 1):
        print(f"  チャンク {i}/{len(chunks)} 要約中...", file=sys.stderr)
        prompt = MAP_PROMPT_TEMPLATE.format(context=context, text=chunk)
        summary = _invoke_claude(prompt)
        chunk_summaries.append(summary)

    summaries_text = "\n\n---\n\n".join(
        f"【チャンク{i}】\n{s}" for i, s in enumerate(chunk_summaries, 1)
    )
    reduce_prompt = REDUCE_PROMPT_TEMPLATE.format(
        context=context, summaries=summaries_text
    )
    return _invoke_claude(reduce_prompt)


def main() -> None:
    """CLIエントリーポイント。"""
    parser = argparse.ArgumentParser(
        description="テキストをClaude CLIで要約する",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--file",
        "-f",
        default=None,
        metavar="PATH",
        help="入力ファイルパス (指定なしの場合は stdin)",
    )
    parser.add_argument(
        "--context",
        "-c",
        default=DEFAULT_CONTEXT,
        help="要約の文脈・視点",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=CHUNK_SIZE,
        metavar="N",
        help=f"チャンクサイズ上限（文字数）(デフォルト: {CHUNK_SIZE})",
    )
    args = parser.parse_args()

    if args.file:
        try:
            with open(args.file, encoding="utf-8") as f:
                text = f.read()
        except OSError as e:
            print(f"ERROR: ファイルを読み込めません: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        text = sys.stdin.read()

    try:
        result = summarize(text, context=args.context, chunk_size=args.chunk_size)
    except SummarizeError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    print(result)


if __name__ == "__main__":
    main()

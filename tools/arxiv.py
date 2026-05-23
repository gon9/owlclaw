"""
owlclaw tools: arXiv論文取得ツール。

arxiv パッケージを使い、論文メタデータ+Abstractを取得する。
langchain-community の ArxivLoader も内部で利用可能。

使い方:
  python -m tools.arxiv "LLM agent reasoning" --max-results 5
  python -m tools.arxiv --paper-id 2312.00001
  python -m tools.arxiv "GPT" --categories cs.AI cs.CL --days 7
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import UTC, datetime, timedelta
from typing import TypedDict

import arxiv

DEFAULT_CATEGORIES = ["cs.AI", "cs.CL", "cs.LG"]
REQUEST_SLEEP_SEC = 0.5


class PaperResult(TypedDict):
    """論文取得結果。"""

    paper_id: str
    title: str
    authors: list[str]
    published: str
    abstract: str
    url: str
    pdf_url: str
    categories: list[str]


class ArxivError(Exception):
    """arXiv取得失敗時の例外。"""


def _paper_to_result(paper: arxiv.Result) -> PaperResult:
    """arxiv.Result を PaperResult に変換する。"""
    paper_id = paper.get_short_id()
    return PaperResult(
        paper_id=paper_id,
        title=paper.title.strip(),
        authors=[str(a) for a in paper.authors],
        published=paper.published.strftime("%Y-%m-%d") if paper.published else "",
        abstract=paper.summary.strip(),
        url=f"https://arxiv.org/abs/{paper_id}",
        pdf_url=paper.pdf_url or "",
        categories=paper.categories or [],
    )


def search_papers(
    query: str,
    max_results: int = 10,
    categories: list[str] | None = None,
    days: int | None = None,
) -> list[PaperResult]:
    """arXivでキーワード検索して論文リストを返す。

    Parameters
    ----------
    query : str
        検索クエリ
    max_results : int
        最大取得件数
    categories : list[str] | None
        カテゴリフィルタ。Noneの場合はデフォルトカテゴリを使用
    days : int | None
        直近N日間に絞り込む。Noneの場合は絞り込まない

    Returns
    -------
    list[PaperResult]
        論文リスト

    Raises
    ------
    ArxivError
        取得失敗時
    """
    cats = categories or DEFAULT_CATEGORIES
    cat_filter = " OR ".join(f"cat:{c}" for c in cats)
    full_query = f"({query}) AND ({cat_filter})"

    try:
        client = arxiv.Client(num_retries=3, delay_seconds=REQUEST_SLEEP_SEC)
        search = arxiv.Search(
            query=full_query,
            max_results=max_results,
            sort_by=arxiv.SortCriterion.SubmittedDate,
            sort_order=arxiv.SortOrder.Descending,
        )
        results = list(client.results(search))
    except Exception as e:
        raise ArxivError(f"arXiv検索に失敗しました: {e}") from e

    papers = [_paper_to_result(r) for r in results]

    if days is not None:
        cutoff = datetime.now(UTC) - timedelta(days=days)
        papers = [
            p for p in papers
            if p["published"]
            and datetime.fromisoformat(p["published"]).replace(tzinfo=UTC) >= cutoff
        ]

    time.sleep(REQUEST_SLEEP_SEC)
    return papers


def fetch_paper(paper_id: str) -> PaperResult:
    """arXiv IDを指定して1件の論文を取得する。

    Parameters
    ----------
    paper_id : str
        arXiv ID (例: "2401.00001" or "2401.00001v2")

    Returns
    -------
    PaperResult
        論文情報

    Raises
    ------
    ArxivError
        取得失敗または論文が存在しない場合
    """
    try:
        client = arxiv.Client(num_retries=3, delay_seconds=REQUEST_SLEEP_SEC)
        search = arxiv.Search(id_list=[paper_id])
        results = list(client.results(search))
    except Exception as e:
        raise ArxivError(f"論文取得に失敗しました (id={paper_id}): {e}") from e

    if not results:
        raise ArxivError(f"論文が見つかりません: {paper_id}")

    return _paper_to_result(results[0])


def main() -> None:
    """CLIエントリーポイント。"""
    parser = argparse.ArgumentParser(
        description="arXivから論文を取得する",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("query", nargs="?", help="検索クエリ")
    group.add_argument("--paper-id", metavar="ID", help="arXiv ID (例: 2401.00001)")
    parser.add_argument(
        "--max-results",
        type=int,
        default=10,
        metavar="N",
        help="最大取得件数 (デフォルト: 10)",
    )
    parser.add_argument(
        "--categories",
        nargs="+",
        default=None,
        metavar="CAT",
        help=f"カテゴリフィルタ (デフォルト: {' '.join(DEFAULT_CATEGORIES)})",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=None,
        metavar="N",
        help="直近N日間に絞り込む",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="output_json",
        help="JSON形式で出力",
    )
    args = parser.parse_args()

    try:
        if args.paper_id:
            results = [fetch_paper(args.paper_id)]
        else:
            results = search_papers(
                args.query,
                max_results=args.max_results,
                categories=args.categories,
                days=args.days,
            )
    except ArxivError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    if args.output_json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        for i, p in enumerate(results, 1):
            print(f"[{i}] {p['title']}")
            print(f"     {p['published']} | {', '.join(p['categories'])}")
            print(f"     {p['url']}")
            print(f"     {p['abstract'][:200]}...")
            print()


if __name__ == "__main__":
    main()

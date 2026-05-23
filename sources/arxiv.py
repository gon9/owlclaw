"""
owlclaw: arXiv論文ソースプラグイン。

tools/arxiv.py をラップして BaseSource インターフェースに適合させる。
タスク YAML の sources セクションで type: arxiv として指定して使用する。

設定例 (tasks/*.yaml):
  sources:
    - type: arxiv
      query: "LLM agent reasoning"
      categories: ["cs.AI", "cs.CL"]
      days: 7
      max_results: 10
"""

from __future__ import annotations

import sys
from datetime import datetime

from sources.base import BaseSource
from tools.arxiv import DEFAULT_CATEGORIES, ArxivError, fetch_paper, search_papers


class ArxivSource(BaseSource):
    """arXiv論文取得ソースプラグイン。"""

    def fetch(
        self,
        config: dict,
        cutoff: datetime,
        last_seen_per_source: dict | None = None,
    ) -> tuple[str, dict]:
        """arXivから論文を取得してMarkdownを返す。

        Parameters
        ----------
        config : dict
            ソース設定。有効キー:
              - query (str): 検索クエリ (paper_id 未指定時は必須)
              - paper_id (str): arXiv ID で1件取得 (query より優先)
              - categories (list[str]): カテゴリフィルタ
              - days (int): 直近N日に絞り込み
              - max_results (int): 最大取得件数 (デフォルト: 10)
        cutoff : datetime
            使用しない (days パラメータで代替)
        last_seen_per_source : dict | None
            使用しない

        Returns
        -------
        tuple[str, dict]
            (Markdownテキスト, {})
        """
        paper_id: str | None = config.get("paper_id")
        query: str = config.get("query", "LLM AI agent")
        categories: list[str] | None = config.get("categories")
        days: int | None = config.get("days")
        max_results: int = int(config.get("max_results", 10))

        if categories is None:
            categories = DEFAULT_CATEGORIES

        label = f"arXiv: {paper_id}" if paper_id else f"arXiv: {query}"
        try:
            if paper_id:
                papers = [fetch_paper(paper_id)]
            else:
                papers = search_papers(
                    query,
                    max_results=max_results,
                    categories=categories,
                    days=days,
                )
        except ArxivError as e:
            print(f"  [arXiv] エラー: {e}", file=sys.stderr)
            return f"## {label}\n\n*(取得エラー: {e})*\n", {}

        print(f"  [arXiv] {len(papers)} 件取得", file=sys.stderr)

        lines = [f"## {label} ({len(papers)}件)\n"]
        if not papers:
            lines.append("*(該当論文なし)*\n")
            return "\n".join(lines), {}

        for i, p in enumerate(papers, 1):
            authors = ", ".join(p["authors"][:3])
            if len(p["authors"]) > 3:
                authors += " et al."
            abstract_excerpt = (
                p["abstract"][:400] + "..." if len(p["abstract"]) > 400 else p["abstract"]
            )
            lines.append(f"### {i}. {p['title']}")
            lines.append(f"- URL: {p['url']}")
            lines.append(f"- Date: {p['published']}")
            lines.append(f"- Authors: {authors}")
            lines.append(f"- Categories: {', '.join(p['categories'])}")
            lines.append(f"- Abstract: {abstract_excerpt}")
            lines.append("")

        return "\n".join(lines), {}

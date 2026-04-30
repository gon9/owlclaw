"""
owlclaw: RSSソースプラグイン。

config/sources.yaml の enabled=true ソースをすべて fetch し、
cutoff 以降の記事を Markdown 文字列で返す。
"""

import html
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from datetime import UTC, datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

from sources.base import BaseSource

MAX_PER_SOURCE = 10
EXCERPT_LEN = 200
JST = timezone(timedelta(hours=9))


def _clean(text: str) -> str:
    """HTMLタグ・エンティティを除去し、空白を正規化して返す。"""
    text = html.unescape(text)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _parse_pub_date(raw: str) -> datetime | None:
    """RSS pubDate / Atom updated 文字列をdatetimeに変換する。失敗時はNoneを返す。"""
    if not raw:
        return None
    iso_parser = lambda s: datetime.fromisoformat(s.rstrip("Z").split(".")[0])  # noqa: E731
    for parser in (parsedate_to_datetime, iso_parser):
        try:
            dt = parser(raw)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=UTC)
            return dt
        except Exception:
            continue
    return None


def _fetch_feed(url: str, name: str, cutoff: datetime) -> list[dict]:
    """指定URLのRSS/Atomフィードを取得し、cutoff以降の記事をリストで返す。"""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "owlclaw/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            content = resp.read()
    except Exception as e:
        print(f"  SKIP {name}: {e}", file=sys.stderr)
        return []

    try:
        root = ET.fromstring(content)
    except ET.ParseError as e:
        print(f"  PARSE ERROR {name}: {e}", file=sys.stderr)
        return []

    ns = {"atom": "http://www.w3.org/2005/Atom"}
    items: list[dict] = []

    for item in root.findall(".//item"):
        title = _clean(item.findtext("title") or "")
        link = (item.findtext("link") or "").strip()
        desc = _clean(item.findtext("description") or "")[:EXCERPT_LEN]
        raw_pub = item.findtext("pubDate") or ""
        pub_dt = _parse_pub_date(raw_pub)
        if title and link:
            items.append({"title": title, "url": link, "excerpt": desc,
                          "pub_dt": pub_dt, "pub": raw_pub[:16]})

    for entry in root.findall("atom:entry", ns):
        title = _clean(entry.findtext("atom:title", namespaces=ns) or "")
        link_el = entry.find("atom:link", ns)
        link = (link_el.get("href", "") if link_el is not None else "").strip()
        desc = _clean(entry.findtext("atom:summary", namespaces=ns) or "")[:EXCERPT_LEN]
        raw_pub = entry.findtext("atom:updated", namespaces=ns) or ""
        pub_dt = _parse_pub_date(raw_pub)
        if title and link:
            items.append({"title": title, "url": link, "excerpt": desc,
                          "pub_dt": pub_dt, "pub": raw_pub[:16]})

    filtered = [it for it in items if it["pub_dt"] is None or it["pub_dt"] >= cutoff]
    return filtered[:MAX_PER_SOURCE]


class RssSource(BaseSource):
    """RSSフィードソースプラグイン。"""

    def fetch(
        self,
        config: dict,
        cutoff: datetime,
        last_seen_per_source: dict | None = None,
    ) -> tuple[str, dict]:
        """
        設定された全RSSフィードを取得し、(Markdown文字列, 最終既読辞書) を返す。

        Parameters
        ----------
        config : dict
            sources.yaml のパース済み辞書。
            "_source_filter" キーがあればそのソース名リストのみ対象にする。
        cutoff : datetime
            グローバル閾値（UTC aware）
        last_seen_per_source : dict | None
            {source_name: iso_str} — 指定時は各ソースで max(cutoff, last_seen) を使用

        Returns
        -------
        tuple[str, dict]
            (Markdown テキスト, {source_name: latest_pub_iso_str})
        """
        digest_cfg = config.get("digest", {})
        lookback_hours: int = digest_cfg.get("lookback_hours", 24)
        persona: str = digest_cfg.get("persona", "日本SaaS企業の社員。")
        source_filter: list[str] | None = config.get("source_filter")

        all_sources = [s for s in config.get("sources", []) if s.get("enabled") and s.get("url")]
        sources = (
            [s for s in all_sources if s["name"] in source_filter]
            if source_filter
            else all_sources
        )

        today = datetime.now(UTC).astimezone(JST).strftime("%Y-%m-%d")

        lines = [
            f"# owlclaw digest input — {today}",
            "",
            f"読者ペルソナ: {persona.strip()}",
            f"取得対象期間: 過去{lookback_hours}時間以内"
            f" (global cutoff: {cutoff.strftime('%Y-%m-%d %H:%M')} UTC)",
            "",
            "---",
            "",
        ]

        total = 0
        latest_seen: dict[str, str] = {}

        for s in sources:
            name = s["name"]

            # per-source 有効カットオフ: last_seen があれば max(cutoff, last_seen) を使用
            effective_cutoff = cutoff
            if last_seen_per_source and name in last_seen_per_source:
                try:
                    ls_dt = datetime.fromisoformat(last_seen_per_source[name])
                    if ls_dt.tzinfo is None:
                        ls_dt = ls_dt.replace(tzinfo=UTC)
                    effective_cutoff = max(cutoff, ls_dt)
                except ValueError:
                    pass

            print(f"Fetching {name} ...", file=sys.stderr)
            items = _fetch_feed(s["url"], name, effective_cutoff)
            print(f"  → {len(items)} items", file=sys.stderr)
            total += len(items)

            # 各ソースの最新記事日時を記録
            for it in items:
                if it["pub_dt"]:
                    current = latest_seen.get(name)
                    if current is None or it["pub_dt"] > datetime.fromisoformat(current).replace(
                        tzinfo=UTC
                    ):
                        latest_seen[name] = it["pub_dt"].isoformat()

            lines.append(f"## {name} ({len(items)}件)")
            if not items:
                lines.append("*(取得できませんでした)*")
                lines.append("")
                continue
            for i, it in enumerate(items, 1):
                lines.append(f"### {i}. {it['title']}")
                lines.append(f"- URL: {it['url']}")
                lines.append(f"- Date: {it['pub']}")
                if it["excerpt"]:
                    lines.append(f"- Excerpt: {it['excerpt']}")
                lines.append("")

        lines += [
            "---",
            f"合計 {total} 件。上記から最大10件を選んでキュレーション・日本語要約してください。",
        ]

        print(f"✓ Fetched {total} items total", file=sys.stderr)
        return "\n".join(lines), latest_seen

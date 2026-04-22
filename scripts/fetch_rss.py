#!/usr/bin/env python3
"""
owlclaw: RSSフェッチ & 整形スクリプト。

config/sources.yaml の enabled=true ソースをすべて取得し、
lookback_hours 以内の記事をMarkdown形式で tmp/digest_input.md に出力する。
Claude は このファイルを Read するだけでよい。Python/JSONの処理は不要。
"""

import html
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from datetime import UTC, datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

import yaml

CONFIG_PATH = Path(__file__).parent.parent / "config" / "sources.yaml"
OUTPUT_PATH = Path(__file__).parent.parent / "tmp" / "digest_input.md"
MAX_PER_SOURCE = 10
EXCERPT_LEN = 200

JST = timezone(timedelta(hours=9))


def load_config(path: Path) -> dict:
    """YAMLコンフィグを読み込み辞書として返す。"""
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def get_enabled_sources(config: dict) -> list[dict]:
    """enabled=true かつ url が存在するソース一覧を返す。"""
    return [s for s in config.get("sources", []) if s.get("enabled") and s.get("url")]


def clean(text: str) -> str:
    """HTMLタグ・エンティティを除去し、空白を正規化して返す。"""
    text = html.unescape(text)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def parse_pub_date(raw: str) -> datetime | None:
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


def fetch_feed(url: str, name: str, cutoff: datetime) -> list[dict]:
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
    items = []

    for item in root.findall(".//item"):
        title = clean(item.findtext("title") or "")
        link = (item.findtext("link") or "").strip()
        desc = clean(item.findtext("description") or "")[:EXCERPT_LEN]
        raw_pub = item.findtext("pubDate") or ""
        pub_dt = parse_pub_date(raw_pub)
        if title and link:
            items.append({"title": title, "url": link, "excerpt": desc,
                          "pub_dt": pub_dt, "pub": raw_pub[:16]})

    for entry in root.findall("atom:entry", ns):
        title = clean(entry.findtext("atom:title", namespaces=ns) or "")
        link_el = entry.find("atom:link", ns)
        link = (link_el.get("href", "") if link_el is not None else "").strip()
        desc = clean(entry.findtext("atom:summary", namespaces=ns) or "")[:EXCERPT_LEN]
        raw_pub = entry.findtext("atom:updated", namespaces=ns) or ""
        pub_dt = parse_pub_date(raw_pub)
        if title and link:
            items.append({"title": title, "url": link, "excerpt": desc,
                          "pub_dt": pub_dt, "pub": raw_pub[:16]})

    filtered = [it for it in items if it["pub_dt"] is None or it["pub_dt"] >= cutoff]
    return filtered[:MAX_PER_SOURCE]


def main() -> None:
    """メインエントリーポイント。RSSフェッチ結果をMarkdownファイルに書き出す。"""
    config = load_config(CONFIG_PATH)
    sources = get_enabled_sources(config)
    lookback_hours: int = config.get("digest", {}).get("lookback_hours", 24)
    persona: str = config.get("digest", {}).get("persona", "日本SaaS企業の社員。")

    now = datetime.now(UTC)
    cutoff = now - timedelta(hours=lookback_hours)
    today = now.astimezone(JST).strftime("%Y-%m-%d")

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    lines = [
        f"# owlclaw digest input — {today}",
        "",
        f"読者ペルソナ: {persona.strip()}",
        f"取得対象期間: 過去{lookback_hours}時間以内"
        f" (cutoff: {cutoff.strftime('%Y-%m-%d %H:%M')} UTC)",
        "",
        "---",
        "",
    ]

    total = 0
    for s in sources:
        name = s["name"]
        print(f"Fetching {name} ...", file=sys.stderr)
        items = fetch_feed(s["url"], name, cutoff)
        print(f"  → {len(items)} items", file=sys.stderr)
        total += len(items)

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
        f"合計 {total} 件。上記から最大6件を選んでキュレーション・日本語要約してください。",
    ]

    OUTPUT_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"✓ Written {total} items → {OUTPUT_PATH}", file=sys.stderr)


if __name__ == "__main__":
    main()

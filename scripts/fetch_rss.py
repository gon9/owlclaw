#!/usr/bin/env python3
"""
owlclaw: RSSフェッチ & 整形スクリプト
- config/sources.yaml の enabled=true ソースをすべて取得
- ソースごと最新10件に絞り込み
- Claudeが Read ツールで直接読めるMarkdown形式で出力
  → /Users/gon9a/workspace/ai_agent/owlclaw/tmp/digest_input.md

Claude はこのファイルを Read するだけでよい。Python/JSONの処理は不要。
"""

import sys
import urllib.request
import xml.etree.ElementTree as ET
import re
import html
from datetime import datetime, timezone, timedelta
from pathlib import Path

CONFIG_PATH = Path(__file__).parent.parent / "config" / "sources.yaml"
OUTPUT_PATH = Path(__file__).parent.parent / "tmp" / "digest_input.md"
MAX_PER_SOURCE = 10
EXCERPT_LEN = 200

JST = timezone(timedelta(hours=9))


def parse_sources(path: Path) -> list[dict]:
    sources = []
    current = {}
    in_sources = False
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped == "sources:":
            in_sources = True
            continue
        if not in_sources:
            continue
        m = re.match(r"^\s{2}- name:\s*(.+)", line)
        if m:
            if current:
                sources.append(current)
            current = {"name": m.group(1).strip()}
            continue
        m = re.match(r"^\s{4}url:\s*([^\s#]+)", line)
        if m:
            current["url"] = m.group(1).strip()
            continue
        m = re.match(r"^\s{4}enabled:\s*(true|false)", line)
        if m:
            current["enabled"] = m.group(1) == "true"
            continue
    if current:
        sources.append(current)
    return [s for s in sources if s.get("enabled") and s.get("url")]


def clean(text: str) -> str:
    text = html.unescape(text)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def fetch_feed(url: str, name: str) -> list[dict]:
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
        link  = (item.findtext("link") or "").strip()
        desc  = clean(item.findtext("description") or "")[:EXCERPT_LEN]
        pub   = (item.findtext("pubDate") or "")[:16]
        if title and link:
            items.append({"title": title, "url": link, "excerpt": desc, "pub": pub})

    for entry in root.findall("atom:entry", ns):
        title = clean(entry.findtext("atom:title", namespaces=ns) or "")
        link_el = entry.find("atom:link", ns)
        link  = (link_el.get("href", "") if link_el is not None else "").strip()
        desc  = clean(entry.findtext("atom:summary", namespaces=ns) or "")[:EXCERPT_LEN]
        pub   = (entry.findtext("atom:updated", namespaces=ns) or "")[:16]
        if title and link:
            items.append({"title": title, "url": link, "excerpt": desc, "pub": pub})

    return items[:MAX_PER_SOURCE]


def main():
    config = parse_sources(CONFIG_PATH)
    today = datetime.now(JST).strftime("%Y-%m-%d")

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    lines = []
    lines.append(f"# owlclaw digest input — {today}")
    lines.append("")
    lines.append("読者ペルソナ: ナレッジワーク（日本SaaS）社員。AI業界トレンド・海外組織モデル（FDE等）・SaaS示唆に関心。")
    lines.append("")
    lines.append("---")
    lines.append("")

    total = 0
    for s in config:
        name = s["name"]
        print(f"Fetching {name} ...", file=sys.stderr)
        items = fetch_feed(s["url"], name)
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

    lines.append("---")
    lines.append(f"合計 {total} 件。上記から最大6件を選んでキュレーション・日本語要約してください。")

    OUTPUT_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"✓ Written {total} items → {OUTPUT_PATH}", file=sys.stderr)


if __name__ == "__main__":
    main()

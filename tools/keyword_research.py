#!/usr/bin/env python3
"""Fetches the Iranian Google result page for a list of queries.

WHY IT EXISTS
-------------
Topics were being picked from an impression of what search returns. This
records what search actually returns — the pages already ranking, the
questions Google itself lists, and the related searches — so a topic can be
chosen against evidence and the evidence stays in the repository.

WHY IT PARSES HTML RATHER THAN CALLING A TIDY API
-------------------------------------------------
The SERP is fetched through Bright Data's unlocker, which returns the page as
the browser would see it. Google's markup is not a contract, so every
extractor here is written to return nothing rather than raise: a query whose
shape changed produces an empty list next to a saved html_bytes count, which
is enough to see that the parser slipped rather than the query being empty.

Run by .github/workflows/keyword-research.yml. Needs BRIGHTDATA_API_KEY.
"""

from __future__ import annotations

import html
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "research"
ENDPOINT = "https://api.brightdata.com/request"

# Iran, Persian, one page deep. num=20 gives enough of a picture without
# paging; anything past the first twenty is not what a topic competes with.
SERP = ("https://www.google.com/search"
        "?q={q}&gl=ir&hl=fa&num=20&pws=0")

DEFAULT_QUERIES = [
    "هوش مصنوعی برای کسب و کار ایرانی",
    "چت بات فارسی برای فروش",
    "پیگیری خودکار مشتری",
    "دستیار هوش مصنوعی واتساپ فارسی",
    "هوش مصنوعی برای کلینیک زیبایی",
]


def queries_from_env() -> list[str]:
    raw = (os.environ.get("QUERIES") or "").strip()
    if not raw:
        return DEFAULT_QUERIES
    out = [q.strip() for q in raw.split(";")]
    return [q for q in out if q] or DEFAULT_QUERIES


def fetch(query: str, key: str, zone: str) -> str:
    body = json.dumps({
        "zone": zone,
        "url": SERP.format(q=urllib.parse.quote_plus(query)),
        "format": "raw",
    }).encode()
    req = urllib.request.Request(
        ENDPOINT, data=body, method="POST",
        headers={"Authorization": f"Bearer {key}",
                 "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read().decode("utf-8", "replace")


def _clean(s: str) -> str:
    s = re.sub(r"<[^>]+>", "", s)
    return html.unescape(s).strip()


def organic(page: str) -> list[dict]:
    """Result titles and the site they point at, in order."""
    out, seen = [], set()
    # An <a href="/url?q=..."> or a direct https href wrapping an <h3>.
    for m in re.finditer(r'<a[^>]+href="(https?://[^"]+)"[^>]*>.*?<h3[^>]*>(.*?)</h3>',
                         page, re.S):
        url, title = m.group(1), _clean(m.group(2))
        host = urllib.parse.urlparse(url).netloc.lower()
        if not title or "google." in host or host in seen:
            continue
        seen.add(host)
        out.append({"title": title[:160], "url": url[:300], "site": host})
        if len(out) >= 20:
            break
    return out


def people_also_ask(page: str) -> list[str]:
    """The questions Google prints itself — each one is a heading someone
    should be able to answer in a single section."""
    found, seen = [], set()
    for m in re.finditer(r'data-q="([^"]{8,180})"', page):
        q = html.unescape(m.group(1)).strip()
        if q and q not in seen:
            seen.add(q)
            found.append(q)
    return found[:12]


def related(page: str) -> list[str]:
    out, seen = [], set()
    # q= may be the first parameter or a later one; the old form required a
    # preceding & and so matched nothing at all.
    for m in re.finditer(r'/search\?(?:[^"]*?&)?q=([^"&]{4,120})', page):
        term = urllib.parse.unquote_plus(m.group(1)).strip()
        if (len(term) > 3 and term not in seen
                and not term.startswith("http") and "site:" not in term):
            seen.add(term)
            out.append(term)
    return out[:20]


def main() -> int:
    key = os.environ.get("BRIGHTDATA_API_KEY", "").strip()
    if not key:
        print("BRIGHTDATA_API_KEY missing", file=sys.stderr)
        return 1
    zone = os.environ.get("BRIGHTDATA_ZONE", "cli_unlocker").strip() or "cli_unlocker"

    results = []
    for q in queries_from_env():
        record: dict = {"query": q}
        try:
            page = fetch(q, key, zone)
            record.update({
                "html_bytes": len(page),
                "organic": organic(page),
                "people_also_ask": people_also_ask(page),
                "related": related(page),
            })
            print(f"✓ {q} — {len(record['organic'])} نتیجه، "
                  f"{len(record['people_also_ask'])} پرسش")
        except urllib.error.HTTPError as e:
            record["error"] = f"HTTP {e.code}"
            print(f"✗ {q} — HTTP {e.code}", file=sys.stderr)
        except Exception as e:                       # noqa: BLE001
            record["error"] = type(e).__name__
            print(f"✗ {q} — {type(e).__name__}", file=sys.stderr)
        results.append(record)
        time.sleep(2)   # courteous spacing between lookups

    OUT_DIR.mkdir(exist_ok=True)
    stamp = date.today().isoformat()
    payload = {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "market": "gl=ir, hl=fa",
        "results": results,
    }
    (OUT_DIR / f"serp-{stamp}.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [f"# عکس فوری نتایج جستجو — {stamp}", "",
             "برداشته‌شده از گوگل ایران (فارسی). این فایل برای انتخاب موضوع است، نه یک صفحه‌ی سایت.", ""]
    for r in results:
        lines.append(f"## {r['query']}")
        if r.get("error"):
            lines.append(f"خطا: {r['error']}")
            lines.append("")
            continue
        lines.append("")
        lines.append("**چه کسانی رتبه دارند**")
        for i, o in enumerate(r.get("organic", [])[:10], 1):
            lines.append(f"{i}. {o['title']} — `{o['site']}`")
        if r.get("people_also_ask"):
            lines.append("")
            lines.append("**پرسش‌هایی که خود گوگل فهرست می‌کند**")
            for q in r["people_also_ask"]:
                lines.append(f"- {q}")
        if r.get("related"):
            lines.append("")
            lines.append("**جستجوهای مرتبط**")
            lines.append("، ".join(r["related"][:12]))
        lines.append("")
    (OUT_DIR / "latest.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"نوشته شد: research/serp-{stamp}.json و research/latest.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

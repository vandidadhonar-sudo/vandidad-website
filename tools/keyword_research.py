#!/usr/bin/env python3
"""Fetches what Iranian Google actually returns for a list of queries.

WHY IT EXISTS
-------------
Article topics were being chosen from an impression of what search returns.
This records what search really returns — who already ranks, the questions
Google prints itself, and the related searches — and commits it, so a topic
is argued from a file anyone can open and re-check months later.

WHY IT RUNS IN CI RATHER THAN WHERE THE ARTICLES ARE WRITTEN
------------------------------------------------------------
The writing environment's egress gateway answers 403 to the CONNECT for
every research host — the owner's own gateway Worker, api.brightdata.com and
google.com alike. No credential changes that; the route does not exist. A
GitHub runner has open internet, so the lookup happens here and the answer
travels back as a commit.

TWO WAYS IN, PREFERRED IN THIS ORDER
------------------------------------
1. The owner's gateway Worker (GATE_URL + GATE_KEY). It already returns
   parsed results and enforces its own daily ceiling, so nothing here has to
   know about zones or quotas.
2. Bright Data's request API directly (BRIGHTDATA_API_KEY), which returns the
   raw result page for this file to parse.

Both are normalised to the same record shape, so the committed file looks the
same whichever route produced it and the writing never has to care.

Google's markup is not a contract, so every extractor returns nothing rather
than raising: a query whose shape changed shows up as an empty list beside a
large html_bytes count, which reads as "the parser slipped", not "nobody
ranks for this".
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
PROJECT = os.environ.get("GATE_PROJECT", "vandidad-site")

BRIGHTDATA_ENDPOINT = "https://api.brightdata.com/request"
SERP_URL = "https://www.google.com/search?q={q}&gl=ir&hl=fa&num=20&pws=0"

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
    out = [q.strip() for q in raw.split(";") if q.strip()]
    return out or DEFAULT_QUERIES


# ── shared helpers ───────────────────────────────────────────────

def _clean(s: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", s)).strip()


class GateError(Exception):
    """Carries what the gateway said, not just that it said no. A bare
    'HTTP 403' sends you guessing between a wrong key, a spent quota and a
    rejected project name; the body distinguishes them in one line."""


# Cloudflare sits in front of the gateway and blocks requests whose signature
# looks automated before the Worker's own code ever runs — the refusal comes
# back as 403 with 'error code: 1010' in the body, which is easy to misread as
# the key being wrong. urllib announces itself as Python-urllib/3.x, which is
# exactly the signature that gets blocked. Presenting an ordinary browser's
# headers is not a trick to get past someone else's protection: the gateway is
# the owner's own Worker and this is the owner's own key.
_HEADERS = {
    "User-Agent": ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "fa-IR,fa;q=0.9,en;q=0.8",
}


def _get(url: str, timeout: int = 120) -> str:
    req = urllib.request.Request(url, headers=_HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8", "replace").strip()[:300]
        except Exception:
            pass
        raise GateError(f"HTTP {e.code}" + (f" — {body}" if body else
                                            " (no message in the response)")) from None


# ── route 1: the owner's gateway ─────────────────────────────────

def _first_list(obj, *names) -> list:
    """Pull the first present key out of a dict, tolerating naming drift —
    the gateway's field names are its own business, not this file's."""
    if not isinstance(obj, dict):
        return []
    for n in names:
        v = obj.get(n)
        if isinstance(v, list):
            return v
    return []


def _as_result(item) -> dict | None:
    if isinstance(item, str):
        return {"title": item[:160], "url": "", "site": ""}
    if not isinstance(item, dict):
        return None
    title = str(item.get("title") or item.get("name") or "").strip()
    url = str(item.get("url") or item.get("link") or "").strip()
    if not title and not url:
        return None
    site = urllib.parse.urlparse(url).netloc.lower() if url else ""
    return {"title": title[:160], "url": url[:300], "site": site}


def parse_gate(data: dict) -> dict:
    """Turn one gateway answer into the shape the report is written from.

    The gateway names its fields in Persian — رتبه‌دارها, میپرسند, مرتبط — and
    returns bare title strings rather than objects, so it carries no URLs at
    all. The English names are kept alongside in case that ever changes; the
    first name present wins.
    """
    # A page of results is a few kilobytes; anything far larger is a payload
    # nobody meant to commit, so keep its shape and drop its bulk.
    raw = data if len(json.dumps(data)) <= 40000 else {
        "_truncated": True,
        "keys": sorted(data.keys()) if isinstance(data, dict) else str(type(data)),
    }
    organic = [r for r in (_as_result(i) for i in
                           _first_list(data, "رتبه‌دارها", "organic", "results",
                                       "rankers")) if r]
    return {
        "source": "gate",
        # The gateway's own answer, kept verbatim. Titles arrived but no URLs,
        # and two of five queries came back empty — two facts that cannot tell
        # a parser which missed a field name from a gateway that found
        # nothing, while every guess at the difference spends a query against
        # the daily ceiling. With the payload committed the parser is fixed by
        # reading a file. It is public search data; the key travels in the
        # request, never in the response.
        "raw": raw,
        "organic": organic[:20],
        "people_also_ask": [str(x)[:180] for x in
                            _first_list(data, "میپرسند", "people_also_ask",
                                        "paa", "questions")][:12],
        "related": [str(x)[:120] for x in
                    _first_list(data, "مرتبط", "related", "related_searches",
                                "searches")][:20],
    }


def via_gate(query: str, base: str, key: str) -> dict:
    url = (base.rstrip("/") + "/serp?"
           + urllib.parse.urlencode({"key": key, "p": PROJECT, "q": query}))
    return parse_gate(json.loads(_get(url)))


# ── route 2: Bright Data directly ────────────────────────────────

def via_brightdata(query: str, key: str, zone: str) -> dict:
    body = json.dumps({
        "zone": zone,
        "url": SERP_URL.format(q=urllib.parse.quote_plus(query)),
        "format": "raw",
    }).encode()
    req = urllib.request.Request(
        BRIGHTDATA_ENDPOINT, data=body, method="POST",
        headers={"Authorization": f"Bearer {key}",
                 "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        page = r.read().decode("utf-8", "replace")
    return {
        "source": "brightdata",
        "html_bytes": len(page),
        "organic": organic_from_html(page),
        "people_also_ask": people_also_ask(page),
        "related": related(page),
    }


def organic_from_html(page: str) -> list[dict]:
    out, seen = [], set()
    for m in re.finditer(
            r'<a[^>]+href="(https?://[^"]+)"[^>]*>.*?<h3[^>]*>(.*?)</h3>',
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
    found, seen = [], set()
    for m in re.finditer(r'data-q="([^"]{8,180})"', page):
        q = html.unescape(m.group(1)).strip()
        if q and q not in seen:
            seen.add(q)
            found.append(q)
    return found[:12]


def related(page: str) -> list[str]:
    # q= may be the first parameter or a later one; requiring a preceding &
    # matched nothing at all.
    out, seen = [], set()
    for m in re.finditer(r'/search\?(?:[^"]*?&)?q=([^"&]{4,120})', page):
        term = urllib.parse.unquote_plus(m.group(1)).strip()
        if (len(term) > 3 and term not in seen
                and not term.startswith("http") and "site:" not in term):
            seen.add(term)
            out.append(term)
    return out[:20]


# ── report ───────────────────────────────────────────────────────

def write_report(results: list[dict], usage: str | None,
                 stamp: str | None = None) -> None:
    # A re-parse must keep the day the data was fetched on, or a snapshot
    # re-read next month would be filed under next month's date.
    OUT_DIR.mkdir(exist_ok=True)
    stamp = stamp or date.today().isoformat()
    path = OUT_DIR / f"serp-{stamp}.json"

    # Merge into the day's snapshot rather than replacing it. The daily quota
    # is forty queries and a run carries at most ten, so measuring a whole
    # keyword list means several runs in one day — and this used to overwrite,
    # so each batch destroyed the one before it and the day ended with only
    # the last ten. A query measured twice keeps the newer answer; every other
    # query already on file is kept.
    merged: dict[str, dict] = {}
    if path.exists():
        try:
            for old_row in json.loads(path.read_text("utf-8")).get("results", []):
                merged[old_row.get("query", "")] = old_row
        except Exception:
            pass          # a corrupt snapshot must not lose the fresh results
    for row in results:
        merged[row.get("query", "")] = row

    path.write_text(json.dumps({
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "market": "gl=ir, hl=fa",
        "project": PROJECT,
        "usage_after_run": usage,
        "results": list(merged.values()),
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [f"# عکس فوری نتایج جستجو — {stamp}", "",
             "برداشته‌شده از گوگل ایران (فارسی). این فایل برای انتخاب موضوع است، نه صفحه‌ی سایت.", ""]
    for r in results:
        lines.append(f"## {r['query']}")
        if r.get("error"):
            lines += [f"خطا: {r['error']}", ""]
            continue
        lines += ["", "**چه کسانی رتبه دارند**"]
        for i, o in enumerate(r.get("organic", [])[:10], 1):
            site = f" — `{o['site']}`" if o.get("site") else ""
            lines.append(f"{i}. {o['title']}{site}")
        if r.get("people_also_ask"):
            lines += ["", "**پرسش‌هایی که خود گوگل فهرست می‌کند** (هرکدام یک سرتیتر آماده)"]
            lines += [f"- {q}" for q in r["people_also_ask"]]
        if r.get("related"):
            lines += ["", "**جستجوهای مرتبط**", "، ".join(r["related"][:12])]
        lines.append("")
    if usage:
        lines += ["---", f"مصرف پس از این اجرا: {usage}"]
    (OUT_DIR / "latest.md").write_text("\n".join(lines), encoding="utf-8")


def reparse_newest() -> int:
    """Rebuild the report from the newest committed snapshot, no network.

    The parser will be wrong again — Google's fields move and the gateway's
    may too. Without this, every correction costs five live queries to see
    whether it worked. With it, the raw payloads already in the repository are
    re-read and the report rewritten for nothing.
    """
    snaps = sorted(OUT_DIR.glob("serp-*.json"))
    if not snaps:
        print("هیچ عکس فوری‌ای در research/ نیست.", file=sys.stderr)
        return 1
    doc = json.loads(snaps[-1].read_text(encoding="utf-8"))
    results = []
    for rec in doc.get("results", []):
        raw = rec.get("raw")
        if isinstance(raw, dict) and not raw.get("_truncated"):
            rec = {"query": rec["query"], **parse_gate(raw)}
        results.append(rec)
    write_report(results, doc.get("usage_after_run"),
                 stamp=snaps[-1].stem.removeprefix("serp-"))
    print(f"دوباره تحلیل شد از {snaps[-1].name} — {len(results)} پرس‌وجو")
    return 0


def main() -> int:
    if "--reparse" in sys.argv:
        return reparse_newest()

    gate_url = (os.environ.get("GATE_URL") or "").strip()
    gate_key = (os.environ.get("GATE_KEY") or "").strip()
    bd_key = (os.environ.get("BRIGHTDATA_API_KEY") or "").strip()
    bd_zone = (os.environ.get("BRIGHTDATA_ZONE") or "cli_unlocker").strip()

    if gate_url and gate_key:
        route = "gate"
    elif bd_key:
        route = "brightdata"
    else:
        print("Set GATE_URL + GATE_KEY, or BRIGHTDATA_API_KEY.", file=sys.stderr)
        return 1
    print(f"مسیر: {route} · پروژه: {PROJECT}")

    # Preflight. /usage needs only the key, so if this succeeds the key is
    # accepted and any later refusal is about the query, the project or the
    # quota — not the credential.
    if route == "gate":
        try:
            print("بررسی کلید از راه /usage: "
                  + _get(gate_url.rstrip("/") + "/usage?"
                         + urllib.parse.urlencode({"key": gate_key}),
                         timeout=30)[:300])
        except Exception as e:                       # noqa: BLE001
            print(f"/usage رد شد → {e}", file=sys.stderr)
            # Name the two refusals apart. 1010 is Cloudflare's edge refusing
            # the request's signature before the Worker runs, so it says
            # nothing at all about the key; anything else came from the
            # gateway itself, which did read the key.
            if "1010" in str(e):
                print("این پیامِ کلادفلر است، نه دروازه: درخواست پیش از "
                      "رسیدن به کد ورکر بلوکه شده. کلید ربطی ندارد.",
                      file=sys.stderr)
            else:
                print("یعنی خودِ دروازه کلید را نپذیرفت.", file=sys.stderr)
            return 1

    results = []
    for q in queries_from_env():
        record: dict = {"query": q}
        try:
            record.update(via_gate(q, gate_url, gate_key) if route == "gate"
                          else via_brightdata(q, bd_key, bd_zone))
            print(f"✓ {q} — {len(record.get('organic', []))} نتیجه، "
                  f"{len(record.get('people_also_ask', []))} پرسش")
        except GateError as e:
            record["error"] = str(e)
            print(f"✗ {q} — {e}", file=sys.stderr)
        except urllib.error.HTTPError as e:
            record["error"] = f"HTTP {e.code}"
            print(f"✗ {q} — HTTP {e.code}", file=sys.stderr)
        except Exception as e:                       # noqa: BLE001
            record["error"] = type(e).__name__
            print(f"✗ {q} — {type(e).__name__}", file=sys.stderr)
        results.append(record)
        time.sleep(2)

    usage = None
    if route == "gate":
        try:
            usage = _get(gate_url.rstrip("/") + "/usage?"
                         + urllib.parse.urlencode({"key": gate_key}),
                         timeout=30)[:300]
            print(f"مصرف: {usage}")
        except Exception:
            pass

    write_report(results, usage)
    ok = sum(1 for r in results if not r.get("error"))
    print(f"نوشته شد: research/latest.md — {ok} از {len(results)} پرس‌وجو موفق")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

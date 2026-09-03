#!/usr/bin/env python3
"""Tells the search engines a page exists, the moment it exists.

WHY THIS MATTERS MORE THAN IT LOOKS
-----------------------------------
Waiting for a crawler to find a new article takes weeks. IndexNow is a free,
account-less ping: the key file served at the domain root is the whole
authentication. Bing is the one that counts here — ChatGPT's live search reads
Bing — so this is the shortest path between publishing an article and an
assistant being able to cite it. Google does not participate and is reached
through the sitemap instead.

WHY IT IS A FILE RATHER THAN LINES IN A WORKFLOW
------------------------------------------------
Two workflows publish: the one that renders committed Markdown, and the daily
one that releases the next queued article. The ping was written inline in the
first, as a heredoc inside a heredoc inside YAML — a shape that cannot be run
or tested anywhere except by pushing to main and watching. Here it can be run
by hand, and a mistake shows up before it is live.

Submitting the whole sitemap rather than one URL is deliberate: IndexNow
accepts up to 10,000 URLs per request, re-submission of an unchanged page is
explicitly allowed, and it means a page that was missed by an earlier failed
run is picked up by the next one instead of being lost.

Never fails the build. The article is already published by the time this runs;
a search engine being slow, rate-limiting, or down is not a reason to mark a
release red.
"""

from __future__ import annotations

import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HOST = "vandidad.xyz"
KEY = "e1f25c1e9599de7ac40a9f13dd647f7c7fa1f352213a90ca3c667c623d1f933e"
ENDPOINT = "https://api.indexnow.org/IndexNow"


def urls_from_sitemap(xml: str) -> list[str]:
    return re.findall(r"<loc>\s*(.*?)\s*</loc>", xml)


def payload(urls: list[str]) -> dict:
    return {
        "host": HOST,
        "key": KEY,
        "keyLocation": f"https://{HOST}/{KEY}.txt",
        "urlList": urls,
    }


def submit(urls: list[str], timeout: int = 30) -> int:
    body = json.dumps(payload(urls), ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        ENDPOINT, data=body, method="POST",
        headers={"Content-Type": "application/json; charset=utf-8"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            print(f"پاسخ IndexNow: {r.status}")
            return r.status
    except urllib.error.HTTPError as e:
        print(f"پاسخ IndexNow: {e.code}", file=sys.stderr)
        try:
            print(e.read().decode("utf-8", "replace")[:300], file=sys.stderr)
        except Exception:
            pass
        return e.code
    except Exception as e:                                   # noqa: BLE001
        print(f"IndexNow نرسید: {type(e).__name__}", file=sys.stderr)
        return 0


def main() -> int:
    sitemap = ROOT / "sitemap.xml"
    if not sitemap.exists():
        print("sitemap.xml نیست — چیزی اعلام نشد.", file=sys.stderr)
        return 0
    urls = urls_from_sitemap(sitemap.read_text(encoding="utf-8"))
    if not urls:
        print("sitemap.xml خالی است — چیزی اعلام نشد.", file=sys.stderr)
        return 0
    print(f"اعلام به موتورها: {len(urls)} آدرس")
    submit(urls)
    return 0  # Never red. See the module docstring.


if __name__ == "__main__":
    raise SystemExit(main())

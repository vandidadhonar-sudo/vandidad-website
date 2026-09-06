#!/usr/bin/env python3
"""Asks whether the front door is open, as the crawlers themselves.

WHY THIS EXISTS — AND WHY ITS ABSENCE WAS THE REAL DEFECT
---------------------------------------------------------
Two loops already run daily: identity_audit.py asks where the owner's name
ranks, seo_audit.py asks where the target phrases rank. Both are measurements
of *position*. Neither of them ever asked the prior question — whether a
crawler can fetch the site at all.

That gap had a cost. Search Console reported "Couldn't fetch" on the sitemap
for two days, with an empty last-read and zero discovered pages, while every
loop reported healthy and every test passed. A ranking loop cannot see a
closed door; it only sees that nothing is behind it, which looks exactly like
being new.

So this is the missing half. It runs where there is real internet — a GitHub
runner, not the session container, whose egress proxy answers 403 to the site
itself — and it fails loudly. A rank that has not been won is not a broken
build; a page a crawler cannot fetch is.

WHY IT SENDS SEVERAL USER AGENTS
--------------------------------
A page that opens in a browser proves nothing about a crawler. Cloudflare
sits in front of this site and can be configured — sometimes by a default,
sometimes by a checkbox nobody remembers ticking — to challenge or block
automated clients. When that happens the site looks perfect to its owner and
is invisible to Google and to ChatGPT at the same time.

Googlebot is checked because Google is the search engine. GPTBot and
OAI-SearchBot are checked because they are how an assistant reads the site,
and robots.txt naming them is only permission — it is not proof that the
network in front of them lets them through. A plain agent is checked as the
control: if the plain one passes and the named ones fail, the problem is bot
filtering and not the site.

WHAT IT DELIBERATELY DOES NOT DO
--------------------------------
It does not follow redirects silently. A 301 that a human would never notice
is exactly how a sitemap ends up at an address a crawler treats as a
different file, so redirects are reported rather than resolved.
"""

from __future__ import annotations

import sys
import urllib.error
import urllib.request

SITE = "https://vandidad.xyz"

# The agents. The first is the control; a failure there means the site is
# down, not that a crawler is being filtered.
AGENTS = {
    "plain": "vandidad-reachability/1.0",
    "Googlebot": (
        "Mozilla/5.0 (compatible; Googlebot/2.1; "
        "+http://www.google.com/bot.html)"
    ),
    "GPTBot": "Mozilla/5.0 (compatible; GPTBot/1.2; +https://openai.com/gptbot)",
    "OAI-SearchBot": (
        "Mozilla/5.0 (compatible; OAI-SearchBot/1.0; "
        "+https://openai.com/searchbot)"
    ),
}


def _has(*needles: str):
    """Body must contain all of these, case-insensitively."""
    def check(body: str) -> str:
        low = body.lower()
        missing = [n for n in needles if n.lower() not in low]
        return "" if not missing else "بدون: " + "، ".join(missing)
    return check


# path -> (expected status, body check). The body check exists because a 200
# is not the same as the right file: the Worker's catch-all serves the app for
# an unrecognised path, so a mis-routed sitemap request answers 200 with HTML
# and a status-only check would call that healthy.
TARGETS = {
    "/": (200, _has("<html", "vandidad")),
    "/sitemap.xml": (200, _has("<urlset", "<loc>", "<lastmod>")),
    "/robots.txt": (200, _has("sitemap:", "gptbot", "googlebot")),
    "/llms.txt": (200, _has("vandidad")),
    "/feed.xml": (200, _has("<feed", "<entry")),
    "/about": (200, _has("<html")),
    "/hadi-bakhtzadeh": (200, _has("<html", "بخت")),
    "/mahsoolat": (200, _has("<html")),
    "/karnameh": (200, _has("<html")),
    # The fix for the two-day sitemap failure. A doubled slash must land on
    # the canonical path rather than on the catch-all, and this is what proves
    # the deployed Worker actually carries that behaviour — the unit test only
    # proves the file in the repository does.
    "//sitemap.xml": (301, None),
}

# Only the control agent walks the whole list. The crawler agents check the
# few files that decide whether the site can be indexed and cited at all;
# multiplying every path by every agent would be forty requests a day to prove
# the same one thing.
CRAWLER_PATHS = ["/", "/sitemap.xml", "/robots.txt", "/llms.txt",
                 "/hadi-bakhtzadeh"]


def fetch(path: str, agent: str, timeout: int = 25):
    """Returns (status, body, location). Never raises for an HTTP status."""
    req = urllib.request.Request(
        SITE + path,
        headers={"User-Agent": AGENTS[agent], "Accept": "*/*"},
    )
    # A redirect must be visible, not followed: the whole point of the sitemap
    # failure was a URL quietly becoming a different URL.
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *a, **k):
            return None

    opener = urllib.request.build_opener(NoRedirect)
    try:
        with opener.open(req, timeout=timeout) as r:
            return r.status, r.read(200_000).decode("utf-8", "replace"), ""
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read(20_000).decode("utf-8", "replace")
        except Exception:
            pass
        return e.code, body, e.headers.get("Location", "") if e.headers else ""
    except Exception as e:                       # DNS, TLS, timeout, reset
        return 0, f"{type(e).__name__}: {e}", ""


def main() -> int:
    failures: list[str] = []
    print(f"در دسترس بودن {SITE} — از دید خزنده‌ها\n")

    print("عاملِ شاهد (plain)")
    for path, (want, check) in TARGETS.items():
        status, body, loc = fetch(path, "plain")
        ok = status == want and (check is None or not check(body))
        detail = ""
        if status != want:
            detail = f"وضعیت {status}" + (f" → {loc}" if loc else "")
            if status == 0:
                detail = body[:120]
        elif check is not None:
            detail = check(body)
        print(f"  {'✓' if ok else '✗'} {path:<20} {detail}")
        if not ok:
            failures.append(f"{path} با عامل شاهد: {detail or status}")

    for agent in ("Googlebot", "GPTBot", "OAI-SearchBot"):
        print(f"\n{agent}")
        for path in CRAWLER_PATHS:
            want, check = TARGETS[path]
            status, body, loc = fetch(path, agent)
            ok = status == want and (check is None or not check(body))
            # 403 and 503 are the shapes a bot filter takes. Naming them is
            # the difference between "the site is down" and "this crawler is
            # being turned away", which have nothing to do with each other.
            note = ""
            if status in (403, 503):
                note = "  ← احتمالاً فیلترِ ربات در کلادفلر"
            print(f"  {'✓' if ok else '✗'} {path:<20} {status}{note}")
            if not ok:
                failures.append(f"{path} با {agent}: {status}{note}")

    print()
    if failures:
        print(f"✗ {len(failures)} مشکل:")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("✓ همهٔ مسیرها برای همهٔ خزنده‌ها باز است.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

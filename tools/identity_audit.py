#!/usr/bin/env python3
"""The identity loop: state the goal, measure against it, say pass or fail.

WHY THIS EXISTS
---------------
The goal of this work has been said in conversation many times and never
written where it could be checked: **when someone searches the owner's name,
in any spelling and in Persian, English or Turkish, they should find him
described as an AI systems architect — with his own site among the sources.**

A goal that lives only in a conversation gets re-litigated every session and
drifts. Twice already a decision was lost that way. This file is the goal in
a form that fails loudly.

WHAT IT MEASURES
----------------
Two halves, deliberately separated, because they fail for different reasons
and are fixed in different places.

  ON-PAGE   — everything under our control. Do the pages actually carry every
              spelling of the name, in text a crawler can read rather than
              only in markup? Is the entity one @id with one profile page? Are
              the confirmed profiles declared? This half must be 100%: there
              is no excuse for a defect here, and it is checked against the
              built HTML, not against intention.

  IN-SEARCH — what Google actually returned, read from research/serp-*.json.
              This half is not under our control and moves slowly. A failure
              here is a fact to work on, not a bug — but it is recorded so
              progress is measured rather than felt.

The distinction matters: on 2026-09-06 the on-page half looked finished while
two searches returned nothing, and the cause was a spelling that existed in
alternateName and appeared once in visible text. Only measuring both halves
separately made that visible.

USAGE
-----
    python3 tools/identity_audit.py           # report
    python3 tools/identity_audit.py --check   # non-zero exit if on-page fails
"""

from __future__ import annotations

import argparse
import glob
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import build_content as bc  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent

# ── THE GOAL ─────────────────────────────────────────────────────────────
#
# Every spelling a person might actually type. The half-space and full-space
# forms look identical on screen and are different strings to a search engine;
# treating them as one is exactly the mistake that cost two failed searches.
SPELLINGS_FA = [
    "هادی بخت‌زاده",
    "هادی بخت زاده",
    "محمد هادی بخت‌زاده",
    "محمد هادی بخت زاده",
]
SPELLINGS_LATIN = ["Hadi Bakhtzadeh", "Mohammadhadi Bakhtzadeh"]

# What a searcher must see next to the name. These are the words that turn
# "some person" into "the person who does this".
ROLE_WORDS_FA = ["معمار", "هوش مصنوعی"]

# The searches that define success, and what counts as success for each.
# `wants_site` means vandidad.xyz must be among the sources; a name that
# resolves only through LinkedIn is not the goal.
TARGET_QUERIES = [
    ("هادی بخت‌زاده", True),
    ("هادی بخت زاده", True),
    ("محمد هادی بخت زاده", True),
    ("هادی بخت زاده هوش مصنوعی", True),
    ("Hadi Bakhtzadeh", True),
    ("وندیداد گروپ", True),
]

# Pages that must carry the identity, and the minimum number of times each
# Persian spelling has to appear in text a crawler can read. One occurrence
# buried in a footnote is what failed in September; three is the floor for the
# page whose whole job is the name.
PAGE_MINIMUMS = {
    "hadi-bakhtzadeh.html": 3,
    "karnameh.html": 1,
}


def visible_text(html_text: str) -> str:
    """Text a crawler reads — markup and JSON-LD removed.

    The distinction this function draws is the entire point of the on-page
    half: a name declared in alternateName is a claim about an entity, while a
    name in the body is a string that can be matched against a query.
    """
    body = html_text.split("<body>", 1)[-1]
    body = re.sub(r"<script.*?</script>", " ", body, flags=re.S)
    body = re.sub(r"<style.*?</style>", " ", body, flags=re.S)
    return " ".join(re.sub(r"<[^>]+>", " ", body).split())


def audit_pages() -> list[tuple[bool, str]]:
    out: list[tuple[bool, str]] = []

    for name, minimum in PAGE_MINIMUMS.items():
        path = ROOT / name
        if not path.exists():
            out.append((False, f"{name} ساخته نشده"))
            continue
        text = path.read_text("utf-8")
        vis = visible_text(text)
        for spelling in SPELLINGS_FA:
            n = vis.count(spelling)
            ok = n >= minimum
            out.append((ok, f"{name}: «{spelling}» {n} بار در متن دیده‌شدنی "
                            f"(حداقل {minimum})"))
        if name == "hadi-bakhtzadeh.html":
            for word in ROLE_WORDS_FA:
                out.append((word in vis,
                            f"{name}: «{word}» در متن هست"))
            for spelling in SPELLINGS_LATIN:
                out.append((spelling in vis,
                            f"{name}: «{spelling}» در متن هست"))

    # The entity itself: one identity, every spelling declared, one profile
    # page, and the confirmed accounts present.
    person = bc.PERSON
    declared = set(person.get("alternateName", [])) | {person.get("name")}
    for spelling in SPELLINGS_FA + SPELLINGS_LATIN:
        out.append((spelling in declared,
                    f"داده: «{spelling}» در alternateName"))
    out.append((person["@id"] == bc.SITE + "/#person", "داده: یک @id"))
    out.append((person["mainEntityOfPage"]["@id"] == bc.PERSON_URL,
                "داده: صفحهٔ رکورد یکی است"))
    out.append((person["url"] == bc.PERSON_URL,
                "داده: url و mainEntityOfPage یکی‌اند"))

    same = person.get("sameAs", [])
    for host in ("github.com", "linkedin.com", "instagram.com",
                 "x.com"):
        out.append((any(host in s for s in same), f"داده: sameAs → {host}"))

    # The three languages, on one page, as summaries a model can quote.
    page = (ROOT / "hadi-bakhtzadeh.html")
    if page.exists():
        t = page.read_text("utf-8")
        out.append(('lang="en"' in t, "صفحه: خلاصهٔ انگلیسی"))
        out.append(('lang="tr"' in t, "صفحه: خلاصهٔ ترکی"))
    return out


def audit_search() -> list[tuple[bool | None, str]]:
    """What Google returned, from the newest snapshot on disk.

    Not under our control, so a failure here is reported and not counted as a
    build error. A query with no snapshot returns None — unknown, which is a
    third state and must not be read as either pass or fail.
    """
    files = sorted(glob.glob(str(ROOT / "research" / "serp-*.json")))
    if not files:
        return [(None, "هیچ عکسی از نتایج جستجو موجود نیست")]

    seen: dict[str, list[str]] = {}
    for f in files:                       # newest wins
        try:
            data = json.loads(Path(f).read_text("utf-8"))
        except Exception:
            continue
        for r in data.get("results", []):
            titles = r.get("raw", {}).get("رتبه‌دارها", [])
            if titles:
                seen[bc._norm_keyword(r.get("query", ""))] = titles

    out: list[tuple[bool | None, str]] = []
    for query, wants_site in TARGET_QUERIES:
        titles = seen.get(bc._norm_keyword(query))
        if titles is None:
            out.append((None, f"«{query}» — هنوز سنجیده نشده"))
            continue
        blob = " ".join(titles)
        ours = ("vandidad" in blob.lower()
                or "وندیداد" in blob
                or any(bc._phrase_in(blob, s) and "معمار" in blob
                       for s in SPELLINGS_FA))
        rank = next((i + 1 for i, t in enumerate(titles)
                     if "vandidad" in t.lower() or "وندیداد" in t
                     or "معمار هوش مصنوعی" in t), None)
        if wants_site and ours:
            out.append((True, f"«{query}» — پیدا شد"
                              + (f" (رتبهٔ {rank})" if rank else "")))
        else:
            out.append((False, f"«{query}» — چیزی از ما در نتایج نیست"))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                    help="خروج با خطا اگر بخش روی-صفحه کامل نباشد")
    args = ap.parse_args()

    pages = audit_pages()
    search = audit_search()

    print("هدف: هر کسی که اسم مالک را — به هر املا و به فارسی، انگلیسی یا")
    print("      ترکی — جستجو کند، او را معمار سیستم‌های هوش مصنوعی ببیند،")
    print("      و vandidad.xyz میان منابع باشد.\n")

    print("── روی صفحه (زیر کنترل ما — باید ۱۰۰٪ باشد) " + "─" * 18)
    bad = 0
    for ok, line in pages:
        print(("  ✓ " if ok else "  ✗ ") + line)
        bad += 0 if ok else 1

    print("\n── در نتایج جستجو (زیر کنترل ما نیست — کند حرکت می‌کند) " + "─" * 6)
    unknown = 0
    fails = 0
    for ok, line in search:
        mark = "  ✓ " if ok else ("  ? " if ok is None else "  ✗ ")
        print(mark + line)
        unknown += 1 if ok is None else 0
        fails += 1 if ok is False else 0

    total = len(pages)
    print(f"\nروی صفحه: {total - bad} از {total}"
          + ("  — کامل" if not bad else f"  — {bad} مورد باقی مانده"))
    print(f"در جستجو: {len(search) - fails - unknown} از {len(search)}"
          + (f"  ({unknown} هنوز سنجیده نشده)" if unknown else ""))

    if bad:
        print("\nبخش روی-صفحه کامل نیست. تا کامل نشده، از لوپ بیرون نیا.")
    if args.check and bad:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

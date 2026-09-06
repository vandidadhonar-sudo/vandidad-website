#!/usr/bin/env python3
"""The keyword loop: the SEO goal, measured — on the page and in the results.

WHY THIS EXISTS
---------------
tools/seo_report.py already checks each article's on-page mechanics: is the
target phrase used, is it in the title, is it early, does the page link out.
That is necessary and it is not the goal. The goal is:

  **rank in search engines, and be the source a language model cites, on
  هوش مصنوعی · هوشواره · سیستم‌عامل هوش مصنوعی · ایجنت · اتوماسیون and the
  rest of the phrases chosen from real search data.**

Those are two different things and they fail differently:

  A search engine ranks a page. It needs the phrase in the places a crawler
  weighs, links pointing at the page, and a site structure that says which
  page is the authority on a subject.

  A language model quotes a passage. It needs a short, self-contained answer
  in the language the question was asked in, matching text a reader can see —
  and it needs to find the page at all, which for a Persian site means
  llms.txt and structured data more than it means backlinks.

A page can pass every on-page SEO check and still be unquotable, because
nothing on it is a paragraph that answers a question on its own. This audit
measures both, separately, so neither hides behind the other.

THREE HALVES, NOT TWO
---------------------
  ON-PAGE    everything under our control, must be 100%
  FOR LLMs   quotable, declared, discoverable — also under our control
  IN-SEARCH  what Google actually returned; slow, and not a build error

USAGE
-----
    python3 tools/seo_audit.py             # report
    python3 tools/seo_audit.py --check     # non-zero exit if our half fails
    python3 tools/seo_audit.py --unmeasured  # print phrases never rank-checked
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
# The subjects this site intends to be the source on. Every target keyword
# should sit under one of these; a phrase that belongs to none of them is a
# phrase we chose for its own sake rather than for the position.
PILLARS = [
    # The technology
    "هوش مصنوعی", "هوشواره", "سیستم عامل هوش مصنوعی", "ایجنت",
    "مدل زبانی", "چت بات", "ربات",
    # The work it does — added after the first run called six real phrases
    # orphans. They were not orphans; this list was short.
    "اتوماسیون", "پیگیری", "پاسخ", "لید", "سرنخ", "امنیت", "حریم خصوصی",
    "کسب و کار", "مشتری",
]

# Two strategies, measured differently. Conflating them is a mistake I made
# on 2026-09-06: I read the first-page results for «معمار هوش مصنوعی», found
# building architecture owning all nine, and called the phrase lost. That is
# the right test for one strategy and the wrong test for the other.
#
#   CAPTURE — an existing question with existing demand. Someone is already
#             searching it and someone else is already answering. Success is
#             ranking against them, and intent must match or the traffic
#             bounces. Today's first page is the decision.
#
#   CREATE  — a meaning being established rather than contested. «هوشواره»
#             is the clearest case: the word exists, the concept is ours to
#             define, and whoever holds the phrase today holds it for another
#             meaning. Today's first page is not the decision; being the
#             reference for the meaning is. Rank ten among results about a
#             different subject is a beginning, not a failure.
#
# The owner's decision, and it is his to make: these four are CREATE. The
# category is being built, not captured.
CREATE_PHRASES = [
    "هوشواره",
    "معمار هوش مصنوعی",
    "ارکستراسیون هوش مصنوعی",
    "سیستم عامل هوش مصنوعی",
]

# What makes a passage quotable by a model: it stands alone, it is in the
# language of the question, and a reader can see the same words on the page.
ANSWER_MIN_WORDS = 25


def articles() -> list[tuple[bc.Article, bool]]:
    """Every article, paired with whether it is live.

    Liveness is the folder, not the front matter. A queued article carries
    `collection: hamzad` because that is where it will land — reading the
    field instead of the path counts thirty-seven articles as published when
    nine are, which is what the first run of this audit did.
    """
    out = []
    for folder in ("hamzad", "blog", "queue"):
        d = bc.CONTENT / folder
        if not d.exists():
            continue
        for path in sorted(d.glob("*.md")):
            if path.name.endswith(".social.md"):
                continue
            try:
                out.append((bc.parse(path), folder != "queue"))
            except bc.BuildError:
                continue
    return out


def audit_onpage(arts: list[bc.Article]) -> list[tuple[bool, str]]:
    """The mechanics, rolled up. Detail stays in seo_report.py."""
    out: list[tuple[bool, str]] = []

    with_kw = [a for a in arts if a.target_keyword]
    out.append((len(with_kw) == len(arts),
                f"هر مقاله عبارت هدف دارد ({len(with_kw)} از {len(arts)})"))

    # One phrase, one page. Two pages chasing one phrase is not twice the
    # traffic; it is Google picking one and discounting the other.
    seen: dict[str, str] = {}
    clashes = []
    for a in with_kw:
        key = bc._norm_keyword(a.target_keyword)
        if key in seen:
            clashes.append(f"{a.slug} و {seen[key]}")
        seen[key] = a.slug
    out.append((not clashes,
                "هیچ دو مقاله‌ای یک عبارت را هدف نگرفته‌اند"
                + (f" — تداخل: {', '.join(clashes)}" if clashes else "")))

    # Every phrase should belong to a subject we are trying to own.
    orphan_topics = [a.target_keyword for a in with_kw
                     if not any(bc._phrase_in(a.target_keyword, p)
                                for p in PILLARS)]
    out.append((not orphan_topics,
                "هر عبارت هدف زیر یکی از ستون‌هاست"
                + (f" — بیرون: {'، '.join(orphan_topics)}"
                   if orphan_topics else "")))

    # Tiers: a trade article that links to no pillar is a leaf with no tree.
    tiers = {t: [a for a in arts if a.tier == t] for t in bc.TIERS}
    out.append((len(tiers["ستون"]) >= 4,
                f"ستون‌ها: {len(tiers['ستون'])} مقاله (حداقل ۴)"))
    for name, group in tiers.items():
        out.append((bool(group), f"ردهٔ «{name}» خالی نیست"))

    return out


def audit_for_llms(pairs) -> list[tuple[bool, str]]:
    """Quotable, declared, discoverable.

    A model does not rank pages; it looks for a passage it can lift. That
    passage has to exist, stand alone, and match what a reader sees — the
    condition for using it at all.
    """
    out: list[tuple[bool, str]] = []
    arts = [a for a, _ in pairs]

    missing = [a.slug for a in arts if not a.answer]
    out.append((not missing,
                f"هر مقاله بلوک پاسخ کوتاه دارد "
                f"({len(arts) - len(missing)} از {len(arts)})"
                + (f" — بدون پاسخ: {'، '.join(missing[:3])}"
                   if missing else "")))

    short = [a.slug for a in arts
             if a.answer and len(a.answer.split()) < ANSWER_MIN_WORDS]
    out.append((not short,
                f"هیچ پاسخی کوتاه‌تر از {ANSWER_MIN_WORDS} کلمه نیست"
                + (f" — کوتاه: {'، '.join(short[:3])}" if short else "")))

    # The answer must contain the phrase it is answering about, or a model
    # matching a question to a passage has nothing to match on.
    off = [a.slug for a in arts
           if a.answer and a.target_keyword
           and not bc._phrase_in(a.answer, a.target_keyword)]
    out.append((not off,
                "عبارت هدف در پاسخ کوتاه هست"
                + (f" — نیست در: {'، '.join(off[:3])}" if off else "")))

    # Building a category has a precondition that capturing one does not: the
    # term has to be defined somewhere we own. A phrase we intend to make the
    # reference for, with no page that says what it means, is a phrase we are
    # hoping about rather than building. This check exists because
    # «ارکستراسیون» was named as a term to establish while no article defined
    # it and llms.txt did not contain the word once.
    for phrase in CREATE_PHRASES:
        defining = [a.slug for a in arts
                    if a.target_keyword
                    and (bc._phrase_in(a.target_keyword, phrase)
                         or bc._phrase_in(phrase, a.target_keyword))]
        out.append((bool(defining),
                    f"مفهومِ «{phrase}» مقالهٔ تعریف‌کننده دارد"
                    + (f" — {defining[0]}" if defining else " — ندارد")))

    published = [a for a, live in pairs if live]
    llms = ROOT / "llms.txt"
    if llms.exists():
        text = llms.read_text("utf-8")
        absent = [a.slug for a in published if a.url not in text]
        out.append((not absent,
                    f"هر مقالهٔ منتشرشده در llms.txt هست "
                    f"({len(published) - len(absent)} از {len(published)})"))
        for page in (bc.PERSON_URL, bc.PRODUCTS_URL):
            out.append((page in text, f"llms.txt → {page.split('/')[-1]}"))
        for lang_marker in ("Türkçe",):
            out.append((lang_marker in text, f"llms.txt: «{lang_marker}»"))
        # A model answering about a term we are establishing reads this file
        # before it reads the site. A term absent from it is invisible there.
        #
        # Matched with the folding comparison, not `in`: llms.txt writes
        # «سیستم‌عامل» with a zero-width joiner and this list writes «سیستم
        # عامل» with a space. They are one word to a reader and two strings
        # to `in` — the same defect that cost two failed name searches, found
        # here in my own check rather than on a page.
        for phrase in CREATE_PHRASES:
            out.append((bc._phrase_in(text, phrase),
                        f"llms.txt: «{phrase}»"))
    else:
        out.append((False, "llms.txt نیست"))

    # An assistant that cannot fetch the page still reads the sitemap and the
    # feed. Both must carry every live article.
    sm = (ROOT / "sitemap.xml")
    if sm.exists():
        xml = sm.read_text("utf-8")
        gone = [a.slug for a in published if a.url not in xml]
        out.append((not gone, f"هر مقالهٔ منتشرشده در sitemap هست"))
    return out


def rank_of(titles: list[str], phrase: str) -> int | None:
    for i, t in enumerate(titles, 1):
        low = t.lower()
        if "vandidad" in low or "وندیداد" in t or "همزاد" in t:
            return i
    return None


def snapshots() -> dict[str, list[str]]:
    seen: dict[str, list[str]] = {}
    for f in sorted(glob.glob(str(ROOT / "research" / "serp-*.json"))):
        try:
            data = json.loads(Path(f).read_text("utf-8"))
        except Exception:
            continue
        for r in data.get("results", []):
            titles = r.get("raw", {}).get("رتبه‌دارها", [])
            if titles:
                seen[bc._norm_keyword(r.get("query", ""))] = titles
    return seen


def is_create(phrase: str) -> bool:
    return any(bc._phrase_in(phrase, c) or bc._phrase_in(c, phrase)
               for c in CREATE_PHRASES)


def audit_search(arts: list[bc.Article]):
    """Split by strategy, because the two are not scored the same way.

    For a phrase being captured, absence from the first page is a failure to
    work on. For a phrase whose meaning is being built, presence at any rank
    is progress and absence is the expected starting point — the incumbents
    are answering a different question.
    """
    seen = snapshots()
    cap_found, cap_absent, cre_found, cre_absent, unmeasured = [], [], [], [], []
    for a in arts:
        if not a.target_keyword:
            continue
        kw = a.target_keyword
        titles = seen.get(bc._norm_keyword(kw))
        if titles is None:
            unmeasured.append(kw)
            continue
        rank = rank_of(titles, kw)
        label = f"{kw}" + (f" (رتبهٔ {rank})" if rank else "")
        if is_create(kw):
            (cre_found if rank else cre_absent).append(label)
        else:
            (cap_found if rank else cap_absent).append(label)
    return cap_found, cap_absent, cre_found, cre_absent, unmeasured


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--unmeasured", action="store_true",
                    help="فقط عبارت‌هایی که هرگز سنجیده نشده‌اند")
    args = ap.parse_args()

    pairs = articles()
    arts = [a for a, _ in pairs]
    cap_found, cap_absent, cre_found, cre_absent, unmeasured = audit_search(arts)

    if args.unmeasured:
        print("; ".join(unmeasured))
        return 0

    print("هدف: رتبه گرفتن در موتورهای جستجو و بودن در پاسخِ مدل‌های زبانی،")
    print("      روی هوش مصنوعی، هوشواره، سیستم‌عامل هوش مصنوعی، ایجنت،")
    print("      اتوماسیون و بقیهٔ عبارت‌هایی که از دادهٔ واقعی انتخاب شدند.\n")

    bad = 0
    for title, rows in (("روی صفحه", audit_onpage(arts)),
                        ("برای مدل‌های زبانی", audit_for_llms(pairs))):
        print(f"── {title} (زیر کنترل ما — باید ۱۰۰٪ باشد) " + "─" * 12)
        for ok, line in rows:
            print(("  ✓ " if ok else "  ✗ ") + line)
            bad += 0 if ok else 1
        print()

    print("── گرفتنِ عبارتِ موجود (رقابت با کسی که الان جواب می‌دهد) " + "─" * 4)
    print(f"  ✓ در نتایج هست: {len(cap_found)}")
    for f in cap_found:
        print(f"      · {f}")
    print(f"  ✗ سنجیده شد و نبود: {len(cap_absent)}")
    for a in cap_absent[:8]:
        print(f"      · {a}")

    print("\n── ساختنِ مفهوم (نتیجهٔ امروزِ رقیب معیار نیست) " + "─" * 8)
    print("  اینها را نمی‌گیریم، می‌سازیم. صاحبِ امروزِ عبارت به پرسشِ")
    print("  دیگری جواب می‌دهد؛ معیار این است که مرجعِ این معنا بشویم.")
    print(f"  ✓ حضور پیدا کرده: {len(cre_found)}")
    for f in cre_found:
        print(f"      · {f}")
    print(f"  ○ هنوز نه — نقطهٔ شروع، نه شکست: {len(cre_absent)}")
    for a in cre_absent:
        print(f"      · {a}")
    print(f"\n  ? هرگز سنجیده نشده: {len(unmeasured)}")

    total_kw = (len(cap_found) + len(cap_absent) + len(cre_found)
                + len(cre_absent) + len(unmeasured))
    print(f"\nعبارت‌های هدف: {total_kw}")
    print(f"بخش زیر کنترل ما: {'کامل' if not bad else f'{bad} مورد باقی مانده'}")
    if unmeasured:
        print(f"\n{len(unmeasured)} عبارت هنوز رتبه‌سنجی نشده — تا سنجیده")
        print("نشوند نمی‌شود گفت لوپ بسته شده.")
        print("گرفتنشان:  python3 tools/seo_audit.py --unmeasured")
    if args.check and bad:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

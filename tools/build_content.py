#!/usr/bin/env python3
"""Turns the Markdown a writer commits into the pages the site serves.

WHY THIS EXISTS
---------------
Articles are written in one place and the site is built in another. If the
writer produced HTML, every article would carry its own accidental markup and
its own accidental idea of what an article looks like, and the pages would
drift apart the way the Worker drifted from the repository. So the writer
produces Markdown with front matter and nothing else, and this file is the only
thing that decides what a page on this site is.

WHY IT ALSO REFUSES
-------------------
The brief says a Hamzad article is at least 600 words and must end with a
section on what the subject concretely means for an Iranian business. A brief
that is only advice gets forgotten on a tired week. Here those rules fail the
build, with a message naming the file and the fix, so the site never quietly
fills up with the generic writing the owner already rejected once.

WHY THE STRUCTURED DATA MATTERS MORE THAN llms.txt
--------------------------------------------------
Measurements of AI crawler traffic show the assistant crawlers overwhelmingly
skip llms.txt and read HTML. So the facts that place this company and this
person — and separate them from the unrelated Iranian construction firm of the
same name that currently owns the search results — are written into every page
as JSON-LD, where the crawlers actually look.

Run: python3 tools/build_content.py [--check]
  --check  validate and render without writing, for pull requests
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
import urllib.parse
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

try:
    import markdown as md_lib
except ImportError:  # pragma: no cover - the workflow installs it
    sys.exit("missing dependency: pip install markdown pyyaml")
try:
    import yaml
except ImportError:  # pragma: no cover
    sys.exit("missing dependency: pip install markdown pyyaml")

ROOT = Path(__file__).resolve().parent.parent
CONTENT = ROOT / "content"
SITE = "https://vandidad.xyz"

SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
FRONT_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)$", re.S)

# The section every Hamzad article has to end with. Matched loosely on the
# stem so a writer's spacing or half-space does not fail a good article.
IRAN_SECTION = re.compile(r"برای\s*کسب.?و.?کار\s*ایرانی")

# A quotable answer, sized. Under the floor it says nothing; over the ceiling
# no snippet and no assistant lifts it in one piece.
ANSWER_MIN = 180
ANSWER_MAX = 420

# The three levels an article can sit at. See Article.tier.
TIERS = ("ستون", "میانی", "صنفی")

# The owner's standing rules, enforced rather than advised.
#
# These exist because the approval step was removed: articles publish straight
# to main so he stops being the bottleneck. That is only safe if the things
# that would actually damage him — a quoted price, a promised delivery date, a
# political aside, a statistic with no source — cannot get through. A rule that
# lives only in a brief gets forgotten on a tired week; a rule that fails the
# build does not.
#
# Each entry is (name, pattern, what the writer should do instead).
FORBIDDEN = [
    (
        "قیمت",
        re.compile(
            r"(?:^|[^\w])(?:\d[\d,،.]*\s*(?:تومان|ریال|میلیون|میلیارد|دلار|یورو|لیر)"
            r"|(?:تومان|ریال|دلار|یورو|لیر)\s*\d"
            r"|قیمت\s*(?:از|شروع|حدود|تقریب)"
            r"|هزینه\s*(?:از|حدود|تقریب)\s*\d)",
        ),
        "قیمت هرگز در محتوا نمی‌آید — نه عدد، نه محدوده، نه «از … شروع می‌شود». "
        "قیمت فقط در گفتگوی مستقیم مشخص می‌شود.",
    ),
    (
        "زمانِ تحویل",
        re.compile(
            r"(?:ظرف|در\s*عرض|طی)\s*(?:\d+|یک|دو|سه|چند)\s*"
            r"(?:روز|هفته|ماه)\s*(?:تحویل|آماده|راه‌?اندازی|می‌?سازیم|تمام)"
            r"|(?:تحویل|راه‌?اندازی)\s*(?:در|ظرف)\s*(?:\d+|یک|دو|سه|چند)\s*(?:روز|هفته|ماه)"
        ),
        "زمانِ ساخت هم مثل قیمت است — هیچ تعهدِ زمانی در محتوا نوشته نمی‌شود.",
    ),
    (
        "سیاست",
        re.compile(
            r"تحریم|رژیم|حکومت|دولت\s*(?:فعلی|قبلی)|انتخابات|براندازی|اصلاح‌?طلب|اصول‌?گرا"
        ),
        "سیاست ممنوع است. اگر محدودیتی فنی یا اقتصادی هست، خودِ محدودیت را "
        "توصیف کن بدونِ اشاره‌ی سیاسی — مثلاً «دسترسی به این سرویس از ایران باز نیست».",
    ),
    (
        "لینکِ بی‌معنا",
        # The weak phrase can sit anywhere inside the link text — «اینجا کلیک
        # کنید» is the common form, not a bare «اینجا».
        re.compile(
            r"\[[^\]]*(?:کلیک\s*کنید|اینجا|همین\s*جا|این\s*لینک"
            r"|بیشتر\s*بخوانید|ادامه\s*مطلب|click\s*here)[^\]]*\]\("
        ),
        "متنِ لینک باید بگوید آن طرف چیست. «اینجا کلیک کنید» نه برای خواننده "
        "معنا دارد نه برای موتور جست‌وجو.",
    ),
    (
        "ادعای اثبات‌ناپذیر",
        # A superlative is a claim a reader cannot check and a competitor can
        # dispute. The brand is built on being the one that does not exaggerate,
        # so this costs more than it buys.
        re.compile(
            r"(?:^|[^\w])(?:اولین|نخستین|تنها\s+(?:شرکت|سیستم|ابزار|راه)"
            r"|بهترین|بی‌?نظیر|بی‌?رقیب|پیشرو|معجزه|صد\s*در\s*صد|۱۰۰\s*٪)"
        ),
        "«اولین»، «تنها»، «بهترین» را نمی‌شود ثابت کرد و رقیب می‌تواند ردش کند. "
        "به‌جایش همان کارِ مشخصی را بنویس که سیستم انجام می‌دهد.",
    ),
    (
        "لحنِ ساعت‌فروشی",
        # "bespoke" and its Persian cousins frame the company as an hourly
        # consultancy. AIOS is a platform the company owns; client systems are
        # configured on it.
        re.compile(r"bespoke|سفارشی‌?دوزی|از\s*صفر\s*(?:برای|ساخته)"),
        "ما پلتفرم داریم و سیستمِ هر مشتری روی آن پیکربندی می‌شود — نه اینکه هر "
        "پروژه از صفر ساخته شود. این تفاوتِ شرکتِ محصول با دفترِ مشاوره است.",
    ),
    (
        "جمله‌ی قصار",
        re.compile(
            r"هوش\s*مصنوعی\s*آینده\s*است"
            r"|داده\s*(?:نفتِ?|طلای)\s*جدید"
            r"|یک\s*(?:انتخاب|گزینه)\s*نیست[،.]?\s*یک\s*ضرورت"
            r"|قطارِ?\s*(?:پیشرفت|فناوری)"
            r"|عقب\s*ماندن\s*از\s*قافله"
        ),
        "جمله‌ی قصار هیچ چیزی به کسی نمی‌گوید و خواننده را فراری می‌دهد. "
        "به‌جایش یک واقعیتِ مشخص از کارِ خواننده بنویس.",
    ),
]

# A number that reads like a statistic needs a source in the same paragraph.
STAT = re.compile(r"(?:^|[^\w.])(\d{1,3}(?:[.,]\d+)?)\s*(?:٪|درصد|%)")
SOURCE_NEAR = re.compile(r"\[[^\]]+\]\(https?://|طبق|بر\s*اساس|به\s*گزارش|منبع")

COLLECTIONS = {
    "blog": {
        "fa": "بلاگ",
        "en": "Blog",
        "lead": "نوشته‌های کوتاه درباره‌ی به‌کار بستنِ هوش مصنوعی در یک کسب‌وکارِ واقعی.",
        "min_words": 0,
        "require_iran_section": False,
    },
    "hamzad": {
        # The path stays /hamzad. Five articles are already in the sitemap and
        # have been announced to the engines under it, and renaming a URL to
        # improve a heading throws away the little indexing that exists. What
        # a reader sees is a separate question from what the address says.
        "fa": "مقالات",
        "en": "Articles",
        # The old line — «نوشته‌های بلندتر» — described our filing system: it
        # told a reader that these pieces are longer than some other pieces
        # they had never seen. A lead has one job, which is to say what the
        # reader gets.
        "lead": "دربارهٔ اینکه هوش مصنوعی در یک کسب‌وکار واقعی کجا کار می‌کند و کجا نه — با مثال از کارِ ایرانی، بدون شعار و بدون فروش.",
        "min_words": 1500,
        "require_iran_section": True,
    },
}

# Articles written before the floor was raised from 600 to 1500 words. Google
# publishes no word count and none is being claimed here: the number is ours,
# chosen because the pages already ranking for these phrases in Persian run
# well past a thousand words, and a short page loses to them on coverage
# rather than on quality.
#
# These six are listed rather than exempted quietly, so the debt is visible in
# the file that enforces the rule instead of living in someone's memory. Each
# one leaves this list by being expanded, not by being forgotten.
# Empty, and that is the point: every article on it was expanded past the
# floor rather than exempted forever. Kept because the mechanism is what
# makes raising a rule survivable — the next time a floor moves, the
# articles that fall short go here with a date, and a test in
# tools/test_pipeline.py fails if one of them has quietly grown long enough
# to leave. An empty list means no debt, not no rule.
LEGACY_SHORT: set[str] = set()

# One statement of who this is, reused in every page's structured data. The
# sameAs list is what lets a model connect the site to the person rather than
# guessing from a name that another company already owns.
ORGANISATION = {
    "@type": "Organization",
    "@id": SITE + "/#organization",
    "name": "Vandidad Group",
    "alternateName": ["وندیداد گروپ", "AIOS"],
    "url": SITE,
    "email": "ai@vandidad.xyz",
    "description": (
        "Vandidad Group builds AIOS — an AI platform for business conversation — "
        "and the systems that run on it. One reasoning core serves every channel a "
        "business talks on, and each client system is configured for its industry "
        "rather than rebuilt from scratch."
    ),
    "address": {
        "@type": "PostalAddress",
        "addressLocality": "Konak, İzmir",
        "addressCountry": "TR",
    },
    # An assistant asked "who builds AI sales systems for Persian-speaking
    # businesses" has to resolve this name against an unrelated Iranian
    # construction firm that currently owns the search results. A name and a
    # description are not enough to separate them; the language served, the
    # market served and the subject matter are the properties that do.
    "knowsLanguage": ["fa", "en", "tr"],
    "areaServed": [
        {"@type": "Country", "name": "Iran"},
        {"@type": "Country", "name": "Türkiye"},
    ],
    "knowsAbout": [
        "conversational AI for business",
        "Persian-language AI assistants",
        "digital twin sales agents",
        "customer follow-up automation",
        "AI systems architecture",
    ],
    "founder": {"@id": SITE + "/#person"},
}

# One person, one identity, every spelling.
#
# Searching the owner's name in Persian returned, from Google's own AI
# overview, "no detailed biography published on the web" — and for one
# spelling, "not registered in official sources". Two defects caused that.
#
# First, the name was written four ways across this site — Hadi Bakhtzadeh,
# Hadi Bahtzade, هادی بخت‌زاده, Mohammadhadi Bakhtzadeh — and the form he
# actually searched, محمد هادی بخت‌زاده, appeared nowhere. Second, the founder
# named on /about carried a bare Person object with no @id, so nothing tied
# it to the author of the articles. To a search engine those are two people,
# each with almost no record.
#
# Every spelling now sits in alternateName on a single @id that /about and
# every article share. A model resolving any one of them arrives at the same
# entity, and that entity has the articles attached to it.
PERSON = {
    "@type": "Person",
    "@id": SITE + "/#person",
    "name": "Hadi Bakhtzadeh",
    "alternateName": [
        "هادی بخت‌زاده",
        "محمد هادی بخت‌زاده",
        "هادی بخت زاده",
        "محمدهادی بخت‌زاده",
        "Mohammadhadi Bakhtzadeh",
        "Mohammad Hadi Bakhtzadeh",
        "Hadi Bahtzade",
        "M. Hadi Bakhtzadeh",
    ],
    "givenName": "Hadi",
    "familyName": "Bakhtzadeh",
    "jobTitle": "Architect of Intelligent Systems",
    "description": (
        "AI systems architect and founder of Vandidad Group, a technology "
        "company registered in İzmir, Türkiye (İzmir Trade Registry 202783, "
        "founded March 2018). Designs the behaviour of AI systems for "
        "businesses that sell in Persian: what they understand, how they "
        "speak, what they remember between conversations, and where they must "
        "refuse. Writes on AI systems architecture, agentic AI and "
        "conversational design in Persian."
    ),
    "nationality": {"@type": "Country", "name": "Iran"},
    "workLocation": {
        "@type": "Place",
        "address": {
            "@type": "PostalAddress",
            "addressLocality": "Konak, İzmir",
            "addressCountry": "TR",
        },
    },
    # The page a machine should treat as this person's record.
    "mainEntityOfPage": {"@type": "ProfilePage", "@id": SITE + "/about"},
    # Profiles that confirm the same person elsewhere. sameAs is the strongest
    # identity signal there is, and it cannot be invented — every entry has to
    # be a real profile the owner controls. Empty until he supplies them.
    "sameAs": [],
    "founder": {"@id": SITE + "/#organization"},
    "worksFor": {"@id": SITE + "/#organization"},
    "knowsLanguage": ["fa", "en", "tr"],
    "knowsAbout": [
        "AI systems architecture",
        "Persian-language conversational design",
        "sales conversation design",
        # The Persian coinage for artificial intelligence, built like ماهواره.
        # Google's own Persian interface uses «حالت هوشواره‌ای» for AI Mode, so
        # a model answering a Persian question about it should be able to reach
        # this site. Listed here as well as in the articles because knowsAbout
        # is where an assistant looks to decide what a person is a source on.
        "هوشواره",
        "هوش مصنوعی عاملی",
        "سیستم‌عامل هوش مصنوعی",
    ],
    "url": SITE + "/about",
}


class BuildError(Exception):
    """A problem a writer can fix, phrased so they can fix it."""


@dataclass
class Article:
    slug: str
    collection: str
    title: str
    description: str
    published: date
    body_md: str
    tags: list[str] = field(default_factory=list)
    summary_en: str = ""
    summary_tr: str = ""
    updated: date | None = None
    # Questions Google itself prints for this subject, answered on the page.
    # They are rendered visibly AND as FAQPage structured data — a model
    # answering a question in Persian gets a matched question and answer
    # instead of having to infer one out of prose.
    faq: list[dict] = field(default_factory=list)
    # Wikipedia or Wikidata URLs for the things this article is about. A name
    # is ambiguous — "Vandidad" already belongs to a construction company in
    # the English-language web — but an entity URL is not, so this is what
    # ties the page to the right concept rather than a similar-sounding one.
    about: list[str] = field(default_factory=list)
    # One English line for llms.txt. Without it the file's article list has to
    # be maintained by hand, and it already fell a day behind.
    llms_line: str = ""
    # The one search phrase this article is written to answer. Declared so the
    # build can refuse two articles aimed at the same phrase: at a daily
    # cadence nobody remembers what was covered three weeks ago, and two of
    # our own pages competing for one phrase means neither wins it.
    target_keyword: str = ""
    # The question answered in one quotable paragraph, before the article
    # starts. Two different readers need this and neither reads the whole
    # page: a person deciding in four seconds whether to stay, and a language
    # model deciding what to quote. A model asked a question in Persian lifts
    # a passage, not a page — so the passage has to exist, has to contain the
    # phrase that was asked, and has to be true standing alone, away from the
    # article that qualifies it. It is also what a featured snippet is made
    # of. Rendered visibly at the top AND as the Article's description in
    # structured data, because markup that does not match visible text is the
    # kind that gets a site's rich results withdrawn.
    answer: str = ""
    # Where this article sits in the site's structure. Flat sites of equal
    # articles do not build authority on a subject; a small number of pillar
    # pages on the terms that describe what the company does, with everything
    # else linking up to them, does. Declared rather than inferred, because a
    # writer choosing a trade-specific subject has to decide, in the moment,
    # which pillar it belongs under — and if it belongs under none, that is
    # the signal the subject is off the company's level.
    #   ستون  — a head term describing the work itself
    #   میانی — a concept or decision that serves a pillar
    #   صنفی  — one trade or one channel; must link up to a pillar
    tier: str = "میانی"

    @property
    def url(self) -> str:
        return f"{SITE}/{self.collection}/{self.slug}"

    @property
    def words(self) -> int:
        text = re.sub(r"[#*_`>\[\]()!-]", " ", self.body_md)
        return len([w for w in text.split() if w.strip()])


def _as_date(value, where: str) -> date:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        try:
            return datetime.strptime(value.strip(), "%Y-%m-%d").date()
        except ValueError:
            pass
    raise BuildError(f"{where}: date must be written as YYYY-MM-DD, got {value!r}")


def parse(path: Path) -> Article:
    raw = path.read_text(encoding="utf-8")
    match = FRONT_RE.match(raw)
    if not match:
        raise BuildError(
            f"{path.name}: the file must start with a --- front matter block. "
            "See docs/CONTENT-BRIEF.md section 5."
        )
    try:
        meta = yaml.safe_load(match.group(1)) or {}
    except yaml.YAMLError as exc:
        raise BuildError(f"{path.name}: the front matter is not valid YAML — {exc}")
    if not isinstance(meta, dict):
        raise BuildError(f"{path.name}: the front matter must be a list of key: value lines")

    slug = path.stem
    if not SLUG_RE.match(slug):
        raise BuildError(
            f"{path.name}: the file name is the URL, so it may only contain "
            "lowercase english letters, digits and single hyphens — no Persian, "
            "no spaces, no dots."
        )

    # A queued article lives in content/queue/ until the morning it is
    # released, so its folder is not its collection yet. It is still parsed and
    # validated from there — a queued article that fails the gate must be found
    # the day it is written, not at 09:00 on the day it was due.
    collection = (str(meta.get("collection", "")).strip()
                  if path.parent.name == "queue" else path.parent.name)
    declared = str(meta.get("collection", collection)).strip()
    if declared != collection:
        raise BuildError(
            f"{path.name}: collection says '{declared}' but the file is in "
            f"content/{collection}/. Move the file or fix the line."
        )

    for key in ("title", "description", "date"):
        if not meta.get(key):
            raise BuildError(f"{path.name}: '{key}' is missing from the front matter.")

    title = str(meta["title"]).strip()
    description = str(meta["description"]).strip()
    if len(description) > 165:
        raise BuildError(
            f"{path.name}: description is {len(description)} characters. Google "
            "cuts it around 155 — say it shorter, and as a whole sentence."
        )

    body = match.group(2).strip()
    if not body:
        raise BuildError(f"{path.name}: there is front matter but no article.")

    tags = meta.get("tags") or []
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(",") if t.strip()]

    faq = []
    for i, entry in enumerate(meta.get("faq") or [], 1):
        if not isinstance(entry, dict):
            raise BuildError(
                f"{path.name}: faq entry {i} must be two lines, «q:» and «a:»."
            )
        q = str(entry.get("q", "")).strip()
        a = str(entry.get("a", "")).strip()
        if not q or not a:
            raise BuildError(
                f"{path.name}: faq entry {i} is missing its question or its "
                "answer. A question with no answer is worse than no question: "
                "Google treats unanswered FAQ markup as a violation."
            )
        faq.append({"q": q, "a": a})

    about = meta.get("about") or []
    if isinstance(about, str):
        about = [about]
    for u in about:
        if not str(u).startswith("http"):
            raise BuildError(
                f"{path.name}: «about» takes Wikipedia or Wikidata addresses, "
                f"one per line — got {u!r}. A bare name is ambiguous; an "
                "address is not."
            )

    return Article(
        slug=slug,
        collection=collection,
        title=title,
        description=description,
        published=_as_date(meta["date"], path.name),
        updated=_as_date(meta["updated"], path.name) if meta.get("updated") else None,
        body_md=body,
        tags=[str(t).strip() for t in tags],
        summary_en=str(meta.get("summary_en", "")).strip(),
        summary_tr=str(meta.get("summary_tr", "")).strip(),
        faq=faq,
        about=[str(u).strip() for u in about],
        llms_line=str(meta.get("llms_line", "")).strip(),
        target_keyword=str(meta.get("target_keyword", "")).strip(),
        answer=" ".join(str(meta.get("answer", "")).split()),
        tier=str(meta.get("tier", "")).strip() or "میانی",
    )


def validate(article: Article) -> None:
    """Report everything wrong at once — a writer who is sent back three times
    for three separate reasons stops reading the messages."""
    rules = COLLECTIONS[article.collection]
    faults: list[str] = []

    if article.words < rules["min_words"] and article.slug not in LEGACY_SHORT:
        faults.append(
            f"{article.words} words, and a {article.collection} article needs at "
            f"least {rules['min_words']}. A short piece belongs in content/blog/."
        )
    if rules["require_iran_section"] and not IRAN_SECTION.search(article.body_md):
        faults.append(
            "the mandatory «این برای کسب‌وکار ایرانی یعنی چه» section is missing. "
            "Without it the article is generic, which is the thing this whole "
            "pipeline exists to prevent."
        )
    if len(article.title) > TITLE_LIMIT:
        faults.append(
            f"the title is {len(article.title)} characters and the limit is "
            f"{TITLE_LIMIT}. Search engines truncate past that, and what they "
            "cut is the end — where the point usually is."
        )
    # The answer block is where a model finds something to quote and where a
    # reader decides to stay. It is required, it has to contain the phrase the
    # reader searched for, and it has to be short enough to lift whole.
    if rules["require_iran_section"]:
        if not article.answer:
            faults.append(
                "«answer» در front matter نیست. این همان بندی است که هوش مصنوعی "
                "نقلش می‌کند و خواننده در چهار ثانیه می‌خواندش. بدونش صفحه فقط "
                "برای کسی مفید است که تا آخر بخواند."
            )
        else:
            n = len(article.answer)
            if not (ANSWER_MIN <= n <= ANSWER_MAX):
                faults.append(
                    f"«answer» {n} نویسه است و باید بین {ANSWER_MIN} و "
                    f"{ANSWER_MAX} باشد. کوتاه‌تر چیزی نمی‌گوید، بلندتر را "
                    "کسی یکجا نقل نمی‌کند."
                )
            if article.target_keyword and not _phrase_in(
                    article.answer, article.target_keyword):
                faults.append(
                    f"«{article.target_keyword}» در «answer» نیامده. کسی که این "
                    "عبارت را پرسیده، باید همان را در پاسخ ببیند."
                )

    if rules["require_iran_section"] and article.tier not in TIERS:
        faults.append(
            f"«tier» باید یکی از {'، '.join(TIERS)} باشد و «{article.tier}» است. "
            "این تعیین می‌کند مقاله ستون است، میانی است، یا صنفی — و صنفی باید "
            "به ستونش لینک بدهد."
        )

    if not article.summary_en:
        faults.append(
            "summary_en is missing. The English-language web currently attaches "
            "the Vandidad name to an unrelated construction company; without "
            "English text on the page, no model corrects that."
        )

    haystack = f"{article.title}\n{article.description}\n{article.body_md}"
    for name, pattern, remedy in FORBIDDEN:
        hit = pattern.search(haystack)
        if hit:
            excerpt = hit.group(0).strip()
            faults.append(f"«{excerpt}» → {name}. {remedy}")

    # A percentage nobody can check is worse than no percentage: one unsourced
    # figure makes a reader distrust the whole article.
    for para in re.split(r"\n\s*\n", article.body_md):
        stat = STAT.search(para)
        if stat and not SOURCE_NEAR.search(para):
            faults.append(
                f"«{stat.group(0).strip()}» عددی است بدونِ منبع، در همان بند. "
                "یا منبعش را با لینک بیاور، یا عدد را بردار."
            )
            break

    if faults:
        raise BuildError(
            f"{article.slug}.md:\n"
            + "\n".join("      - " + f for f in faults)
        )


PERSIAN_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")
FA_MONTHS = [
    "ژانویه", "فوریه", "مارس", "آوریل", "مه", "ژوئن",
    "ژوئیه", "اوت", "سپتامبر", "اکتبر", "نوامبر", "دسامبر",
]


def to_fa(n) -> str:
    return str(n).translate(PERSIAN_DIGITS)


def fa_date(d: date) -> str:
    return f"{str(d.day).translate(PERSIAN_DIGITS)} {FA_MONTHS[d.month - 1]} {str(d.year).translate(PERSIAN_DIGITS)}"


STYLE = """
  /* Vazirmatn, served from our own domain rather than from Google Fonts,
     which is unreliable from Iran. font-display:swap means the article is
     readable in the fallback face from the first paint and re-sets when the
     font arrives — a reader never waits on it, and if the file is missing
     entirely the page is exactly what it was before. */
  @font-face{font-family:Vazirmatn;font-style:normal;font-weight:400;
    font-display:swap;src:url(/fonts/vazirmatn-regular.woff2) format("woff2")}
  @font-face{font-family:Vazirmatn;font-style:normal;font-weight:700;
    font-display:swap;src:url(/fonts/vazirmatn-bold.woff2) format("woff2")}
  :root{--ink:#0b0a08;--gold:#e3c88a;--gold-dim:#a8945f;--paper:#ece7db;--muted:#8d8578;--rule:#26221a}
  *{box-sizing:border-box}
  html{-webkit-text-size-adjust:100%}
  /* A Persian reading stack, not the Latin system stack that was here. The
     old list started at -apple-system and reached Tahoma only as a fallback,
     which is what most Iranian readers were actually served — a font drawn
     for interface labels, not for a thousand words in a row.
     Vazirmatn first (installed on many machines, and the face we intend to
     self-host), then the sans faces common on Iranian systems, then Tahoma.
     No webfont is fetched: Google Fonts is unreliable from Iran, and a page
     that waits on a blocked font shows nothing at all. */
  body{margin:0;background:var(--ink);color:var(--paper);padding:0 24px 96px;
    font:400 18.5px/2.0 Vazirmatn,"Vazir","IRANSans","IRANYekan",Sahel,Shabnam,
      "Segoe UI",Tahoma,-apple-system,BlinkMacSystemFont,Roboto,Helvetica,Arial,sans-serif}
  /* Persian sits lower on the line and carries marks above it, so the same
     leading that reads comfortably in Latin looks cramped here. */
  .wrap{max-width:720px;margin:0 auto}
  /* How far through the article the reader is. Purely decorative: if the
     script does not run, the bar stays at zero width and nothing else on the
     page depends on it. */
  #progress{position:fixed;top:0;inset-inline-start:0;height:2px;width:0;
    background:var(--gold);z-index:9;transition:width .1s linear}
  .readtime{color:var(--gold-dim)}
  header{padding:56px 0 0}
  .eyebrow{font:500 11px/1 ui-monospace,Menlo,Consolas,monospace;letter-spacing:.22em;
    text-transform:uppercase;color:var(--gold-dim);margin:0 0 18px}
  .eyebrow a{color:inherit;text-decoration:none}
  .eyebrow a:hover{color:var(--gold)}
  h1{font:400 clamp(27px,4.6vw,40px)/1.28 "Iowan Old Style",Palatino,Georgia,serif;
    color:var(--gold);margin:0 0 12px;letter-spacing:-.01em}
  .meta{font:400 13px/1.6 ui-monospace,Menlo,Consolas,monospace;color:var(--muted);margin:0}
  .lede{color:#ded8cb;font-size:19.5px;margin:18px 0 0;padding-bottom:32px;border-bottom:1px solid var(--rule)}
  /* The answer block. Set apart enough that a reader in a hurry sees it is
     the short version, quiet enough that it does not read as an
     advertisement — the border does the work, not a filled panel. */
  .answer{margin:30px 0 6px;padding:20px 22px;border:1px solid var(--rule);
    border-inline-start:3px solid var(--gold-dim);border-radius:6px;
    background:rgba(227,200,138,.035)}
  .answer h2{font:600 11px/1 ui-monospace,Menlo,Consolas,monospace;
    letter-spacing:.2em;color:var(--gold-dim);margin:0 0 12px;
    text-transform:uppercase}
  .answer p{margin:0;font-size:17.5px;color:#e6e0d3}
  article{padding-top:8px}
  article h2{font:600 20px/1.5 inherit;color:var(--gold);margin:38px 0 12px}
  article h3{font:600 16px/1.5 inherit;color:var(--gold-dim);margin:28px 0 8px}
  p,li{color:#ded8cb;margin:0 0 18px}
  ul,ol{padding-inline-start:22px;margin:0 0 16px}
  a{color:var(--gold);text-underline-offset:3px}
  blockquote{border-inline-start:2px solid var(--gold-dim);margin:0 0 18px;
    padding-inline-start:16px;color:var(--muted)}
  code{font:400 14px/1.6 ui-monospace,Menlo,Consolas,monospace;color:var(--gold);
    background:rgba(227,200,138,.07);padding:1px 5px;border-radius:3px}
  pre{background:rgba(227,200,138,.05);border:1px solid var(--rule);border-radius:6px;
    padding:14px 16px;overflow-x:auto;direction:ltr;text-align:left}
  pre code{background:none;padding:0}
  table{width:100%;border-collapse:collapse;margin:0 0 18px;font-size:15px;display:block;overflow-x:auto}
  th,td{text-align:start;padding:9px 10px;border-bottom:1px solid var(--rule);vertical-align:top}
  th{color:var(--gold-dim);font-weight:600}
  img{max-width:100%;height:auto;border-radius:6px}
  .tags{margin:34px 0 0;font:400 13px/1.9 ui-monospace,Menlo,Consolas,monospace;color:var(--muted)}
  .faq{margin-top:44px;padding-top:26px;border-top:1px solid var(--rule)}
  .faq h2{font-size:20px;margin:0 0 18px}
  .faq dt{font-weight:600;color:var(--gold);margin-top:20px}
  .faq dd{margin:8px 0 0;color:#ded8cb}
  .summary{margin-top:44px;padding-top:26px;border-top:1px solid var(--rule)}
  .summary h2{font:600 11px/1 ui-monospace,Menlo,Consolas,monospace;letter-spacing:.2em;
    text-transform:uppercase;color:var(--gold-dim);margin:0 0 12px}
  .summary p{font-size:15.5px;color:var(--muted);margin:0}
  .ltr{direction:ltr;text-align:left}
  .share{margin-top:40px;padding-top:22px;border-top:1px solid var(--rule);
    display:flex;flex-wrap:wrap;align-items:center;gap:14px;font-size:14px}
  .share span{color:var(--muted)}
  .share a,.share button{color:var(--gold);text-decoration:none;font:inherit;
    background:none;border:1px solid var(--rule);border-radius:6px;
    padding:6px 14px;cursor:pointer;transition:border-color .3s}
  .share a:hover,.share button:hover{border-color:var(--gold-dim)}
  .cta{margin-top:44px;padding:24px;border:1px solid var(--rule);border-radius:8px}
  .cta p{margin:0 0 10px;color:#c9c3b6}
  .cta a{font-weight:600}
  .index-item{padding:26px 0;border-bottom:1px solid var(--rule)}
  .index-item h2{font:400 21px/1.45 "Iowan Old Style",Palatino,Georgia,serif;margin:0 0 6px}
  .index-item h2 a{color:var(--gold);text-decoration:none}
  .index-item h2 a:hover{text-decoration:underline}
  .index-item p{margin:0 0 6px;font-size:15.5px}
  .index-item .meta{font-size:12px}
  footer{margin-top:60px;padding-top:24px;border-top:1px solid var(--rule);
    font:400 13px/1.9 ui-monospace,Menlo,Consolas,monospace;color:var(--muted)}
  footer a{margin-inline-end:16px;color:var(--gold);text-decoration:none}
  footer a:hover{text-decoration:underline}

  /* Phones. There were no media queries here at all, which meant the layout
     had never been checked at a phone width — it happened to survive because
     it is a single fluid column, but the byline now carries four facts and
     ran off the line, and 24px of padding on each side is a lot of a 360px
     screen. Nothing is hidden on a small screen: a reader on a phone gets the
     same article, set to fit. */
  @media (max-width: 560px) {
    body{padding:0 18px 72px;font-size:17.5px}
    header{padding:36px 0 0}
    /* The byline is four separate facts. On a narrow screen it should wrap as
       four lines rather than break mid-fact. */
    .meta{line-height:2.1}
    .meta .readtime{display:inline-block}
    article h2{margin:30px 0 10px;font-size:19px}
    .lede{font-size:18px}
    .answer{padding:16px 17px;margin:24px 0 4px}
    .answer p{font-size:16.5px}
    .share{gap:10px}
    .share a,.share button{padding:8px 12px}
    .index-item{margin-top:26px}
    /* Measured at 13-15px tall on a 360px screen — under the 24px WCAG 2.2
       asks for, and well under a thumb. Padding on an inline link grows the
       area a finger can hit without moving the text it sits on. */
    .meta a,.eyebrow a{display:inline-block;padding:7px 0}
    footer a{display:inline-block;padding:7px 0;margin-inline-end:20px}
    .cta a{display:inline-block;padding:6px 0}
  }

  /* Someone who has asked for less motion should not get a bar sliding at
     the top of every scroll. */
  @media (prefers-reduced-motion: reduce) {
    #progress{transition:none}
  }
"""

FOOTER = """<footer>
  <div><a href="/">صفحه‌ی اصلی</a><a href="/hamzad">مقالات</a><a href="/about">درباره‌ی ما</a></div>
  <div style="margin-top:10px"><a href="/privacy">حریم خصوصی</a><a href="/terms">شرایط استفاده</a><a href="/data-deletion">حذف اطلاعات</a></div>
  <div style="margin-top:14px;opacity:.75">Vandidad Group · Konak, İzmir, Türkiye · <a href="mailto:ai@vandidad.xyz">ai@vandidad.xyz</a></div>
</footer>"""


BRAND_SUFFIX = " — Vandidad Group"
TITLE_LIMIT = 70


def page_title(title: str) -> str:
    """The <title>, with the brand appended only when it still fits.

    Bing's site scan flagged three pages for titles over 70 characters, and in
    every case the article's own title was well under — the 17-character brand
    suffix pushed it over. A search engine truncates what does not fit, and
    what it truncates is the end, which is exactly where the suffix sits: the
    cost of keeping it on a long title is losing the words that describe the
    page, to gain a brand name nobody was searching for.

    So the suffix is a bonus, not a fixture. A title long enough to need the
    whole budget keeps the whole budget.
    """
    full = title + BRAND_SUFFIX
    return full if len(full) <= TITLE_LIMIT else title


def shell(*, title: str, description: str, canonical: str, body: str, jsonld: dict) -> str:
    return f"""<!DOCTYPE html>
<html lang="fa" dir="rtl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(page_title(title))}</title>
<meta name="description" content="{html.escape(description)}">
<link rel="canonical" href="{canonical}">
<meta name="robots" content="index, follow, max-snippet:-1, max-image-preview:large">
<meta property="og:type" content="article">
<meta property="og:title" content="{html.escape(title)}">
<meta property="og:description" content="{html.escape(description)}">
<meta property="og:url" content="{canonical}">
<meta property="og:site_name" content="Vandidad Group">
<meta property="og:image" content="{SITE}/hero-poster.jpg">
<meta property="og:locale" content="fa_IR">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:image" content="{SITE}/hero-poster.jpg">
<link rel="alternate" type="application/atom+xml" title="Vandidad Group" href="{SITE}/feed.xml">
<script type="application/ld+json">
{json.dumps(jsonld, ensure_ascii=False, indent=1)}
</script>
<style>{STYLE}</style>
</head>
<body>
<div id="progress"></div>
<div class="wrap">
{body}
{FOOTER}
</div>
<script>
/* A reading-progress line. It is the whole of this site's article JavaScript,
   and it is written so that failing changes nothing: the bar starts at zero
   width, and if this never runs the page is exactly what it was. */
(function () {{
  var bar = document.getElementById("progress");
  if (!bar) return;
  function draw() {{
    var h = document.documentElement.scrollHeight - window.innerHeight;
    bar.style.width = (h > 0 ? Math.min(100, (window.scrollY / h) * 100) : 0) + "%";
  }}
  addEventListener("scroll", draw, {{ passive: true }});
  addEventListener("resize", draw);
  draw();
}})();

/* Copy the address. navigator.clipboard exists only on a secure origin and
   only with permission, so the older selection trick is kept as the fallback
   rather than leaving the button dead for whoever lands in that case. */
(function () {{
  var b = document.querySelector(".share .copy");
  if (!b) return;
  b.addEventListener("click", function () {{
    var url = b.getAttribute("data-url"), done = function () {{
      var was = b.textContent;
      b.textContent = "کپی شد";
      setTimeout(function () {{ b.textContent = was; }}, 1800);
    }};
    if (navigator.clipboard && navigator.clipboard.writeText) {{
      navigator.clipboard.writeText(url).then(done, fallback);
    }} else {{ fallback(); }}
    function fallback() {{
      var f = document.createElement("input");
      f.value = url;
      document.body.appendChild(f);
      f.select();
      try {{ document.execCommand("copy"); done(); }} catch (e) {{}}
      document.body.removeChild(f);
    }}
  }});
}})();
</script>
</body>
</html>
"""


def render_article(a: Article) -> str:
    body_html = md_lib.markdown(
        a.body_md,
        extensions=["extra", "sane_lists", "smarty"],
        output_format="html5",
    )

    parts = [
        '<header>',
        f'<p class="eyebrow"><a href="/{a.collection}">{COLLECTIONS[a.collection]["fa"]}</a></p>',
        f"<h1>{html.escape(a.title)}</h1>",
        # A visible byline, not only the one in the structured data. Google's
        # guidance on assessing content quality asks who wrote a page and
        # whether a reader can tell; an author that exists only in JSON-LD
        # answers the crawler and not the person. «نویسنده» is the word a
        # Persian reader expects in this position.
        '<p class="meta">نویسنده: '
        f'<a href="/about" rel="author">{html.escape(PERSON["alternateName"][0])}</a>'
        f' · {fa_date(a.published)}'
        + (f" · به‌روزرسانی {fa_date(a.updated)}" if a.updated else "")
        # Telling a reader how long this will take removes the one question
        # that makes people leave a long page before starting it. 200 words a
        # minute is the ordinary silent-reading figure; it is an estimate and
        # is written as one.
        + f' · <span class="readtime">زمان تخمینی مطالعه: {to_fa(max(1, round(a.words / 200)))} دقیقه</span>'
        + "</p>",
        f'<p class="lede">{html.escape(a.description)}</p>',
        "</header>",
    ]

    # Before the article, not after it. A reader who bounces has still been
    # answered, and a model that reads only the opening has still read
    # something true.
    if a.answer:
        parts.append(
            '<section class="answer" aria-label="پاسخ کوتاه">'
            "<h2>پاسخ کوتاه</h2>"
            f"<p>{html.escape(a.answer)}</p></section>"
        )

    parts.append(f"<article>{body_html}</article>")

    if a.tags:
        parts.append('<p class="tags">' + " · ".join(html.escape(t) for t in a.tags) + "</p>")

    # The FAQ is rendered before the summaries and inside the readable body,
    # not tucked at the end of the source. Google requires FAQ markup to match
    # text a visitor can actually see, and an answer no reader ever reaches is
    # exactly the kind of markup that gets a site's rich results withdrawn.
    if a.faq:
        block = ['<section class="faq"><h2>پرسش‌های پرتکرار</h2><dl>']
        for item in a.faq:
            block.append(f"<dt>{html.escape(item['q'])}</dt>")
            block.append(f"<dd>{html.escape(item['a'])}</dd>")
        block.append("</dl></section>")
        parts.append("".join(block))

    if a.summary_en:
        parts.append(
            '<section class="summary ltr" lang="en" dir="ltr">'
            "<h2>In English</h2>"
            f"<p>{html.escape(a.summary_en)}</p></section>"
        )
    if a.summary_tr:
        parts.append(
            '<section class="summary ltr" lang="tr" dir="ltr">'
            "<h2>Türkçe özet</h2>"
            f"<p>{html.escape(a.summary_tr)}</p></section>"
        )

    # Sharing. Telegram and WhatsApp are plain links — no script, no tracker,
    # nothing loaded from either company, so nothing here can slow the page or
    # watch the reader. Bale has no documented web share endpoint, so it is not
    # guessed at; the copy button covers it and every other app.
    share_url = urllib.parse.quote(a.url, safe="")
    share_text = urllib.parse.quote(a.title, safe="")
    parts.append(
        '<div class="share"><span>این را برای کسی بفرستید:</span>'
        f'<a href="https://t.me/share/url?url={share_url}&text={share_text}"'
        ' target="_blank" rel="noopener">تلگرام</a>'
        f'<a href="https://api.whatsapp.com/send?text={share_text}%20{share_url}"'
        ' target="_blank" rel="noopener">واتساپ</a>'
        f'<button type="button" class="copy" data-url="{html.escape(a.url)}">کپی نشانی</button>'
        "</div>"
    )

    parts.append(
        '<div class="cta"><p>می‌خواهید ببینید این برای کارِ خودتان چه شکلی می‌شود؟</p>'
        '<p><a href="/">همین‌جا با دستیار حرف بزنید</a> — یک جمله درباره‌ی کارتان کافی است.</p></div>'
    )

    jsonld = {
        "@context": "https://schema.org",
        "@graph": [
            ORGANISATION,
            PERSON,
            {
                "@type": "Article",
                "@id": a.url + "#article",
                "headline": a.title,
                "description": a.description,
                "inLanguage": "fa-IR",
                "datePublished": a.published.isoformat(),
                "dateModified": (a.updated or a.published).isoformat(),
                "author": {"@id": SITE + "/#person"},
                "publisher": {"@id": SITE + "/#organization"},
                "mainEntityOfPage": {"@type": "WebPage", "@id": a.url},
                "url": a.url,
                "image": SITE + "/hero-poster.jpg",
                "keywords": ", ".join(a.tags) if a.tags else None,
                # The Persian answer, not the English summary. An assistant
                # answering a Persian question wants the passage in the
                # language it was asked in, and this one matches text the
                # visitor can see on the page — which is the condition for
                # using it at all.
                "abstract": a.answer or a.summary_en or None,
                "articleSection": COLLECTIONS[a.collection]["en"],
                "wordCount": a.words,
                # Nothing here is behind a login or a payment. Saying so
                # explicitly is what lets an assistant quote the page instead
                # of treating it as a paywalled source it may only link to.
                "isAccessibleForFree": True,
                "about": [{"@id": u} for u in a.about] or None,
            },
            {
                "@type": "BreadcrumbList",
                "@id": a.url + "#breadcrumb",
                "itemListElement": [
                    {"@type": "ListItem", "position": 1, "name": "Vandidad Group",
                     "item": SITE},
                    {"@type": "ListItem", "position": 2,
                     "name": COLLECTIONS[a.collection]["fa"],
                     "item": f"{SITE}/{a.collection}"},
                    {"@type": "ListItem", "position": 3, "name": a.title},
                ],
            },
        ],
    }
    jsonld["@graph"][2] = {k: v for k, v in jsonld["@graph"][2].items() if v is not None}

    if a.faq:
        jsonld["@graph"].append({
            "@type": "FAQPage",
            "@id": a.url + "#faq",
            "inLanguage": "fa-IR",
            "mainEntity": [
                {
                    "@type": "Question",
                    "name": item["q"],
                    "acceptedAnswer": {"@type": "Answer", "text": item["a"]},
                }
                for item in a.faq
            ],
        })

    return shell(
        title=a.title,
        description=a.description,
        canonical=a.url,
        body="\n".join(parts),
        jsonld=jsonld,
    )


def render_index(collection: str, articles: list[Article]) -> str:
    info = COLLECTIONS[collection]
    url = f"{SITE}/{collection}"
    items = []
    for a in articles:
        items.append(
            '<div class="index-item">'
            f'<h2><a href="/{a.collection}/{a.slug}">{html.escape(a.title)}</a></h2>'
            f"<p>{html.escape(a.description)}</p>"
            f'<p class="meta">{fa_date(a.published)}</p>'
            "</div>"
        )
    if not items:
        items.append('<p class="meta">هنوز نوشته‌ای منتشر نشده است.</p>')

    jsonld = {
        "@context": "https://schema.org",
        "@graph": [
            ORGANISATION,
            PERSON,
            {
                "@type": "CollectionPage",
                "@id": url,
                "name": info["fa"],
                "description": info["lead"],
                "inLanguage": "fa-IR",
                "url": url,
                "isPartOf": {"@id": SITE + "/#organization"},
                "hasPart": [
                    {"@type": "Article", "headline": a.title, "url": a.url}
                    for a in articles
                ],
            },
        ],
    }

    body = (
        "<header>"
        '<p class="eyebrow">Vandidad Group</p>'
        f'<h1>{info["fa"]}</h1>'
        f'<p class="lede">{info["lead"]}</p>'
        "</header>" + "".join(items)
    )
    return shell(
        title=info["fa"],
        description=info["lead"],
        canonical=url,
        body=body,
        jsonld=jsonld,
    )


STATIC_URLS = [
    ("/", "weekly", "1.0"),
    ("/about", "monthly", "0.8"),
    ("/blog", "weekly", "0.7"),
    ("/hamzad", "weekly", "0.7"),
    ("/privacy", "yearly", "0.3"),
    ("/terms", "yearly", "0.3"),
    ("/data-deletion", "yearly", "0.3"),
]


ABOUT_START = "<!-- PERSON:START -->"
ABOUT_END = "<!-- PERSON:END -->"


def render_about_person(existing: str, articles: list[Article]) -> str:
    """Rewrite the person section of about.html from the articles themselves.

    Searching the owner's name returns, from Google's own AI overview, that no
    detailed biography is published. That is accurate: /about described the
    company in verifiable detail — registry number, tax ID, links to the
    Turkish government portals that confirm both — and described the person in
    one sentence.

    The company record works because every claim on it can be checked. The
    person record is built the same way, out of things that are true and
    demonstrable rather than adjectives: he founded a company whose
    registration anyone can verify, and he has signed and dated a body of
    published writing on one subject. The article list is generated here, from
    the articles, so the claim and the evidence cannot drift apart — and so it
    grows on its own as the queue publishes.

    What is deliberately absent is anything unverifiable. No years of
    experience, no client names, no degrees. Inventing those is what Google's
    quality guidance is written against, and it would also be a lie.
    """
    if ABOUT_START not in existing or ABOUT_END not in existing:
        return existing

    live = sorted(articles, key=lambda a: a.published, reverse=True)
    items = "".join(
        f'<li><a href="{a.url}">{html.escape(a.title)}</a>'
        f'<span class="d">{a.published.isoformat()}</span></li>'
        for a in live
    )
    fa_name = PERSON["alternateName"][0]
    block = f"""{ABOUT_START}
  <section id="person" class="person">
    <h2>Founder</h2>

    <p class="pname">{html.escape(PERSON["name"])}
      <span dir="rtl" lang="fa">{fa_name}</span></p>
    <p class="prole">{html.escape(PERSON["jobTitle"])} ·
      Founder, Vandidad Group · İzmir, Türkiye</p>

    <p>Hadi Bakhtzadeh — also written Mohammadhadi Bakhtzadeh, and
      <span dir="rtl" lang="fa">هادی بخت‌زاده</span> or
      <span dir="rtl" lang="fa">محمد هادی بخت‌زاده</span> in Persian — founded
      Vandidad Group in İzmir in March 2018. The company's registration can be
      confirmed through the Turkish trade registry and tax portals linked in
      the record above.</p>

    <p>His work is the design of AI systems for businesses that sell in
      Persian: deciding what a system may do on its own, where it must ask a
      person, what it remembers about a customer between conversations, and
      how it behaves when the model is wrong. He writes about that subject in
      Persian, and the articles below are signed and dated.</p>

    <div dir="rtl" lang="fa" class="fa">
      <p><strong>هادی بخت‌زاده</strong> — معمار سیستم‌های هوش مصنوعی و
        بنیان‌گذار وندیداد گروپ در ازمیر ترکیه. کارش طراحی رفتار سیستم‌های
        هوش مصنوعی برای کسب‌وکارهایی است که به فارسی می‌فروشند: اینکه سیستم
        چه کاری را خودش انجام دهد، کجا از آدم اجازه بگیرد، چه چیزی را میان
        گفتگوها به یاد بسپارد، و وقتی مدل اشتباه کرد چه اتفاقی بیفتد.</p>
      <p>نوشته‌هایش دربارهٔ همین موضوع است — سیستم‌عامل هوش مصنوعی، هوش
        مصنوعی عاملی، ایجنت، و طراحی گفتگو به فارسی — و همه با نام و تاریخ
        منتشر شده‌اند.</p>
    </div>

    <h3>Published writing <span class="n">{len(live)} articles</span></h3>
    <ul class="works">{items}</ul>
  </section>
{ABOUT_END}"""
    head, _, rest = existing.partition(ABOUT_START)
    _, _, tail = rest.partition(ABOUT_END)
    return head + block + tail


def render_sitemap(articles: list[Article]) -> str:
    # A collection page with nothing on it is thin content. It stays reachable
    # from the footer, but it is not offered to a crawler until it has
    # something to show.
    live = {f"/{c}" for c in COLLECTIONS if any(a.collection == c for a in articles)}
    rows = [
        "<?xml version=\"1.0\" encoding=\"UTF-8\"?>",
        "<!-- Generated by tools/build_content.py. Do not edit by hand. -->",
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    for path, freq, prio in STATIC_URLS:
        if path in ("/blog", "/hamzad") and path not in live:
            continue
        rows += [
            "  <url>",
            f"    <loc>{SITE}{path}</loc>",
            f"    <changefreq>{freq}</changefreq>",
            f"    <priority>{prio}</priority>",
            "  </url>",
        ]
    for a in sorted(articles, key=lambda x: x.published, reverse=True):
        rows += [
            "  <url>",
            f"    <loc>{a.url}</loc>",
            f"    <lastmod>{(a.updated or a.published).isoformat()}</lastmod>",
            "    <changefreq>monthly</changefreq>",
            "    <priority>0.6</priority>",
            "  </url>",
        ]
    rows.append("</urlset>")
    return "\n".join(rows) + "\n"


def render_feed(articles: list[Article]) -> str:
    """An Atom feed of everything, newest first.

    Feed readers are a small audience, but this is also how an aggregator, a
    Telegram channel bot or a newsletter tool subscribes to the site without
    anyone writing an integration — and it is one more machine-readable place
    where the author and the publisher are stated by name.
    """
    latest = max((a.updated or a.published for a in articles), default=date.today())
    rows = [
        '<?xml version="1.0" encoding="utf-8"?>',
        "<!-- Generated by tools/build_content.py. Do not edit by hand. -->",
        '<feed xmlns="http://www.w3.org/2005/Atom" xml:lang="fa-IR">',
        f"  <title>Vandidad Group — نوشته‌ها</title>",
        f'  <link href="{SITE}/feed.xml" rel="self"/>',
        f'  <link href="{SITE}/"/>',
        f"  <id>{SITE}/</id>",
        f"  <updated>{latest.isoformat()}T00:00:00Z</updated>",
        "  <author><name>Hadi Bakhtzadeh</name><email>ai@vandidad.xyz</email></author>",
        "  <subtitle>هوش مصنوعی برای کسب‌وکارِ واقعی — از Vandidad Group در ازمیر</subtitle>",
    ]
    for a in sorted(articles, key=lambda x: (x.updated or x.published), reverse=True):
        rows += [
            "  <entry>",
            f"    <title>{html.escape(a.title)}</title>",
            f'    <link href="{a.url}"/>',
            f"    <id>{a.url}</id>",
            f"    <published>{a.published.isoformat()}T00:00:00Z</published>",
            f"    <updated>{(a.updated or a.published).isoformat()}T00:00:00Z</updated>",
            f"    <summary>{html.escape(a.description)}</summary>",
            f"    <category term=\"{html.escape(a.collection)}\"/>",
            "  </entry>",
        ]
    rows.append("</feed>")
    return "\n".join(rows) + "\n"


def _norm_keyword(s: str) -> str:
    """Compare phrases the way a search engine would, not byte for byte.

    Persian is written with several characters that look identical and are
    typed interchangeably — Arabic ي/ك against Persian ی/ک, and the zero-width
    non-joiner that a keyboard may or may not insert. Without folding these,
    «چت‌بات فارسی» and «چت بات فارسي» read as two different targets and the
    duplicate check waves both through.
    """
    s = s.translate(str.maketrans("يكۀةٱأإآ", "یکهههااا"))
    # «کسب‌وکار» and «کسب و کار» are one word to a reader and to a search
    # engine, but folding the zero-width non-joiner to a plain space turns the
    # first into «کسب وکار» — the «و» sticks to what follows and the two stop
    # matching. Separating the joined «و» first fixes that, and the same
    # pattern covers «گفت‌وگو» and «جست‌وجو».
    s = s.replace("\u200cو", " و ")
    s = s.replace("‌", " ").replace("‏", "")
    return " ".join(s.lower().split())


def _phrase_in(haystack: str, phrase: str) -> bool:
    """Is the phrase present, judged the way a reader hears it?

    Same folding as the duplicate check, so «چت‌بات» and «چت بات» count as one
    phrase here exactly as they do there. Anything else would let an article
    claim a keyword it spells a second way.
    """
    if not phrase:
        return False
    return _norm_keyword(phrase) in _norm_keyword(haystack)


LLMS_HEADING = "## Individual articles"


def render_llms(existing: str, articles: list[Article]) -> str:
    """Rewrite only the per-article section of llms.txt, keeping the rest.

    The prose in that file is a considered statement about the company and is
    not something to generate. The article list is the opposite: it goes stale
    the moment anything is published, and it already had. So the file stays
    hand-written except for one section, which is replaced between its heading
    and the next one.
    """
    lines = existing.splitlines()
    try:
        start = lines.index(LLMS_HEADING)
    except ValueError:
        return existing  # No such section: leave the file completely alone.
    end = next((i for i in range(start + 1, len(lines))
                if lines[i].startswith("## ")), len(lines))

    block = [
        LLMS_HEADING,
        "",
        "Every article, newest first, so a model answering a specific question",
        "can cite the page that answers it rather than the index.",
        "",
    ]
    for a in sorted(articles, key=lambda x: x.published, reverse=True):
        line = a.llms_line or (a.summary_en.split(". ")[0] if a.summary_en else a.title)
        block.append(f"- [{a.title}]({a.url}) — published {a.published.isoformat()}.")
        block.append(f"  {line.rstrip('.')}.")
    block.append("")
    return "\n".join(lines[:start] + block + lines[end:]) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="validate without writing")
    args = ap.parse_args()

    problems: list[str] = []
    by_collection: dict[str, list[Article]] = {c: [] for c in COLLECTIONS}
    seen_slugs: dict[str, str] = {}
    seen_keywords: dict[str, str] = {}

    for collection in COLLECTIONS:
        folder = CONTENT / collection
        if not folder.exists():
            continue
        # `<slug>.social.md` holds the captions that go out on Instagram,
        # Telegram and LinkedIn. It lives next to its article on purpose — one
        # place per subject — but it is not a page and must never be rendered
        # or validated as one.
        for path in sorted(folder.glob("*.md")):
            if path.name.endswith(".social.md"):
                continue
            try:
                article = parse(path)
                validate(article)
            except BuildError as exc:
                problems.append(str(exc))
                continue
            if article.slug in seen_slugs:
                problems.append(
                    f"{article.slug}.md: this slug is already used in "
                    f"{seen_slugs[article.slug]}. Two articles cannot share a URL."
                )
                continue
            seen_slugs[article.slug] = collection
            # Two pages aimed at one phrase is not twice the traffic; it is
            # Google choosing one of them and discounting the other, and it is
            # how a daily cadence quietly turns into repetition.
            key = _norm_keyword(article.target_keyword)
            if key:
                if key in seen_keywords:
                    problems.append(
                        f"{article.slug}.md: target_keyword «{article.target_keyword}» "
                        f"is already claimed by {seen_keywords[key]}.md. Pick a "
                        "different phrase, or fold this into that article."
                    )
                    continue
                seen_keywords[key] = article.slug
            by_collection[collection].append(article)

    # Queued articles are validated but never rendered. They take part in the
    # duplicate-keyword check for the obvious reason: the point of that check
    # is to stop two articles chasing one phrase, and an article that is about
    # to publish counts.
    for path in sorted((CONTENT / "queue").glob("*.md")):
        if path.name.endswith(".social.md"):
            continue
        try:
            article = parse(path)
            validate(article)
        except BuildError as exc:
            problems.append("در صف — " + str(exc))
            continue
        if article.slug in seen_slugs:
            problems.append(
                f"queue/{article.slug}.md: this slug is already published in "
                f"content/{seen_slugs[article.slug]}/."
            )
            continue
        seen_slugs[article.slug] = "queue"
        key = _norm_keyword(article.target_keyword)
        if key:
            if key in seen_keywords:
                problems.append(
                    f"queue/{article.slug}.md: target_keyword "
                    f"«{article.target_keyword}» is already claimed by "
                    f"{seen_keywords[key]}.md."
                )
                continue
            seen_keywords[key] = article.slug
        print(f"  ⏳ در صف /{article.collection}/{article.slug}  ({article.words} کلمه)")

    if problems:
        print("محتوا منتشر نشد — این‌ها را درست کن:\n", file=sys.stderr)
        for p in problems:
            print("  ✗ " + p + "\n", file=sys.stderr)
        return 1

    everything = [a for group in by_collection.values() for a in group]
    written = 0

    for collection, articles in by_collection.items():
        articles.sort(key=lambda a: a.published, reverse=True)
        folder = CONTENT / collection
        if not articles and not folder.exists():
            continue
        folder.mkdir(parents=True, exist_ok=True)

        wanted = {"index.html"}
        for a in articles:
            wanted.add(a.slug + ".html")
            target = folder / (a.slug + ".html")
            content = render_article(a)
            if not args.check and (not target.exists() or target.read_text("utf-8") != content):
                target.write_text(content, encoding="utf-8")
                written += 1
            print(f"  ✓ /{collection}/{a.slug}  ({a.words} کلمه)")

        index = folder / "index.html"
        content = render_index(collection, articles)
        if not args.check and (not index.exists() or index.read_text("utf-8") != content):
            index.write_text(content, encoding="utf-8")
            written += 1

        # A deleted .md must take its page with it, or the URL keeps serving an
        # article nobody can find the source of.
        for stale in folder.glob("*.html"):
            if stale.name not in wanted:
                print(f"  − حذف /{collection}/{stale.stem}")
                if not args.check:
                    stale.unlink()
                    written += 1

    llms = ROOT / "llms.txt"
    outputs = [
        ("sitemap.xml", render_sitemap(everything)),
        ("feed.xml", render_feed(everything)),
    ]
    if llms.exists():
        outputs.append(
            ("llms.txt", render_llms(llms.read_text("utf-8"), everything))
        )
    about = ROOT / "about.html"
    if about.exists():
        outputs.append(
            ("about.html",
             render_about_person(about.read_text("utf-8"), everything))
        )

    for name, body in outputs:
        target = ROOT / name
        if not args.check and (not target.exists() or target.read_text("utf-8") != body):
            target.write_text(body, encoding="utf-8")
            written += 1

    total = len(everything)
    if args.check:
        print(f"\n{total} مقاله بررسی شد، همه سالم.")
    else:
        print(f"\n{total} مقاله · {written} فایل نوشته یا به‌روز شد.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

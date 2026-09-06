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

# The Persian page that identifies the founder. Declared next to SITE
# because the Person entity below points at it: that page, not /about,
# is the URL a search engine should attach the person to.
PERSON_SLUG = "hadi-bakhtzadeh"
PERSON_URL = f"{SITE}/{PERSON_SLUG}"

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
    # Everything below can be checked by a stranger against a government
    # register, which is the only kind of credential worth putting in
    # structured data. The numbers and the verification portals are already
    # printed on /about; this is the machine-readable form of the same claim.
    "foundingDate": "2018-03-15",
    "taxID": "9220834963",
    "identifier": [
        {"@type": "PropertyValue", "name": "İzmir Trade Registry",
         "value": "202783"},
        {"@type": "PropertyValue", "name": "İzmir Chamber of Commerce",
         "value": "1888691"},
    ],
    "memberOf": {
        "@type": "Organization",
        "name": "İzmir Chamber of Commerce",
        "alternateName": "İzmir Ticaret Odası",
        "url": "https://www.izto.org.tr",
    },
    "legalName": (
        "Vandidad Group Gayrimenkul Danışmanlık Hizmetleri İthalat İhracat "
        "Ticaret Limited Şirketi"
    ),
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
    # Every spelling actually typed into a search box, including the ones that
    # look identical on screen and are different strings underneath. The
    # search «محمد هادی بخت زاده» — full space, not a zero-width joiner —
    # returned no trace of this site at all and Google offered محمدباقر نوبخت
    # and هادی نیک‌بخت instead. That spelling was missing from this list; the
    # near-identical ZWNJ form was present, which is not the same string to a
    # search engine.
    "alternateName": [
        "هادی بخت‌زاده",
        "هادی بخت زاده",
        "محمد هادی بخت‌زاده",
        "محمد هادی بخت زاده",
        "محمدهادی بخت‌زاده",
        "محمدهادی بخت زاده",
        "م. هادی بخت‌زاده",
        "Mohammadhadi Bakhtzadeh",
        "Mohammad Hadi Bakhtzadeh",
        "Hadi Bakhtzade",
        "Hadi Bahtzade",
        "M. Hadi Bakhtzadeh",
    ],
    "givenName": "Hadi",
    "familyName": "Bakhtzadeh",
    "jobTitle": "Architect of Intelligent Systems",
    "description": (
        "AI systems architect and founder of Vandidad Group, a technology "
        "company registered in İzmir, Türkiye (İzmir Trade Registry 202783, "
        "founded March 2018). Background in computer engineering, software "
        "architecture and artificial intelligence, with a research focus on "
        "distributed systems, natural language processing and autonomous AI "
        "agents. Designs the behaviour of AI systems for "
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
    # The page a machine should treat as this person's record. It is the
    # Persian one, because the searches that ask who he is are in Persian,
    # and an assistant answering in Persian needs a Persian page to quote.
    # /about still carries the same facts for anyone checking the company.
    "mainEntityOfPage": {"@type": "ProfilePage", "@id": PERSON_URL},
    # Profiles that confirm the same person elsewhere. sameAs is the strongest
    # identity signal there is and it cannot be invented: a wrong entry points
    # the entity at someone else. Only accounts demonstrably his belong here.
    #
    # All four are confirmed rather than guessed. GitHub owns the repository
    # this site is built and served from. The LinkedIn profile names Vandidad
    # Group and AIOS and gives İzmir as the location. The Instagram account
    # carries a verified badge, the same name in both spellings, and links
    # back to vandidad.xyz — a two-way link, which is what makes a sameAs
    # worth having. The site is listed last because a self-reference belongs
    # in the set an engine reconciles.
    "sameAs": [
        "https://github.com/vandidadhonar-sudo",
        "https://www.linkedin.com/in/hadi-bakhtzadeh-8089b1109",
        "https://www.instagram.com/hadi_bakhtzade/",
        # Confirmed by the owner. The X account is result one for the English
        # spelling of his name and the handle is taken from that result, not
        # constructed — a sameAs built from a guess points the entity at
        # someone else, which is the one mistake this field cannot absorb.
        "https://x.com/HadiBakhtzadeh",
        SITE,
    ],
    # A role with a start date, tied to an organisation whose registration is
    # public record. This is the part of his standing that does not rest on
    # anyone taking his word for it.
    "hasOccupation": {
        "@type": "Occupation",
        "name": "AI Systems Architect",
        "occupationalCategory": "15-1252 Software Developers",
        "responsibilities": (
            "Designing the behaviour of AI systems for business conversation: "
            "scope of autonomous action, escalation points, what persists "
            "between conversations, and behaviour under model failure."
        ),
    },
    "memberOf": {"@id": SITE + "/#organization"},
    "founder": {"@id": SITE + "/#organization"},
    "worksFor": {"@id": SITE + "/#organization"},
    "knowsLanguage": ["fa", "en", "tr"],
    "knowsAbout": [
        "AI systems architecture",
        # Subjects he has built in, each corresponding to a system in a
        # repository with a date on it — not subjects he could talk about.
        "multi-agent systems",
        "distributed systems",
        "natural language processing",
        "autonomous AI agents",
        "AI operating systems built for one industry",
        "real-estate AI systems",
        "cross-channel identity and conversation memory",
        "refusal design — what a system does when it does not know",
        "Persian-language conversational design",
        "sales conversation design",
        "هوش مصنوعی در املاک",
        # The Persian coinage for artificial intelligence, built like ماهواره.
        # Google's own Persian interface uses «حالت هوشواره‌ای» for AI Mode, so
        # a model answering a Persian question about it should be able to reach
        # this site. Listed here as well as in the articles because knowsAbout
        # is where an assistant looks to decide what a person is a source on.
        "هوشواره",
        "هوش مصنوعی عاملی",
        "سیستم‌عامل هوش مصنوعی",
    ],
    "url": PERSON_URL,
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
  /* Product cards on /mahsoolat. Each one is a system, so it is given the
     weight of a section rather than a list row: a rule above it, the kind of
     thing it is set beside the name, and the counted figure in the byline
     position where a date would otherwise sit alone. */
  .prod{margin:38px 0 0;padding-top:26px;border-top:1px solid var(--rule)}
  .prod h2{margin:0 0 6px;font-size:23px}
  .prod .pk{display:block;font:500 12px/1.7 ui-monospace,Menlo,Consolas,monospace;
    letter-spacing:.08em;color:var(--gold-dim);margin-top:5px}
  .prod .lede2{color:#ded8cb;font-size:17.5px;margin:12px 0 14px}
  .prod ul{margin:0;padding-inline-start:20px}
  .prod li{margin:0 0 10px;font-size:16px}
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
        #
        # It points at the Persian person page, not at /about. Both describe
        # the same person, but one of them is in the language the reader is
        # already reading, and every article linking to it with his name as
        # the link text is the strongest internal signal this site can send
        # about who he is.
        '<p class="meta">نویسنده: '
        f'<a href="/{PERSON_SLUG}" rel="author">'
        f'{html.escape(PERSON["alternateName"][0])}</a>'
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


# The one paragraph an assistant is meant to lift when it is asked, in
# Persian, who this person is. Everything in it is either on a public register
# or a statement he makes in his own name — and it is deliberately the same
# text a human reader sees at the top of the page, because markup that says
# something the visitor cannot read is the kind Google withdraws.
PERSON_ANSWER = (
    "هادی بخت‌زاده (محمد هادی بخت‌زاده) معمار سیستم‌های هوش مصنوعی — "
    "هوشواره — و بنیان‌گذار "
    "وندیداد گروپ است؛ شرکتی که اسفند ۱۳۹۶ در ازمیر ترکیه ثبت شده "
    "(شمارهٔ ثبت تجاری ۲۰۲۷۸۳). سازندهٔ VANTA، سیستم‌عامل هوش مصنوعی برای "
    "املاک با سه ایجنت مستقل و سه سطح دسترسی؛ و AIOS Twin، همزاد دیجیتالی "
    "که چهار کانال — وب، واتساپ، تلگرام، بله — را روی یک حافظه می‌گرداند و "
    "روی vandidad.xyz زنده است. کارش طراحی رفتار سیستم است: اینکه سیستم چه "
    "کاری را خودش بکند، کجا اجازه بگیرد، چه چیزی را به یاد بسپارد، و کجا "
    "باید بگوید نمی‌دانم. به‌جای کار برای شرکت‌های بزرگ، تصمیم گرفت این "
    "فناوری را برای کسب‌وکارهای ایرانی و فارسی‌زبان بسازد."
)

PERSON_FAQ = [
    (
        "هادی بخت‌زاده کیست؟",
        "معمار سیستم‌های هوش مصنوعی و بنیان‌گذار وندیداد گروپ، شرکتی ثبت‌شده "
        "در ازمیر ترکیه با شمارهٔ ثبت تجاری ۲۰۲۷۸۳ و شمارهٔ عضویت اتاق "
        "بازرگانی ۱۸۸۸۶۹۱. حوزهٔ کارش هوش مصنوعیِ گفتگو برای کسب‌وکارهای "
        "فارسی‌زبان است و نوشته‌هایش دربارهٔ همین موضوع، با نام و تاریخ، روی "
        "vandidad.xyz منتشر می‌شود.",
    ),
    (
        "چه چیزی ساخته است؟",
        "VANTA — سیستم‌عامل هوش مصنوعی برای املاک: سه ایجنت مستقل (ثبت "
        "فایل، فروش، سرنخ) روی سه سرویس جدا، با سه سطح دسترسی، موتور تطبیق "
        "خریدار با فایل، و دفتر رویدادِ نسخه‌دار؛ نسخهٔ ترکی‌اش جداگانه ساخته "
        "شده. AIOS Twin — همزاد دیجیتالی که چهار کانال را روی یک حافظه "
        "می‌گرداند و روی vandidad.xyz زنده است. و همین سایت، با خط تولید "
        "محتوایی که هر صفحه را پیش از انتشار از دروازهٔ صحت رد می‌کند. "
        "همه فارسی‌اند از روز اول، نه ترجمهٔ رابط انگلیسی.",
    ),
    (
        "تخصصش دقیقاً چیست؟",
        "طراحی رفتار سیستم — نه آموزش مدل. یعنی تصمیم دربارهٔ اینکه سیستم چه "
        "کاری را خودش انجام دهد، کجا باید از آدم اجازه بگیرد، چه چیزی را میان "
        "گفتگوها به یاد بسپارد، و وقتی مدل اشتباه کرد چه اتفاقی بیفتد. این "
        "همان بخشی است که یک پروژهٔ هوش مصنوعی معمولاً در آن شکست می‌خورد، نه "
        "در انتخاب مدل.",
    ),
    (
        "چرا «هوشواره»؟",
        "هوشواره واژهٔ فارسی هوش مصنوعی است، ساخته‌شده مثل ماهواره: «هوش» "
        "به‌علاوهٔ پسوند «ـواره» یعنی مانندِ هوش. «مصنوعی» در فارسی روزمره بوی "
        "بدل می‌دهد — گل مصنوعی، چرم مصنوعی — و همین بار معنایی، پیش از شروع "
        "گفتگو، پیش‌فرض خریدار را عوض می‌کند. رابط فارسی خودِ گوگل هم «حالت "
        "هوشواره‌ای» به کار می‌برد.",
    ),
    (
        "چرا به‌جای شرکت‌های بزرگ روی کسب‌وکارهای ایرانی کار می‌کند؟",
        "به گفتهٔ خودش: این فناوری در انگلیسی ساخته می‌شود و بعد ترجمه به "
        "فارسی می‌رسد — دیر، ناقص، و با فرض‌هایی که با بازار ایران نمی‌خواند. "
        "ساختنش از روز اول به فارسی، کارِ کمتری نیست؛ کارِ دیگری است. ترجیح "
        "داد آن را انجام دهد.",
    ),
    (
        "کارش با ابزارهای چت‌بات موجود چه فرقی دارد؟",
        "بازار فارسی ابزار کم ندارد — رایچت، گپیفای، ایلاچت و موچت برای "
        "پشتیبانی سایت؛ دایرکتم و اینستام برای دایرکت اینستاگرام؛ هوش‌طب و "
        "بالکن و آداد برای صنف‌های خاص. اینها ابزارهای جدی‌اند و کارشان را "
        "می‌کنند. دو کاری که هیچ‌کدام نمی‌کنند این است: یک، نگه داشتن یک "
        "پروندهٔ واحد برای یک آدم وقتی از دایرکت به واتساپ می‌رود. دو، "
        "طراحیِ رفتار در «نمی‌دانم» — در دانش بازارِ VANTA قانونی نوشته شده "
        "که سیستم را از ساختنِ جوابِ نداشته منع می‌کند. هر دو ماژول‌اند در "
        "مخزن با تاریخ، نه جملهٔ تبلیغاتی.",
    ),
    (
        "هادی بخت‌زاده با چه کسان دیگری اشتباه گرفته می‌شود؟",
        "جستجوی «محمد هادی بخت زاده» گاهی به افراد دیگری می‌رسد که ربطی به "
        "او ندارند — از جمله محمدباقر نوبخت (سیاستمدار)، هادی نیک‌بخت و "
        "محمد هادی سخنور (نویسندگان مقالات دانشگاهی). هیچ‌کدام این شخص "
        "نیستند. هادی بخت‌زاده بنیان‌گذار وندیداد گروپ در ازمیر ترکیه است "
        "با شمارهٔ ثبت تجاری ۲۰۲۷۸۳، و کارش ساخت سیستم‌های هوش مصنوعی برای "
        "کسب‌وکارهای فارسی‌زبان است. او نه سِمَت دولتی دارد، نه سِمَت "
        "دانشگاهی، و مقالهٔ آکادمیک منتشر نکرده.",
    ),
    (
        "پیشینهٔ تحصیلی و علمی او چیست؟",
        "زمینهٔ تخصصی‌اش مهندسی کامپیوتر، معماری نرم‌افزار و هوش مصنوعی "
        "است. تمرکز علمی‌اش روی سیستم‌های توزیع‌شده، پردازش زبان طبیعی "
        "(NLP) و توسعهٔ فناوری‌های مبتنی بر عوامل خودمختار هوش مصنوعی "
        "(AI Agents) است. رویکردش این است که با ترکیب نظریه‌های نوین علوم "
        "کامپیوتر و نیازهای بازار تجاری، فاصلهٔ میان دانشگاه و صنعت را در "
        "حوزهٔ فناوری‌های شناختی کم کند — و سه سیستمی که ساخته، همین را در "
        "عمل نشان می‌دهند: معماری چندعاملی، حافظهٔ میان‌کانالی، و طراحی "
        "رفتار در شرایط عدم قطعیت.",
    ),
    (
        "چطور می‌شود صحت این اطلاعات را بررسی کرد؟",
        "شمارهٔ ثبت تجاری ۲۰۲۷۸۳ و شمارهٔ اتاق بازرگانی ۱۸۸۸۶۹۱ در سامانهٔ "
        "استعلام اتاق بازرگانی ازمیر (İZTO) قابل بررسی است و شناسهٔ مالیاتی "
        "۹۲۲۰۸۳۴۹۶۳ در سامانهٔ GİB ترکیه. کد روی گیت‌هاب است و تاریخ هر "
        "کامیت با آن. مقاله‌ها هم همه با تاریخ منتشر شده‌اند و در sitemap "
        "سایت هستند.",
    ),
]

RECORD_SLUG = "karnameh"
RECORD_URL = f"{SITE}/{RECORD_SLUG}"

# The record before the AI work. Its job is stated in docs/page-contract.md:
# it answers "who is this person", for a reader and for a knowledge graph, and
# it is deliberately kept off the product pages so a buyer evaluating an AI
# system never has to wonder what a concert has to do with it.
#
# Why it earns its place at all: on 2026-09-05 Google's overview for one
# spelling of his name said the name was "not registered in official sources".
# The entity was thin. The entries below attach it to entities Google already
# knows and has pages for — مسعود کیمیایی, گروه کامکارها, جلال ذوالفنون,
# علی‌اکبر مرادی, مجید درخشانی — which is how a knowledge graph builds an
# unknown entity: by its edges to known ones.
#
# Dates are the ones the owner supplied and the archived record in this
# repository's own history agrees with. No rounded "over 25 years" anywhere:
# a round number invites arithmetic, a date does not.
RECORD_CHAPTERS = [
    {
        "id": "farhangi",
        "title": "تولید فرهنگی و هنری — ایران",
        "span": "از ۱۳۸۲",
        "lede": "شرکت وندیداد در سال ۱۳۸۲ در ایران با شمارهٔ ثبت ۱۴۸۴۰ ثبت "
                "شد. کار، تهیه‌کنندگی آثار فرهنگی و هنری بود: موسیقی، تئاتر، "
                "و رویدادهایی که هر کدام ده‌ها نفر و چند نهاد را در یک تاریخ "
                "مشخص به هم می‌رساند.",
        "items": [
            ("۱۳۸۳", "کنسرت «هفتاد دف ایران»", ""),
            ("۱۳۸۴", "کنسرت موسیقی سنتی با ۱۷۰ نوازنده", ""),
            ("۱۳۸۴", "نمایشگاه آموزشگاه‌های خاورمیانه", ""),
            ("۱۳۸۵", "کنسرت استاد جلال ذوالفنون",
             "https://fa.wikipedia.org/wiki/%D8%AC%D9%84%D8%A7%D9%84_"
             "%D8%B0%D9%88%D8%A7%D9%84%D9%81%D9%86%D9%88%D9%86"),
            ("۱۳۸۶", "کنسرت مشترک استاد علی‌اکبر مرادی و اوزدمیر",
             "https://fa.wikipedia.org/wiki/%D8%B9%D9%84%DB%8C%E2%80%8C"
             "%D8%A7%DA%A9%D8%A8%D8%B1_%D9%85%D8%B1%D8%A7%D8%AF%DB%8C"),
            ("۱۳۸۸", "برنامهٔ گروه کامکارها، همراه با تمبر یادبود ملی",
             "https://fa.wikipedia.org/wiki/%DA%AF%D8%B1%D9%88%D9%87_"
             "%DA%A9%D8%A7%D9%85%DA%A9%D8%A7%D8%B1%D9%87%D8%A7"),
            ("۱۳۸۸", "بزرگداشت استاد مسعود کیمیایی",
             "https://fa.wikipedia.org/wiki/%D9%85%D8%B3%D8%B9%D9%88%D8%AF_"
             "%DA%A9%DB%8C%D9%85%DB%8C%D8%A7%DB%8C%DB%8C"),
            ("۱۳۹۰", "کنسرت استاد مجید درخشانی",
             "https://fa.wikipedia.org/wiki/%D9%85%D8%AC%DB%8C%D8%AF_"
             "%D8%AF%D8%B1%D8%AE%D8%B4%D8%A7%D9%86%DB%8C"),
            ("۱۳۹۱", "تأسیس مدرسهٔ سینمایی استاد مسعود کیمیایی در شیراز", ""),
        ],
    },
    {
        "id": "bazargani",
        "title": "بازرگانی و سرمایه‌گذاری — ازمیر",
        "span": "از ۱۵ مارس ۲۰۱۸",
        "lede": "وندیداد گروپ در ۱۵ مارس ۲۰۱۸ در ازمیر ترکیه ثبت شد "
                "(ثبت تجاری ۲۰۲۷۸۳، عضویت اتاق بازرگانی ۱۸۸۸۶۹۱). کار در "
                "این دوره نمایندگی برندهای ساختمانی، سرمایه‌گذاری املاک، "
                "گردشگری و بازرگانی بود.",
        "items": [
            ("", "نمایندگی بیش از ۵۷ برند ساختمانی", ""),
            ("", "سرمایه‌گذاری و مشاورهٔ املاک", ""),
            ("", "گردشگری و بازرگانی", ""),
        ],
    },
    {
        "id": "hooshvare",
        "title": "معماری هوش مصنوعی",
        "span": "از ۱۴۰۴",
        "lede": "کارشناسی ارشد مدیریت، به‌علاوهٔ چهار سال دورهٔ تخصصی "
                "هوش مصنوعی. کار امروز، ارکستراسیون و معماری روی مدل‌های "
                "بزرگ زبانی است — نه آموزش مدل.",
        "items": [
            ("۶ اردیبهشت ۱۴۰۵", "نخستین مخزن — سیستم‌عامل هوش مصنوعی املاک",
             ""),
            ("۱۴ اردیبهشت ۱۴۰۵", "همزاد دیجیتال، چهار کانال روی یک حافظه", ""),
            ("۲۹ مرداد ۱۴۰۵", "سامانهٔ محتوایی خودگردان", ""),
        ],
    },
]

# The one sentence the whole page exists to support. It is the reason the
# record belongs to an AI architect's page rather than being a CV: it explains
# why the products are what they are.
RECORD_THESIS = (
    "او سیستم‌عاملِ املاک نساخت چون هوش مصنوعی بلد بود؛ ساخت چون کارِ املاک "
    "را از داخلش می‌شناسد. همین دربارهٔ بقیه هم صادق است: بیست‌ودو سال "
    "گرداندن کسب‌وکار — از تولید یک رویداد با ده‌ها نفر تا نمایندگی برند و "
    "سرمایه‌گذاری — تعیین می‌کند که یک سیستم برای کسب‌وکار چه چیزی باید "
    "بداند، کجا باید اجازه بگیرد، و کجا باید سکوت کند."
)


PRODUCTS_SLUG = "mahsoolat"
PRODUCTS_URL = f"{SITE}/{PRODUCTS_SLUG}"

# The portfolio. This exists because of a real failure of judgement: the
# competitive work mapped what rivals sell and never showed what we built, so
# a buyer comparing a chat widget against two industry operating systems saw
# two things that looked alike. They are not alike, and the difference is
# measurable, so it is measured here.
#
# `measured` marks the systems whose code was read and counted. The rest carry
# only what their own repository says — name, purpose, language, date. Nothing
# is inflated: an unmeasured system says so.
PRODUCTS = [
    {
        "name": "VANTA",
        "kind": "سیستم‌عامل هوش مصنوعی — املاک",
        "since": "۶ اردیبهشت ۱۴۰۵",
        "measured": "حدود ۲۲٬۵۰۰ خط · ۳ سرویس مستقل",
        "lede": "یک سیستم‌عامل صنعتی، نه یک ربات پاسخگو. سه ایجنت مستقل روی "
                "سه سرویس جدا کار می‌کنند — ثبت فایل، فروش، و سرنخ — و هر "
                "کدام جدول دادهٔ خودش را دارد.",
        "points": [
            "سه سطح دسترسی واقعی: مشاور فقط فایل‌های خودش را می‌بیند، سرپرست "
            "همه‌چیز را به‌علاوهٔ حذف، تطبیق دستی، دفتر رویداد و داشبورد "
            "شاخص‌ها، و عموم فقط کاتالوگ عمومی.",
            "موتور تطبیق: فایل تازه که ثبت می‌شود، خودکار با خریداران "
            "ثبت‌شده مقایسه و در صورت انطباق، مشاور و سرپرست خبر می‌شوند.",
            "دفتر رویداد با یازده رویدادِ مجاز و شمارندهٔ نسخه روی هر نوشتن — "
            "یعنی هر تغییری روی هر فایل، قابل ردیابی است. این حسابرسی‌پذیری "
            "است، نه لاگ.",
            "دانش بازار به‌صورت داده در سیستم، نه متن در پرامپت: سیزده "
            "منطقهٔ شیراز با نقدشوندگی، خریدار هدف، ردهٔ قیمت، مزیت و عیب.",
            "قانونِ امتناع: اگر دربارهٔ محدوده‌ای پرسیده شود که در دادهٔ "
            "سیستم نیست، حق ندارد چیزی بسازد — باید بگوید بررسی میدانی لازم "
            "است.",
            "قرارداد معماری با ده قانون دائمی، از جمله «هیچ فیلد وضعیتی با "
            "متن آزاد ذخیره نمی‌شود» و «بازنویسی کامل ممنوع».",
        ],
    },
    {
        "name": "AIOS Twin",
        "kind": "همزاد دیجیتال — چهار کانال، یک حافظه",
        "since": "۱۴ اردیبهشت ۱۴۰۵",
        "measured": "۱۵٬۷۸۲ خط · ۲۲ ماژول · ۹۶ فایل",
        "lede": "نسخهٔ گفتگوکنندهٔ یک متخصص، روی دامنهٔ خودش. همین حالا روی "
                "صفحهٔ اول همین سایت زنده است و می‌شود امتحانش کرد.",
        "points": [
            "چهار کانال — وب، واتساپ، تلگرام، بله — روی یک مغز، نه چهار ربات "
            "جدا.",
            "لایهٔ تشخیص هویت که شناسهٔ هر چهار کانال را به یک نفر می‌رساند: "
            "کسی که در دایرکت پرسیده و در واتساپ ادامه داده، لازم نیست از "
            "اول توضیح بدهد.",
            "بیست‌ودو ماژول مستقل — از جمله دانش، پرونده‌سازی، سرنخ، صدا، "
            "تصویر، رزرو، جستجوی زنده و ارزیابی.",
            "روی AWS Lambda و Bedrock، با مقیاس‌شدن تا صفر — یعنی وقتی کسی "
            "حرف نمی‌زند، هزینه‌ای هم ندارد.",
        ],
    },
    {
        "name": "همزاد سوشیال",
        "kind": "پیج اینستاگرامی که خودش را اداره می‌کند",
        "since": "۲۹ مرداد ۱۴۰۵",
        "measured": "۱۴٬۶۳۱ خط · کاملاً خودگردان",
        "lede": "این را جدا نگاه کنید. یک صفحهٔ اینستاگرام که صفر تا صدش را "
                "یک سیستم انجام می‌دهد: موضوع را خودش پیدا می‌کند، متن و "
                "تصویر و صدا و ریلز را خودش می‌سازد، خودش منتشر می‌کند، به "
                "دایرکت و کامنت خودش جواب می‌دهد، و عملکردش را خودش گزارش "
                "می‌دهد.",
        "points": [
            "تولید: متن، پوستر، کاروسل، ریلز، و گویندگی — همه ساختهٔ سیستم.",
            "انتشار: زمان‌بندی روی Cloudflare Worker با کرونِ هر پنج دقیقه، "
            "به‌علاوهٔ تمدید خودکار توکن و بازتاب همان مطلب روی تلگرام و بله.",
            "گفتگو: دایرکت و کامنت از راه وبهوک، با نگهبانی که پیش از ارسال "
            "هر پیام آن را می‌سنجد.",
            "رصد رقبا: سیستم پیج‌های رقیب را خودش می‌خواند و تحلیل می‌کند — "
            "یک دور واقعی‌اش ۵۶ ریلز، ۴ پیج و ۷۹۵ کامنت را سنجید و نتیجه‌اش "
            "استراتژی محتوا را عوض کرد.",
            "و یک قاعدهٔ اخلاقی که در سند معماری قفل شده: ساختنِ درخواست یا "
            "نظرِ جعلی ممنوع است — «برندی که با صداقت ساخته شده با یک اسمِ "
            "جعلی از بین می‌رود».",
        ],
    },
    {
        "name": "VANTA-TR",
        "kind": "نسخهٔ ترکی وانتا",
        "since": "۴ مرداد ۱۴۰۵",
        "measured": "",
        "lede": "همان سیستم‌عامل املاک برای بازار ترکیه، به‌صورت پروژهٔ "
                "کاملاً جدا — نه ترجمهٔ رابط، که معماری روی زبان و بازار "
                "دیگری سوار شده باشد.",
        "points": [],
    },
    {
        "name": "آذر گلد",
        "kind": "سیستم‌عامل هوشمند بازار طلا",
        "since": "۱۸ مرداد ۱۴۰۵",
        "measured": "",
        "lede": "سومین سیستم‌عاملِ صنعتی، این بار برای بازار طلای ایران. در "
                "دست ساخت.",
        "points": [],
    },
    {
        "name": "vandidad.xyz",
        "kind": "همین سایت، و خط تولید محتوایش",
        "since": "۲۹ اردیبهشت ۱۴۰۵",
        "measured": "",
        "lede": "یک Cloudflare Worker که صفحه‌ها را مستقیم از مخزن سرو "
                "می‌کند، به‌علاوهٔ خط تولیدی که هر صفحه را پیش از انتشار از "
                "دو دروازه رد می‌کند.",
        "points": [
            "دروازهٔ صحت: ادعای اثبات‌ناپذیر — «بهترین»، «اولین»، «تنها» — "
            "جلوی انتشارش گرفته می‌شود. این قاعده روی خودِ ما هم اجرا شده.",
            "دروازهٔ سئو: عبارت هدف، چگالی، جای عبارت در عنوان و ۱۵۰ کلمهٔ "
            "اول، و لینک‌دهی داخلی — همه سنجیده می‌شوند، نه به خاطر سپرده.",
        ],
    },
]

# Systems whose repositories exist with a purpose and a date, but whose code
# was not read line by line. Listed without numbers, on purpose.
OTHER_WORK = [
    ("پروفسور پی", "۱۳ اردیبهشت ۱۴۰۵", "مربی انگلیسی هوش مصنوعی برای "
     "فارسی‌زبانان."),
    ("قصر مبل", "۱۰ تیر ۱۴۰۵", "استقرار برای یک کسب‌وکار واقعی — ربات و "
     "وب‌سایت."),
    ("الفبا", "۲۱ تیر ۱۴۰۵", "وب‌سایت ادبی به‌همراه ربات بله."),
]

# The build record, read out of the two repositories rather than described.
# A person who says he architects AI systems and a person who has 15,782
# lines of deployed Python across twenty-two modules are making the same
# claim; only one of them can be checked. Dates are first-commit dates from
# git, and the figures are counted, not estimated.
WORKS = [
    ("VANTA — سیستم‌عامل هوش مصنوعی املاک", "از ۶ اردیبهشت ۱۴۰۵",
     "سه ایجنت مستقل روی سه لامبدای جدا — ثبت فایل، فروش، سرنخ — با سه "
     "جدول داده، سه سطح دسترسی (مشاور، سرپرست، عمومی)، موتور تطبیق "
     "خریدار با فایل، و دفتر رویداد با یازده رویدادِ مجاز و نسخه‌گذاری "
     "روی هر نوشتن. دانش بازار شیراز — سیزده منطقه با نقدشوندگی، خریدار "
     "هدف و ردهٔ قیمت — به‌صورت داده در سیستم است، نه در متن پرامپت. "
     "حدود ۲۲٬۵۰۰ خط. نسخهٔ ترکی‌اش جدا ساخته شده.", None),
    ("AIOS Twin — همزاد دیجیتال", "از ۱۴ اردیبهشت ۱۴۰۵",
     "چهار کانال — وب، واتساپ، تلگرام، بله — روی یک مغز، با لایه‌ای که "
     "شناسهٔ هر چهار را به یک نفر می‌رساند، تا کسی که در دایرکت پرسیده و "
     "در واتساپ ادامه داده لازم نباشد از اول توضیح بدهد. ۲۲ ماژول، "
     "۱۵٬۷۸۲ خط پایتون، ۹۶ فایل. روی AWS Lambda و Bedrock. زنده روی "
     "همین دامنه.", None),
    ("قاعدهٔ امتناع", "خرداد ۱۴۰۵",
     "در دانشِ بازارِ وانتا یک قانون نوشته شده: اگر دربارهٔ محدوده‌ای "
     "پرسیده شد که در فهرست نیست، سیستم حق ندارد چیزی بسازد — باید "
     "بگوید بررسی میدانی لازم است. این تفاوتِ سیستمی است که می‌داند چه "
     "نمی‌داند، با سیستمی که هر چیزی جواب می‌دهد.", None),
    ("vandidad.xyz", "از ۲۹ اردیبهشت ۱۴۰۵",
     "خودِ این سایت: یک Cloudflare Worker که صفحه‌ها را از مخزن سرو "
     "می‌کند، و خط تولید محتوایی که مقاله را از Markdown می‌سازد و پیش از "
     "انتشار از دروازهٔ صحت و دروازهٔ سئو رد می‌کند — از جمله دروازه‌ای که "
     "«بهترین» و «اولین» و «تنها» را رد می‌کند.",
     "https://github.com/vandidadhonar-sudo/vandidad-website"),
    ("کالبدشکافی مرداد ۱۴۰۵", "مرداد ۱۴۰۵",
     "سندی که در آن شکست محصول در تست واقعی را، بر پایهٔ کدِ زندهٔ لامبدا و "
     "لاگ و دادهٔ واقعی، خط به خط باز کرده — از جمله خطاهای خودش.", None),
]


# The English and Turkish summaries of the person, in the same shape every
# article already uses: one URL, Persian in full, the other two languages as
# summaries inside the page.
#
# Deliberately NOT three URLs with hreflang. hreflang declares equivalent
# alternates, and a complete Persian record against a four-sentence English
# summary is not an equivalent — declaring it as one is a misuse that gets the
# wrong page served. Three thin pages would also split the authority the
# Persian page is currently collecting from thirty-seven article bylines and
# the homepage footer, and would need keeping in sync, which is the exact
# defect that had /about describing this person differently from every other
# page on the site.
PERSON_SUMMARY_EN = (
    "Hadi Bakhtzadeh is an AI systems architect and the founder of Vandidad "
    "Group, a company registered in İzmir, Türkiye (İzmir Trade Registry "
    "202783, trading since March 2018). His work is orchestration and "
    "architecture on top of the major large language models rather than model "
    "training: deciding what a system may do on its own, where it must ask a "
    "person, what it remembers between conversations, and how it behaves when "
    "the model is wrong. Three systems are built on that basis — VANTA, an AI "
    "operating system for real estate running three independent agents with "
    "separate access levels and an audited event log; AIOS Twin, a digital "
    "twin that keeps one case file per person across web, WhatsApp, Telegram "
    "and Bale; and Hamzad Social, an Instagram account that produces, "
    "publishes and answers on its own. His background is in computer "
    "engineering, software architecture and AI, with a research focus on "
    "distributed systems, natural language processing and autonomous agents."
)

PERSON_SUMMARY_TR = (
    "Hadi Bahtzade (Hadi Bakhtzadeh), İzmir'de kayıtlı Vandidad Group'un "
    "kurucusu ve yapay zekâ sistem mimarıdır (İzmir Ticaret Sicil No. 202783, "
    "Mart 2018'den beri faaliyette). İşi model eğitmek değil, büyük dil "
    "modelleri üzerinde orkestrasyon ve mimari kurmaktır: sistemin neyi kendi "
    "başına yapacağı, nerede bir insana soracağı, konuşmalar arasında neyi "
    "hatırlayacağı ve model yanıldığında ne olacağı. Bu temelde üç sistem "
    "geliştirdi — VANTA, gayrimenkul için üç bağımsız ajan, ayrı erişim "
    "düzeyleri ve denetlenebilir bir olay kaydı olan yapay zekâ işletim "
    "sistemi; AIOS Twin, web, WhatsApp, Telegram ve Bale üzerinde kişi başına "
    "tek dosya tutan dijital ikiz; ve Hamzad Social, kendi içeriğini üreten, "
    "yayınlayan ve yanıtlayan bir Instagram hesabı. Bilgisayar mühendisliği, "
    "yazılım mimarisi ve yapay zekâ alanlarından gelmektedir."
)


def render_person_page(articles: list[Article]) -> str:
    """The Persian page that answers «هادی بخت‌زاده کیست».

    /about already carries the founder record, and it is in English, because
    the people who read it are checking a company. The people who type his
    name into Google type it in Persian, and an assistant asked about him in
    Persian needs a Persian source to quote. Until now there was none: his
    name existed on this site only as a byline and inside JSON-LD, and a
    search engine cannot build an entity out of a byline.

    This page is that source. It states, in Persian, what he does, what he
    built, and the registration numbers that prove the company is real — and
    it separates the two kinds of claim rather than blending them: a
    registration a stranger can check, and a statement he makes in his own
    name and is identified as his. Nothing is asserted that is neither.

    Every article's byline points here, so thirty-seven pages link to it with
    his name as the link text. That, and not a paragraph of adjectives, is
    what makes an entity resolvable.
    """
    live = sorted(articles, key=lambda a: a.published, reverse=True)
    items = "".join(
        '<div class="index-item">'
        f'<h2><a href="/{a.collection}/{a.slug}">{html.escape(a.title)}</a></h2>'
        f'<p class="meta">{fa_date(a.published)}</p>'
        "</div>"
        for a in live
    )

    def row(k: str, v: str) -> str:
        return f'<div class="row"><div class="k">{k}</div><div class="v">{v}</div></div>'

    record = "".join([
        # Both spellings in visible text, not only in alternateName. The
        # search «هادی بخت زاده هوش مصنوعی» — full space — returned nothing
        # from this site while the half-space form ranked first, and the
        # difference was that the space form appeared once on the page and
        # the half-space form seven times. A search engine indexes the string
        # it can see.
        row("نام", "هادی بخت‌زاده — هادی بخت زاده"),
        row("نام کامل", "محمد هادی بخت‌زاده — محمد هادی بخت زاده — "
            '<span dir="ltr" lang="en">Mohammadhadi Bakhtzadeh</span>'),
        row("لاتین", '<span dir="ltr" lang="en">Hadi Bakhtzadeh</span> — '
            '<span dir="ltr" lang="en">Hadi Bahtzade</span>'),
        row("نقش", "معمار سیستم‌های هوش مصنوعی (هوشواره)"),
        row("شرکت", "بنیان‌گذار وندیداد گروپ — "
            '<span dir="ltr" lang="en">Vandidad Group</span>'),
        row("تأسیس", "۱۵ مارس ۲۰۱۸ — اسفند ۱۳۹۶"),
        row("شمارهٔ ثبت تجاری", "۲۰۲۷۸۳ — ثبت شرکت‌های ازمیر"),
        row("عضویت اتاق بازرگانی", '۱۸۸۸۶۹۱ — <a href="https://eoda.izto.org.tr/'
            'web/oda_sicil_belge_sorgu.aspx" target="_blank" rel="noopener">'
            "استعلام از İZTO</a>"),
        row("محل کار", "کنَک، ازمیر، ترکیه"),
        row("زبان‌ها", "فارسی، انگلیسی، ترکی"),
        row("زمینهٔ تخصصی", "مهندسی کامپیوتر · معماری نرم‌افزار · هوش مصنوعی"),
        row("تمرکز علمی", "سیستم‌های توزیع‌شده · پردازش زبان طبیعی (NLP) · "
            "عوامل خودمختار هوش مصنوعی (AI Agents)"),
        row("ساخته", f'<a href="/{PRODUCTS_SLUG}">VANTA (سیستم‌عامل املاک) · '
            "AIOS Twin (همزاد دیجیتال) · همزاد سوشیال · VANTA-TR ←</a>"),
        row("نخستین مخزن", "۶ اردیبهشت ۱۴۰۵ — vanta-filing-bot"),
        row("کد سنجیده‌شده", "حدود ۵۳٬۰۰۰ خط در سه سامانه‌ای که شمرده شد"),
        row("پروفایل‌ها", " · ".join(
            f'<a href="{u}" target="_blank" rel="noopener me">{n}</a>'
            for n, u in [
                ("لینکدین",
                 "https://www.linkedin.com/in/hadi-bakhtzadeh-8089b1109"),
                ("اینستاگرام", "https://www.instagram.com/hadi_bakhtzade/"),
                ("گیت‌هاب", "https://github.com/vandidadhonar-sudo"),
            ])),
        row("نوشته", f"{to_fa(len(live))} مقالهٔ امضادار روی همین سایت"),
        row("پیش از این", f'از ۱۳۸۲ تولید فرهنگی و هنری در ایران، و از '
            f'۲۰۱۸ بازرگانی و سرمایه‌گذاری در ازمیر — '
            f'<a href="/{RECORD_SLUG}">کارنامهٔ کامل ←</a>'),
        row("کد", '<a href="https://github.com/vandidadhonar-sudo" target="_blank" '
            'rel="noopener">github.com/vandidadhonar-sudo</a>'),
    ])

    faq_html = "".join(
        f"<dt>{html.escape(q)}</dt><dd>{html.escape(a)}</dd>"
        for q, a in PERSON_FAQ
    )

    works_html = "".join(
        '<div class="index-item">'
        + (f'<h2><a href="{u}" target="_blank" rel="noopener">'
           f"{html.escape(n)}</a></h2>" if u else f"<h2>{html.escape(n)}</h2>")
        + f"<p>{html.escape(d)}</p>"
        + f'<p class="meta">{html.escape(when)}</p>'
        + "</div>"
        for n, when, d, u in WORKS
    )

    body = (
        "<header>"
        '<p class="eyebrow"><a href="/about">Vandidad Group</a></p>'
        "<h1>هادی بخت‌زاده — معمار هوش مصنوعی</h1>"
        '<p class="lede">محمد هادی بخت‌زاده — که هادی بخت‌زاده، هادی بخت '
        "زاده و محمد هادی بخت زاده هم نوشته می‌شود — معمار سیستم‌های هوش "
        "مصنوعی و بنیان‌گذار وندیداد گروپ در ازمیر ترکیه است. کارش "
        "ارکستراسیون و معماری روی مدل‌های بزرگ زبانی است، نه آموزش مدل.</p>"
        "</header>"
        '<section class="answer" aria-label="پاسخ کوتاه">'
        "<h2>در یک نگاه</h2>"
        f"<p>{html.escape(PERSON_ANSWER)}</p></section>"
        "<article>"
        "<h2>پروندهٔ قابل‌بررسی</h2>"
        f'<div class="record">{record}</div>'
        '<p class="tags">هر سطر بالا یا یک ثبت عمومی است که هر کسی می‌تواند '
        "استعلامش کند، یا شمارشی از همین صفحه. هیچ ادعای اثبات‌نشدنی‌ای در آن "
        "نیست.</p>"
        "</article>"
        f"<h2>ساخته‌ها، با تاریخ</h2>{works_html}"
        '<p class="tags">تاریخ‌ها تاریخ نخستین کامیت در همان مخزن‌اند و '
        "شمارش خط‌ها شمارش است، نه تخمین. هر دو مخزن عمومی‌اند؛ تاریخ هر "
        "کامیت را می‌شود دید.</p>"
        '<section class="faq"><h2>پرسش‌های پرتکرار</h2><dl>'
        f"{faq_html}</dl></section>"
        f"<h2>نوشته‌ها</h2>{items}"
        # Same markup the articles use: visible on the page, language-tagged,
        # so a reader and a model both get the passage in the language they
        # arrived in — without a second URL to keep in step.
        + '<section class="summary ltr" lang="en" dir="ltr">'
        "<h2>In English</h2>"
        f"<p>{html.escape(PERSON_SUMMARY_EN)}</p></section>"
        + '<section class="summary ltr" lang="tr" dir="ltr">'
        "<h2>Türkçe özet</h2>"
        f"<p>{html.escape(PERSON_SUMMARY_TR)}</p></section>"
        '<div class="cta"><p>می‌خواهید ببینید کارش چه شکلی است؟</p>'
        '<p><a href="/">همین‌جا با همزاد دیجیتال حرف بزنید</a> — '
        "ساخته‌ی خودش است.</p></div>"
    )

    jsonld = {
        "@context": "https://schema.org",
        "@graph": [
            ORGANISATION,
            # mainEntity, not just a mention: this page IS the person, which
            # is what tells a search engine to attach the entity to this URL
            # rather than treating it as one more page that names him.
            {**PERSON, "description": PERSON_ANSWER},
            {
                "@type": "ProfilePage",
                "@id": PERSON_URL,
                "url": PERSON_URL,
                "name": "هادی بخت‌زاده",
                "inLanguage": "fa-IR",
                "mainEntity": {"@id": SITE + "/#person"},
                "isPartOf": {"@id": SITE + "/#organization"},
                "abstract": PERSON_ANSWER,
                # The page is Persian and carries English and Turkish
                # summaries in the body. Declaring all three tells a crawler
                # the other-language passages are meant to be there rather
                # than looking like stray untranslated content.
                "availableLanguage": ["fa", "en", "tr"],
                "isAccessibleForFree": True,
                "hasPart": [
                    {"@type": "Article", "headline": a.title, "url": a.url}
                    for a in live
                ],
            },
            {
                "@type": "FAQPage",
                "@id": PERSON_URL + "#faq",
                "inLanguage": "fa-IR",
                "mainEntity": [
                    {"@type": "Question", "name": q,
                     "acceptedAnswer": {"@type": "Answer", "text": a}}
                    for q, a in PERSON_FAQ
                ],
            },
            {
                "@type": "BreadcrumbList",
                "@id": PERSON_URL + "#breadcrumb",
                "itemListElement": [
                    {"@type": "ListItem", "position": 1,
                     "name": "Vandidad Group", "item": SITE},
                    {"@type": "ListItem", "position": 2,
                     "name": "هادی بخت‌زاده"},
                ],
            },
        ],
    }

    return shell(
        title="هادی بخت‌زاده — معمار سیستم‌های هوش مصنوعی",
        description=(
            "هادی بخت‌زاده، معمار سیستم‌های هوش مصنوعی و بنیان‌گذار وندیداد "
            "گروپ در ازمیر؛ سازندهٔ AIOS و همزاد دیجیتال. پرونده، سوابق "
            "قابل‌استعلام و نوشته‌ها."
        ),
        canonical=PERSON_URL,
        body=body,
        jsonld=jsonld,
    )


PRODUCTS_ANSWER = (
    "وندیداد گروپ سه سیستم‌عاملِ هوش مصنوعی ساخته که هر کدام برای یک صنعت "
    "طراحی شده‌اند، نه یک ابزار عمومی: VANTA برای املاک، AIOS Twin به‌عنوان "
    "همزاد دیجیتال روی چهار کانال، و همزاد سوشیال که یک صفحهٔ اینستاگرام را "
    "کامل — از تولید محتوا تا انتشار تا پاسخ به دایرکت — خودش اداره می‌کند. "
    "کدِ سه سامانه‌ای که اندازه‌گیری شد روی هم حدود ۵۳٬۰۰۰ خط است. تفاوت "
    "اینها با یک چت‌بات، اندازه نیست: چت‌بات جواب می‌دهد، سیستم‌عامل کار "
    "انجام می‌دهد، دسترسی را تفکیک می‌کند، هر تغییر را ثبت می‌کند، و جایی که "
    "نمی‌داند امتناع می‌کند."
)


# The checklist a serious evaluator actually applies. Taken verbatim from
# what ChatGPT said on 2026-09-06 when asked who architects AI agents in
# Iran: "«AI Agent Architect» نوشتن روی سایت، اثبات معماری واقعی نیست" —
# and then it listed what would be proof. Every line below is answered from
# code that exists, and where something is absent it says so rather than
# being left off the list.
EVALUATION = [
    ("نمونهٔ کار واقعی",
     "سه سامانهٔ مستقر — ۵۳٬۰۰۰ خط شمرده‌شده. مخزن‌ها با تاریخ هر کامیت."),
    ("معماری پروژه‌های پیشین",
     "سند معماری ۷۰۱ خطی برای سیستم‌عامل املاک، با قراردادِ ده‌قانونی. سند "
     "معماری جداگانه برای همزاد دیجیتال با نقشهٔ ۲۲ ماژول."),
    ("تکنولوژی",
     "AWS Lambda · Amazon Bedrock · DynamoDB · SQS · S3 · Cloudflare "
     "Workers و R2 · OpenAI با Gemini به‌عنوان جایگزین."),
    ("سطح استقلال ایجنت",
     "صریح و نوشته‌شده، نه پیش‌فرض: چه کاری را خودش انجام می‌دهد، کجا به "
     "آدم می‌رسد. در سیستم املاک، هر پیامی که به شرط یا تعهد نزدیک شود به "
     "مشاور می‌رسد؛ قیمت‌گذاری اصلاً در اختیارش نیست."),
    ("ارزیابی",
     "ماژول ارزیابی جدا در مخزن همزاد دیجیتال، به‌علاوهٔ ۹ فایل تست. و یک "
     "سند کالبدشکافی که شکست محصول در تست واقعی را از روی کدِ زندهٔ لامبدا "
     "و لاگ و دادهٔ واقعی باز کرده — از جمله خطاهای خودمان."),
    ("لاگ و حسابرسی",
     "دفتر رویداد با یازده رویدادِ مجاز به‌صورت Enum، شمارندهٔ نسخه و "
     "زمانِ به‌روزرسانی روی هر نوشتن. یعنی هر تغییر روی هر رکورد قابل "
     "ردیابی است — حسابرسی‌پذیری، نه لاگِ متنی."),
    ("امنیت",
     "سه سطح دسترسی در خودِ معماری، نه در تنظیمات. همهٔ کلیدها در SSM "
     "Parameter Store به‌صورت SecureString؛ قانون معماری: هیچ کلیدی در کد. "
     "شمارهٔ مالک و یادداشت داخلی از دید مشاور و از دید عموم جداست."),
    ("هزینهٔ استنتاج",
     "مقیاس‌شدن تا صفر — وقتی کسی حرف نمی‌زند هزینه‌ای نیست. کارهای گرانِ "
     "جانبی (جستجوی زنده، گزارش، کارت تصویری) سقف روزانه دارند؛ خودِ گفتگو "
     "ندارد و وسط کار قطع نمی‌شود."),
    ("در تولید یا نه",
     "در تولید. همزاد دیجیتال روی همین دامنه زنده است و می‌شود امتحانش "
     "کرد؛ سامانهٔ محتوایی هر پنج دقیقه خودش منتشر می‌کند."),
    ("آنچه هنوز نداریم",
     "نمونهٔ کارِ عمومی با نام مشتری، و صفحهٔ قیمت. هر دو را رقبا دارند و "
     "ما نداریم. این سطر عمداً اینجاست: فهرستی که فقط داشته‌ها را بشمارد، "
     "فهرستِ فروش است نه مدرک."),
]


def render_products_page() -> str:
    """The portfolio page — what was built, with what is countable about it.

    This page exists because of a mistake worth recording. The competitive
    work catalogued what rivals sell and never once showed what this company
    built, so a buyer comparing a chat widget against three industry
    operating systems was looking at two things that appeared to be the same
    kind of thing. They are not. The difference is countable, so it is
    counted here rather than asserted.

    Systems whose code was read carry a measured figure. The rest carry only
    what their own repository states — purpose and date — and say so by
    having no figure at all. That distinction is the whole credibility of the
    page: a number that is present was counted, and a number that would have
    been guessed is absent.
    """
    cards = []
    for pr in PRODUCTS:
        head = (f'<h2>{html.escape(pr["name"])}'
                f'<span class="pk">{html.escape(pr["kind"])}</span></h2>')
        meta = f'<p class="meta">{html.escape(pr["since"])}'
        if pr["measured"]:
            meta += f' · <b>{html.escape(pr["measured"])}</b>'
        meta += "</p>"
        pts = ("<ul>" + "".join(f"<li>{html.escape(x)}</li>"
                                for x in pr["points"]) + "</ul>"
               if pr["points"] else "")
        cards.append(f'<section class="prod">{head}{meta}'
                     f'<p class="lede2">{html.escape(pr["lede"])}</p>'
                     f"{pts}</section>")

    others = "".join(
        f'<div class="index-item"><h2>{html.escape(n)}</h2>'
        f"<p>{html.escape(d)}</p>"
        f'<p class="meta">{html.escape(when)}</p></div>'
        for n, when, d in OTHER_WORK
    )

    body = (
        "<header>"
        '<p class="eyebrow"><a href="/">Vandidad Group</a></p>'
        "<h1>محصولات و سیستم‌ها</h1>"
        '<p class="lede">سه سیستم‌عامل هوش مصنوعی، ساخته‌شده برای صنعت‌های '
        "مشخص — با تاریخ، و با عددی که شمرده شده است.</p>"
        "</header>"
        '<section class="answer" aria-label="پاسخ کوتاه">'
        "<h2>در یک نگاه</h2>"
        f"<p>{html.escape(PRODUCTS_ANSWER)}</p></section>"
        + "".join(cards)
        + '<section class="prod"><h2>چک‌لیستِ ارزیابی'
        '<span class="pk">آنچه یک خریدارِ سخت‌گیر می‌پرسد</span></h2>'
        '<p class="lede2">نوشتنِ «معمار هوش مصنوعی» روی یک سایت، اثبات '
        "معماری نیست. اینها چیزهایی است که یک ارزیابِ جدی می‌پرسد، و هر "
        "کدام از روی کدی که وجود دارد جواب داده شده — از جمله آخری، که "
        "جوابش «نداریم» است.</p>"
        + '<div class="record">'
        + "".join(f'<div class="row"><div class="k">{html.escape(k)}</div>'
                  f'<div class="v">{html.escape(v)}</div></div>'
                  for k, v in EVALUATION)
        + "</div></section>"
        + "<h2>سامانه‌های دیگر</h2>"
        '<p class="tags">اینها مخزن و تاریخ دارند، ولی کدشان خط‌به‌خط '
        "خوانده نشده — پس عددی هم برایشان نوشته نشده.</p>"
        + others
        + '<p class="tags">تاریخ‌ها تاریخ ساخت مخزن‌اند. جایی که عدد هست، '
        "شمارش است نه تخمین؛ جایی که عدد نیست، یعنی شمرده نشده — و حدس "
        "زده هم نشده.</p>"
        '<div class="cta"><p>می‌خواهید ببینید این برای کارِ خودتان چه شکلی '
        'می‌شود؟</p><p><a href="/">همین‌جا با همزاد دیجیتال حرف بزنید</a> — '
        f'یا <a href="/{PERSON_SLUG}">دربارهٔ سازنده‌اش بخوانید</a>.</p></div>'
    )

    jsonld = {
        "@context": "https://schema.org",
        "@graph": [
            ORGANISATION,
            PERSON,
            {
                "@type": "CollectionPage",
                "@id": PRODUCTS_URL,
                "url": PRODUCTS_URL,
                "name": "محصولات و سیستم‌ها",
                "inLanguage": "fa-IR",
                "abstract": PRODUCTS_ANSWER,
                "isPartOf": {"@id": SITE + "/#organization"},
                "isAccessibleForFree": True,
                "mainEntity": {
                    "@type": "ItemList",
                    "numberOfItems": len(PRODUCTS),
                    "itemListElement": [
                        {
                            "@type": "ListItem",
                            "position": i,
                            "item": {
                                "@type": "SoftwareApplication",
                                "name": pr["name"],
                                "applicationCategory": "BusinessApplication",
                                "description": pr["kind"] + " — " + pr["lede"],
                                "inLanguage": "fa",
                                "author": {"@id": SITE + "/#person"},
                                "publisher": {"@id": SITE + "/#organization"},
                            },
                        }
                        for i, pr in enumerate(PRODUCTS, 1)
                    ],
                },
            },
            {
                "@type": "BreadcrumbList",
                "@id": PRODUCTS_URL + "#breadcrumb",
                "itemListElement": [
                    {"@type": "ListItem", "position": 1,
                     "name": "Vandidad Group", "item": SITE},
                    {"@type": "ListItem", "position": 2,
                     "name": "محصولات و سیستم‌ها"},
                ],
            },
        ],
    }

    return shell(
        title="محصولات و سیستم‌های وندیداد گروپ",
        description=(
            "سه سیستم‌عامل هوش مصنوعی برای صنعت‌های مشخص: VANTA برای املاک، "
            "AIOS Twin روی چهار کانال، و همزاد سوشیال که یک صفحهٔ اینستاگرام "
            "را کامل خودش اداره می‌کند."
        ),
        canonical=PRODUCTS_URL,
        body=body,
        jsonld=jsonld,
    )


RECORD_ANSWER = (
    "هادی بخت‌زاده پیش از هوش مصنوعی، از ۱۳۸۲ کسب‌وکار گردانده است: شرکت "
    "وندیداد در ایران با شمارهٔ ثبت ۱۴۸۴۰ ثبت شد و در تولید آثار فرهنگی و "
    "هنری کار می‌کرد — از جمله برنامهٔ گروه کامکارها با تمبر یادبود ملی در "
    "۱۳۸۸ و تأسیس مدرسهٔ سینمایی استاد مسعود کیمیایی در شیراز در ۱۳۹۱. از "
    "۱۵ مارس ۲۰۱۸ در ازمیر ترکیه، وندیداد گروپ (ثبت تجاری ۲۰۲۷۸۳) در "
    "نمایندگی برندهای ساختمانی، سرمایه‌گذاری املاک، گردشگری و بازرگانی "
    "فعال بود. از ۱۴۰۴ تمرکز کامل روی معماری و ارکستراسیون هوش مصنوعی است."
)


def render_record_page() -> str:
    """The record page — what he did before the AI work, and why it matters.

    Its job is fixed in docs/page-contract.md: answer "who is this person" for
    a reader and for a knowledge graph, and stay off the product pages so a
    buyer evaluating an AI system is never asked to care about a concert.

    It is deliberately NOT a second ProfilePage. The person has one record
    page — /hadi-bakhtzadeh — and two ProfilePage nodes sharing one @id is
    precisely the defect that had /about describing him differently from
    every other page. This is a WebPage whose `about` points at that same @id,
    with `mentions` naming the public figures the record touches.
    """
    chapters = []
    for ch in RECORD_CHAPTERS:
        rows = []
        for when, what, link in ch["items"]:
            label = (f'<a href="{link}" target="_blank" rel="noopener">'
                     f"{html.escape(what)}</a>" if link else html.escape(what))
            rows.append(f'<div class="row"><div class="k">'
                        f'{html.escape(when) if when else "—"}</div>'
                        f'<div class="v">{label}</div></div>')
        chapters.append(
            f'<section class="prod" id="{ch["id"]}">'
            f'<h2>{html.escape(ch["title"])}'
            f'<span class="pk">{html.escape(ch["span"])}</span></h2>'
            f'<p class="lede2">{html.escape(ch["lede"])}</p>'
            f'<div class="record">{"".join(rows)}</div>'
            "</section>"
        )

    body = (
        "<header>"
        f'<p class="eyebrow"><a href="/{PERSON_SLUG}">هادی بخت‌زاده</a></p>'
        "<h1>کارنامه — پیش از هوش مصنوعی</h1>"
        '<p class="lede">کارنامهٔ محمد هادی بخت‌زاده (هادی بخت‌زاده، هادی '
        "بخت زاده، محمد هادی بخت زاده) در سه دوره، با تاریخ و شمارهٔ ثبت. "
        "این صفحه ادعای محصولی ندارد؛ سابقه است.</p>"
        "</header>"
        '<section class="answer" aria-label="پاسخ کوتاه">'
        "<h2>در یک نگاه</h2>"
        f"<p>{html.escape(RECORD_ANSWER)}</p></section>"
        + "".join(chapters)
        + "<h2>چرا این سابقه به کارِ امروز ربط دارد</h2>"
        f'<p class="lede2">{html.escape(RECORD_THESIS)}</p>'
        '<p class="tags">تاریخ‌ها همان‌اند که هستند و گِرد نشده‌اند. '
        "شمارهٔ ثبت ایران ۱۴۸۴۰ و ثبت تجاری ازمیر ۲۰۲۷۸۳ در سامانه‌های "
        "رسمی خودشان قابل بررسی‌اند.</p>"
        '<div class="cta"><p>کارِ امروز جای دیگری است.</p>'
        f'<p><a href="/{PRODUCTS_SLUG}">سه سیستمی که ساخته</a> · '
        f'<a href="/{PERSON_SLUG}">پروندهٔ کامل</a></p></div>'
    )

    # Entities a knowledge graph already knows. Naming them with `mentions` is
    # what lets an unknown entity be placed by its edges — the same mechanism
    # the articles use with `about`.
    mentioned = []
    for ch in RECORD_CHAPTERS:
        for _, _, link in ch["items"]:
            if link and link not in mentioned:
                mentioned.append(link)

    jsonld = {
        "@context": "https://schema.org",
        "@graph": [
            ORGANISATION,
            PERSON,
            {
                "@type": "WebPage",
                "@id": RECORD_URL,
                "url": RECORD_URL,
                "name": "کارنامه — هادی بخت‌زاده",
                "inLanguage": "fa-IR",
                "abstract": RECORD_ANSWER,
                "about": {"@id": SITE + "/#person"},
                "isPartOf": {"@id": SITE + "/#organization"},
                "isAccessibleForFree": True,
                "mentions": [{"@id": u} for u in mentioned],
            },
            {
                "@type": "BreadcrumbList",
                "@id": RECORD_URL + "#breadcrumb",
                "itemListElement": [
                    {"@type": "ListItem", "position": 1,
                     "name": "Vandidad Group", "item": SITE},
                    {"@type": "ListItem", "position": 2,
                     "name": "هادی بخت‌زاده", "item": PERSON_URL},
                    {"@type": "ListItem", "position": 3, "name": "کارنامه"},
                ],
            },
        ],
    }

    return shell(
        title="کارنامهٔ هادی بخت‌زاده — پیش از هوش مصنوعی",
        description=(
            "سابقهٔ هادی بخت‌زاده از ۱۳۸۲: تولید آثار فرهنگی و هنری در ایران، "
            "بازرگانی و سرمایه‌گذاری در ازمیر، و از ۱۴۰۴ معماری هوش مصنوعی."
        ),
        canonical=RECORD_URL,
        body=body,
        jsonld=jsonld,
    )


STATIC_URLS = [
    ("/", "weekly", "1.0"),
    ("/about", "monthly", "0.8"),
    (f"/{PERSON_SLUG}", "weekly", "0.9"),
    (f"/{PRODUCTS_SLUG}", "weekly", "0.9"),
    (f"/{RECORD_SLUG}", "monthly", "0.6"),
    ("/blog", "weekly", "0.7"),
    ("/hamzad", "weekly", "0.7"),
    ("/privacy", "yearly", "0.3"),
    ("/terms", "yearly", "0.3"),
    ("/data-deletion", "yearly", "0.3"),
]


ABOUT_START = "<!-- PERSON:START -->"
ABOUT_END = "<!-- PERSON:END -->"

PROFILE_START = "<!-- PROFILE:START -->"
PROFILE_END = "<!-- PROFILE:END -->"


def render_about_profile(existing: str) -> str:
    """Generate /about's ProfilePage JSON-LD instead of keeping a copy of it.

    This block was written by hand and it had already drifted: it declared
    the same @id as the Person every other page carries, with `sameAs: []`
    and mainEntityOfPage pointing at /about. Two pages describing one entity
    two different ways is worse than one page describing it once — an empty
    sameAs on a page a crawler trusts reads as "this person has no profiles",
    which is the opposite of what the other pages now say.
    """
    if PROFILE_START not in existing or PROFILE_END not in existing:
        return existing
    block = (
        PROFILE_START + "\n"
        "<!-- Generated by tools/build_content.py. Do not edit by hand: this\n"
        "     is the same Person as the one on /hadi-bakhtzadeh, sharing one\n"
        "     @id, so a hand-kept copy drifts and the two pages end up\n"
        "     describing one entity two different ways. -->\n"
        '<script type="application/ld+json">\n'
        + json.dumps({
            "@context": "https://schema.org",
            # AboutPage, not a second ProfilePage. /about is the company's
            # page; the founder appears on it, but the page a crawler should
            # treat as *the* profile is /hadi-bakhtzadeh, which the Person's
            # own mainEntityOfPage names. Two ProfilePage nodes for one
            # person is an ambiguity a crawler has to resolve by guessing —
            # found by a full re-check on 2026-09-06, and it is the same
            # class of defect as the hand-kept copy that preceded it.
            "@type": "AboutPage",
            "@id": SITE + "/about#page",
            "url": SITE + "/about",
            "inLanguage": "en",
            "about": {"@id": SITE + "/#organization"},
            "mentions": {"@id": SITE + "/#person"},
            "breadcrumb": {"@id": SITE + "/about#breadcrumb"},
            "mainEntity": ORGANISATION,
        }, ensure_ascii=False, indent=1)
        + "\n</script>\n"
        # Every other static page carries a breadcrumb and this one did not.
        # Search Console's live test made it visible: /hadi-bakhtzadeh,
        # /mahsoolat and /karnameh each reported "Breadcrumbs: 1 valid item"
        # while /about reported "URL has no enhancements". A breadcrumb is
        # what puts a readable trail under the result instead of a bare URL,
        # so its absence was costing the company's own page the presentation
        # the newer pages already get. The homepage is deliberately still
        # without one: it is the root, and a trail to where you already are
        # says nothing.
        + '<script type="application/ld+json">\n'
        + json.dumps({
            "@context": "https://schema.org",
            "@type": "BreadcrumbList",
            "@id": SITE + "/about#breadcrumb",
            "itemListElement": [
                {"@type": "ListItem", "position": 1,
                 "name": "Vandidad Group", "item": SITE},
                {"@type": "ListItem", "position": 2, "name": "دربارهٔ ما"},
            ],
        }, ensure_ascii=False, indent=1)
        + "\n</script>\n"
        + '<script type="application/ld+json">\n'
        # The full Person object still lives on this page — the founder must
        # resolve here — but as an entity the page mentions, not as the page's
        # own identity.
        + json.dumps({"@context": "https://schema.org", **PERSON},
                     ensure_ascii=False, indent=1)
        + "\n</script>\n" + PROFILE_END
    )
    head, _, rest = existing.partition(PROFILE_START)
    _, _, tail = rest.partition(PROFILE_END)
    return head + block + tail


def render_about_person(existing: str, articles: list[Article]) -> str:
    """Rewrite the person section of about.html as a record, not a biography.

    The company section on this page works because every line of it is a field
    with a value a stranger can check against a government register. The
    person section is built the same way and in the same markup: fields and
    values, each one either a public registration, a name actually in use, or
    a count taken from the articles themselves. No prose, no adjectives, and
    nothing that rests on the reader taking his word for it.

    The article list and its count are generated from the articles, so the
    record grows on its own as the queue publishes and the claim can never
    drift from the evidence.
    """
    if ABOUT_START not in existing or ABOUT_END not in existing:
        return existing

    live = sorted(articles, key=lambda a: a.published, reverse=True)
    items = "".join(
        f'<li><a href="{a.url}">{html.escape(a.title)}</a>'
        f'<span class="d">{a.published.isoformat()}</span></li>'
        for a in live
    )
    first = min((a.published for a in live), default=None)
    since = f" — publishing since {first.isoformat()}" if first else ""

    def row(key: str, value: str) -> str:
        return (f'      <div class="row"><div class="k">{key}</div>'
                f'<div class="v">{value}</div></div>\n')

    fa = '<span dir="rtl" lang="fa">{}</span>'
    names_fa = " · ".join(fa.format(n) for n in PERSON["alternateName"][:2])
    names_en = " · ".join(
        html.escape(n) for n in
        ["Mohammadhadi Bakhtzadeh", "Mohammad Hadi Bakhtzadeh"]
    )
    github = PERSON["sameAs"][0]
    record = (
        row("Name", html.escape(PERSON["name"]) + " " + names_fa)
        + row("Also written", names_en)
        + row("Role", html.escape(PERSON["jobTitle"]))
        + row("Company", "Founder, Vandidad Group "
              '<span dir="rtl" lang="fa">وندیداد گروپ</span>')
        + row("Founded", "15.03.2018 "
              '<span style="color:var(--muted);font-size:13.5px">'
              "— company trading since that date</span>")
        + row("Trade registry no.", "<code>202783</code> "
              '<span style="color:var(--muted);font-size:13.5px">'
              "İzmir Trade Registry</span>")
        + row("Chamber reg. no.", "<code>1888691</code>"
              '<a href="https://eoda.izto.org.tr/web/oda_sicil_belge_sorgu.aspx"'
              ' target="_blank" rel="noopener">Verify at İZTO →</a>')
        + row("Based in", "Konak, İzmir, Türkiye")
        + row("Languages", "Persian (native) · English · Turkish")
        + row("Field", "AI systems architecture · agentic AI · "
              "conversational design for Persian-language business")
        + row("Writing", f"{len(live)} signed articles on this site{since}")
        + row("Code", f'<a href="{github}" target="_blank" rel="noopener">'
              "github.com/vandidadhonar-sudo →</a> "
              '<span style="color:var(--muted);font-size:13.5px">'
              "— the account this site is built and served from</span>")
        + row("Full record", f'<a href="/{PERSON_SLUG}">'
              "vandidad.xyz/hadi-bakhtzadeh →</a> "
              '<span style="color:var(--muted);font-size:13.5px">'
              "— the same record in Persian, with the verification links"
              "</span>")
    )
    block = f"""{ABOUT_START}
  <section id="person" class="person">
    <h2>Founder record</h2>
    <div class="record">
{record}    </div>
    <p class="note">Every field above is either a public registration that can
      be confirmed through the portals linked here, or a count taken from the
      articles listed below.</p>

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
    # Every static page carries a lastmod, taken from the file that produces
    # it. Without one, a crawler has nothing to compare against and falls back
    # to its own slow schedule — which is what the four newest pages were
    # doing: published, in the sitemap, announced through IndexNow, and still
    # giving a crawler no reason to come back and look. changefreq and
    # priority are hints a crawler may ignore; lastmod is the one it uses.
    static_file = {
        "/": "index.html",
        "/about": "about.html",
        f"/{PERSON_SLUG}": f"{PERSON_SLUG}.html",
        f"/{PRODUCTS_SLUG}": f"{PRODUCTS_SLUG}.html",
        f"/{RECORD_SLUG}": f"{RECORD_SLUG}.html",
        "/privacy": "privacy.html",
        "/terms": "terms.html",
        "/data-deletion": "data-deletion.html",
    }
    for path, freq, prio in STATIC_URLS:
        if path in ("/blog", "/hamzad") and path not in live:
            continue
        rows.append("  <url>")
        rows.append(f"    <loc>{SITE}{path}</loc>")
        name = static_file.get(path)
        if name and (ROOT / name).exists():
            stamp = date.fromtimestamp((ROOT / name).stat().st_mtime)
            rows.append(f"    <lastmod>{stamp.isoformat()}</lastmod>")
        elif path in ("/blog", "/hamzad"):
            # A collection is as fresh as its newest article.
            newest = max((a.updated or a.published) for a in articles
                         if f"/{a.collection}" == path)
            rows.append(f"    <lastmod>{newest.isoformat()}</lastmod>")
        rows.append(f"    <changefreq>{freq}</changefreq>")
        rows.append(f"    <priority>{prio}</priority>")
        rows.append("  </url>")
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
        (f"{PERSON_SLUG}.html", render_person_page(everything)),
        (f"{PRODUCTS_SLUG}.html", render_products_page()),
        (f"{RECORD_SLUG}.html", render_record_page()),
    ]
    if llms.exists():
        outputs.append(
            ("llms.txt", render_llms(llms.read_text("utf-8"), everything))
        )
    about = ROOT / "about.html"
    if about.exists():
        outputs.append(
            ("about.html",
             render_about_profile(
                 render_about_person(about.read_text("utf-8"), everything)))
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

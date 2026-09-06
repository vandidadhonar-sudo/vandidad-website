#!/usr/bin/env python3
"""Tests for the publishing pipeline.

These cover the parts that only ever run unattended, on a schedule, with
nobody watching — where a mistake is discovered by its absence: an article
that quietly never published, or two pages competing for one phrase.

Run: python3 tools/test_pipeline.py
"""

from __future__ import annotations

import json
import pathlib
import shutil
import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import build_content as bc          # noqa: E402
import indexnow                     # noqa: E402
import release_next as rn           # noqa: E402


ARTICLE = """---
title: یک عنوان آزمایشی برای بررسی خط لوله
description: توضیح کوتاه برای آزمون.
date: 2020-01-01
updated: 2020-01-01
collection: hamzad
publish_on: {when}
target_keyword: {kw}
summary_en: An English summary, required by the gate.
---

این یک متن آزمایشی است. برای کسب‌وکار ایرانی یعنی چه — این بخش لازم است.
"""


class Queue(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        (self.tmp / "content" / "queue").mkdir(parents=True)
        (self.tmp / "content" / "hamzad").mkdir(parents=True)
        self._saved = (rn.ROOT, rn.QUEUE, rn.CONTENT)
        rn.ROOT, rn.QUEUE, rn.CONTENT = (
            self.tmp, self.tmp / "content" / "queue", self.tmp / "content")

    def tearDown(self):
        rn.ROOT, rn.QUEUE, rn.CONTENT = self._saved
        shutil.rmtree(self.tmp)

    def write(self, name: str, when: date, kw: str = "عبارت آزمایشی"):
        p = rn.QUEUE / name
        p.write_text(ARTICLE.format(when=when.isoformat(), kw=kw), encoding="utf-8")
        return p

    def test_nothing_due_leaves_the_queue_alone(self):
        self.write("later.md", date.today() + timedelta(days=5))
        self.assertEqual(rn.main(), 0)
        self.assertTrue((rn.QUEUE / "later.md").exists())

    def test_due_article_moves_into_its_collection(self):
        self.write("today.md", date.today())
        rn.main()
        moved = rn.CONTENT / "hamzad" / "today.md"
        self.assertTrue(moved.exists())
        self.assertFalse((rn.QUEUE / "today.md").exists())

    def test_publish_date_becomes_the_day_it_appeared(self):
        self.write("today.md", date.today())
        rn.main()
        text = (rn.CONTENT / "hamzad" / "today.md").read_text(encoding="utf-8")
        stamp = date.today().isoformat()
        self.assertIn(f"date: {stamp}", text)
        self.assertIn(f"updated: {stamp}", text)
        self.assertNotIn("publish_on", text)

    def test_only_one_article_leaves_per_run(self):
        # A backlog must not empty itself onto the site in one morning.
        for i in range(3):
            self.write(f"a{i}.md", date.today() - timedelta(days=i))
        rn.main()
        self.assertEqual(len(list(rn.QUEUE.glob("*.md"))), 2)

    def test_the_oldest_overdue_article_goes_first(self):
        self.write("newer.md", date.today())
        self.write("older.md", date.today() - timedelta(days=4))
        rn.main()
        self.assertTrue((rn.CONTENT / "hamzad" / "older.md").exists())
        self.assertTrue((rn.QUEUE / "newer.md").exists())

    def test_a_broken_date_is_reported_not_skipped_in_silence(self):
        p = rn.QUEUE / "bad.md"
        p.write_text(ARTICLE.format(when="2026-13-45", kw="x"), encoding="utf-8")
        self.assertEqual(rn.queued(), [])
        self.assertTrue(p.exists())

    def test_it_refuses_to_overwrite_a_published_article(self):
        self.write("clash.md", date.today())
        (rn.CONTENT / "hamzad" / "clash.md").write_text("existing", encoding="utf-8")
        with self.assertRaises(SystemExit):
            rn.main()
        self.assertEqual(
            (rn.CONTENT / "hamzad" / "clash.md").read_text(encoding="utf-8"),
            "existing")


class Keywords(unittest.TestCase):
    """Persian is typed several ways for the same word; the duplicate check
    has to see through that or it never fires."""

    def test_arabic_and_persian_letters_fold_together(self):
        self.assertEqual(bc._norm_keyword("چت بات فارسي"),
                         bc._norm_keyword("چت بات فارسی"))

    def test_zero_width_non_joiner_folds_to_a_space(self):
        self.assertEqual(bc._norm_keyword("چت‌بات فارسی"),
                         bc._norm_keyword("چت بات فارسی"))

    def test_spacing_and_case_do_not_make_a_new_target(self):
        self.assertEqual(bc._norm_keyword("  AI   Agent "),
                         bc._norm_keyword("ai agent"))

    def test_the_two_spellings_of_kasbokar_are_one_phrase(self):
        # «کسب‌وکار» and «کسب و کار» are the same word to a reader and to a
        # search engine. Folding the half-space to a plain space alone left
        # «کسب وکار», which matched neither — found when a target keyword was
        # rewritten into the form people actually type.
        self.assertEqual(bc._norm_keyword("چت‌بات برای کسب‌وکار"),
                         bc._norm_keyword("چت بات برای کسب و کار"))
        self.assertEqual(bc._norm_keyword("گفت‌وگو"), bc._norm_keyword("گفت و گو"))

    def test_different_phrases_stay_different(self):
        self.assertNotEqual(bc._norm_keyword("ایجنت فروش"),
                            bc._norm_keyword("ایجنت پشتیبانی"))


class IndexNow(unittest.TestCase):
    def test_it_reads_every_url_out_of_the_sitemap(self):
        xml = ("<urlset><url><loc>https://vandidad.xyz/a</loc></url>"
               "<url><loc>\n  https://vandidad.xyz/b\n</loc></url></urlset>")
        self.assertEqual(indexnow.urls_from_sitemap(xml),
                         ["https://vandidad.xyz/a", "https://vandidad.xyz/b"])

    def test_the_key_location_matches_the_file_the_worker_serves(self):
        body = indexnow.payload(["https://vandidad.xyz/a"])
        self.assertEqual(body["keyLocation"],
                         f"https://vandidad.xyz/{indexnow.KEY}.txt")
        self.assertEqual(body["host"], "vandidad.xyz")

    def test_the_payload_is_json_the_endpoint_accepts(self):
        json.loads(json.dumps(indexnow.payload(["https://vandidad.xyz/a"])))


class Faq(unittest.TestCase):
    """FAQ markup that does not match visible text is what gets a site's rich
    results withdrawn, so an answerless question must never render."""

    def _parse(self, extra: str):
        # The parser reads the collection from the folder name, so the fixture
        # has to live in one that is really called hamzad.
        root = Path(tempfile.mkdtemp())
        (root / "hamzad").mkdir()
        tmp = root / "hamzad" / "x.md"
        tmp.write_text(
            "---\ntitle: ت\ndescription: د\ndate: 2026-01-01\n"
            "collection: hamzad\n" + extra + "---\n\nمتن.\n", encoding="utf-8")
        try:
            return bc.parse(tmp)
        finally:
            shutil.rmtree(root)

    def test_a_question_without_an_answer_is_rejected(self):
        with self.assertRaises(bc.BuildError):
            self._parse("faq:\n  - q: پرسشی؟\n    a: ''\n")

    def test_a_question_and_answer_pair_is_kept(self):
        a = self._parse("faq:\n  - q: پرسشی؟\n    a: پاسخی.\n")
        self.assertEqual(a.faq, [{"q": "پرسشی؟", "a": "پاسخی."}])

    def test_about_must_be_an_address_not_a_name(self):
        with self.assertRaises(bc.BuildError):
            self._parse("about:\n  - هوش مصنوعی\n")

    def test_about_accepts_an_entity_address(self):
        a = self._parse("about:\n  - https://fa.wikipedia.org/wiki/X\n")
        self.assertEqual(a.about, ["https://fa.wikipedia.org/wiki/X"])


class Byline(unittest.TestCase):
    """An author that exists only in JSON-LD answers the crawler and not the
    reader, and Google's quality guidance asks whether a person can tell who
    wrote a page."""

    def _render(self):
        a = bc.Article(slug="s", collection="hamzad", title="ت",
                       description="د", published=date(2026, 1, 1),
                       body_md="متن.", summary_en="An English summary.")
        return bc.render_article(a)

    def test_the_authors_persian_name_is_visible_on_the_page(self):
        self.assertIn("نویسنده:", self._render())
        self.assertIn("هادی بخت‌زاده", self._render())

    def test_the_byline_links_to_the_page_that_identifies_him(self):
        # The Persian person page, not /about. Someone reading a Persian
        # article who wants to know who wrote it should not be handed an
        # English company page.
        self.assertIn('href="/hadi-bakhtzadeh" rel="author"', self._render())

    def test_the_structured_data_still_names_the_same_person(self):
        self.assertIn('"@id": "https://vandidad.xyz/#person"', self._render())


class WordFloor(unittest.TestCase):
    def test_a_new_short_article_is_refused(self):
        a = bc.Article(slug="brand-new", collection="hamzad", title="ت",
                       description="د", published=date(2026, 9, 4),
                       body_md="کلمه " * 200 + "برای کسب‌وکار ایرانی یعنی چه",
                       summary_en="An English summary.")
        with self.assertRaises(bc.BuildError):
            bc.validate(a)

    def test_an_article_still_on_the_debt_list_builds(self):
        # LEGACY_SHORT shrinks as each short article is expanded, so naming one
        # here would break the test the day that article is fixed — which is
        # exactly what happened. Take whichever entries remain, and when the
        # list is finally empty the debt is paid and there is nothing to guard.
        if not bc.LEGACY_SHORT:
            self.skipTest("no short articles left — the debt is paid")
        a = bc.Article(slug=sorted(bc.LEGACY_SHORT)[0], collection="hamzad",
                       title="ت", description="د", published=date(2026, 8, 12),
                       body_md="کلمه " * 200 + "برای کسب‌وکار ایرانی یعنی چه",
                       summary_en="An English summary.")
        bc.validate(a)

    def test_an_expanded_article_is_off_the_debt_list(self):
        # The list is a record of debt, not a permanent exemption: once an
        # article passes the floor on its own, its name must not still be in it.
        for slug in bc.LEGACY_SHORT:
            path = pathlib.Path("content/hamzad") / f"{slug}.md"
            if not path.exists():
                continue
            self.assertLess(
                bc.parse(path).words, 1500,
                f"{slug} is long enough now — remove it from LEGACY_SHORT")


class TitleLength(unittest.TestCase):
    """Bing's site scan flagged three pages as "Title too long". None of the
    article titles were over on their own — the brand suffix pushed them over.
    So the suffix is conditional, and the gate guards the bare title."""

    def test_the_brand_is_appended_when_it_fits(self):
        self.assertEqual(bc.page_title("عنوان کوتاه"),
                         "عنوان کوتاه" + bc.BRAND_SUFFIX)

    def test_the_brand_is_dropped_rather_than_truncating_the_title(self):
        long = "ب" * (bc.TITLE_LIMIT - 5)
        self.assertEqual(bc.page_title(long), long)

    def test_the_rendered_title_never_passes_the_limit(self):
        for n in range(1, bc.TITLE_LIMIT + 1):
            self.assertLessEqual(len(bc.page_title("ب" * n)), bc.TITLE_LIMIT)

    def test_a_title_over_the_limit_is_refused(self):
        a = bc.Article(slug="s", collection="hamzad",
                       title="ب" * (bc.TITLE_LIMIT + 1), description="د",
                       published=date(2026, 9, 4),
                       body_md="کلمه " * 1500 + "برای کسب‌وکار ایرانی یعنی چه",
                       summary_en="An English summary.")
        with self.assertRaises(bc.BuildError):
            bc.validate(a)


class AnswerBlock(unittest.TestCase):
    """The paragraph a model quotes and a hurried reader reads. It has to
    exist, contain the phrase that was searched, and be short enough to lift
    in one piece."""

    def _article(self, **kw):
        base = dict(slug="s", collection="hamzad", title="ت", description="د",
                    published=date(2026, 9, 4),
                    body_md="کلمه " * 1500 + "برای کسب‌وکار ایرانی یعنی چه",
                    summary_en="An English summary.",
                    target_keyword="ایجنت فروش",
                    answer="ایجنت فروش " + "پاسخ " * 60)
        base.update(kw)
        return bc.Article(**base)

    def test_an_article_without_one_is_refused(self):
        with self.assertRaises(bc.BuildError):
            bc.validate(self._article(answer=""))

    def test_one_too_short_to_say_anything_is_refused(self):
        with self.assertRaises(bc.BuildError):
            bc.validate(self._article(answer="ایجنت فروش خوب است."))

    def test_one_too_long_to_quote_is_refused(self):
        with self.assertRaises(bc.BuildError):
            bc.validate(self._article(answer="ایجنت فروش " + "کلمه " * 200))

    def test_it_must_contain_the_phrase_the_reader_searched(self):
        with self.assertRaises(bc.BuildError):
            bc.validate(self._article(answer="پاسخی " * 60))

    def test_a_good_one_passes(self):
        bc.validate(self._article())

    def test_it_is_rendered_above_the_article_not_below(self):
        html = bc.render_article(self._article())
        self.assertIn("پاسخ کوتاه", html)
        self.assertLess(html.index('class="answer"'), html.index("<article>"))

    def test_the_structured_data_repeats_the_visible_answer(self):
        a = self._article(answer="ایجنت فروش " + "متنِ یکتا " * 30)
        html = bc.render_article(a)
        # Markup that does not match visible text is what gets rich results
        # withdrawn, so the abstract must be the same sentence the reader sees.
        self.assertEqual(html.count("متنِ یکتا"), 60)

    def test_the_phrase_check_sees_through_persian_spelling(self):
        self.assertTrue(bc._phrase_in("یک چت‌بات فارسی", "چت بات فارسي"))
        self.assertFalse(bc._phrase_in("یک ایجنت فروش", "ایجنت پشتیبانی"))


class PersonEntity(unittest.TestCase):
    """Searching the owner's name returned "no detailed biography published"
    and, for one spelling, "not registered in official sources". The cause was
    four spellings across the site and a founder object with no @id tying it
    to the author of the articles. These lock the repair shut."""

    def test_every_spelling_he_might_be_searched_by_is_declared(self):
        names = set(bc.PERSON["alternateName"]) | {bc.PERSON["name"]}
        for spelling in ("هادی بخت‌زاده", "محمد هادی بخت‌زاده",
                         "Mohammadhadi Bakhtzadeh", "Hadi Bakhtzadeh"):
            self.assertIn(spelling, names)

    def test_the_person_has_one_identity(self):
        self.assertEqual(bc.PERSON["@id"], bc.SITE + "/#person")

    def test_one_page_is_declared_as_his_record(self):
        # The Persian person page. Whatever it is, mainEntityOfPage and url
        # must name the same page: two answers to "which page is this person"
        # is the same defect as no answer.
        self.assertEqual(bc.PERSON["mainEntityOfPage"]["@id"], bc.PERSON_URL)
        self.assertEqual(bc.PERSON["url"], bc.PERSON_URL)

    def test_the_person_page_answers_the_question_in_persian(self):
        page = bc.render_person_page([])
        for must in ("هادی بخت‌زاده کیست؟", "هوشواره", "۲۰۲۷۸۳",
                     '<html lang="fa"', "ProfilePage", "FAQPage"):
            self.assertIn(must, page)

    def test_the_person_page_is_in_the_sitemap(self):
        self.assertIn(bc.PERSON_URL, bc.render_sitemap([]))

    def test_sameAs_is_present_even_when_empty(self):
        # The field must exist so adding a real profile is one line, and it
        # must never be filled with a guess: a wrong sameAs points the entity
        # at someone else.
        self.assertIsInstance(bc.PERSON["sameAs"], list)

    def test_the_generated_section_lists_the_articles(self):
        page = ("x" + bc.ABOUT_START + "old" + bc.ABOUT_END + "y")
        a = bc.Article(slug="s", collection="hamzad", title="عنوان",
                       description="د", published=date(2026, 1, 1), body_md="م")
        out = bc.render_about_person(page, [a])
        self.assertIn("عنوان", out)
        self.assertIn("2026-01-01", out)
        self.assertNotIn("old", out)
        self.assertTrue(out.startswith("x") and out.endswith("y"))

    def test_a_page_without_markers_is_left_alone(self):
        self.assertEqual(bc.render_about_person("no markers", []), "no markers")


class CanonicalHost(unittest.TestCase):
    """The Worker 301s www to the apex domain. A canonical or og:url on www
    therefore points at a URL that immediately redirects, while the sitemap
    lists the apex — two contradictory instructions about which URL is real.
    /about carried exactly that, on the page meant to be the founder's record."""

    def _pages(self):
        root = Path(__file__).resolve().parent.parent
        for name in ("index.html", "about.html", "privacy.html",
                     "terms.html", "data-deletion.html"):
            f = root / name
            if f.exists():
                yield name, f.read_text(encoding="utf-8")

    def test_no_page_declares_itself_canonical_on_www(self):
        for name, body in self._pages():
            self.assertNotIn("www.vandidad.xyz", body,
                             f"{name} points at www, which the Worker redirects")

    def test_every_page_has_one_canonical_on_the_apex_host(self):
        import re
        for name, body in self._pages():
            hits = re.findall(r'rel="canonical" href="(https://[^"]+)"', body)
            self.assertEqual(len(hits), 1, f"{name} has {len(hits)} canonicals")
            self.assertTrue(hits[0].startswith("https://vandidad.xyz"), hits[0])


class Llms(unittest.TestCase):
    def test_it_replaces_only_its_own_section(self):
        existing = ("intro\n\n## Individual articles\n\nold list\n\n"
                    "## Machine-readable\n\nkeep me\n")
        art = bc.Article(slug="s", collection="hamzad", title="ت",
                         description="د", published=date(2026, 1, 1),
                         body_md="x", llms_line="One line")
        out = bc.render_llms(existing, [art])
        self.assertIn("intro", out)
        self.assertIn("keep me", out)
        self.assertIn("/hamzad/s", out)
        self.assertNotIn("old list", out)

    def test_a_file_without_the_heading_is_left_untouched(self):
        existing = "just prose, no generated section\n"
        self.assertEqual(bc.render_llms(existing, []), existing)



class AboutProfileIsGenerated(unittest.TestCase):
    """The /about ProfilePage block must come from PERSON, not from a copy.

    It was hand-written and had drifted to `sameAs: []` while every other
    page carried real profiles — one entity, two contradictory descriptions.
    """

    def _about(self):
        return (pathlib.Path(bc.__file__).resolve().parent.parent
                / "about.html").read_text("utf-8")

    def test_the_block_is_between_the_markers(self):
        about = self._about()
        self.assertIn(bc.PROFILE_START, about)
        self.assertIn(bc.PROFILE_END, about)

    def test_it_carries_the_same_profiles_as_the_person(self):
        rendered = bc.render_about_profile(self._about())
        for link in bc.PERSON["sameAs"]:
            self.assertIn(link, rendered)

    def test_it_points_at_the_persian_page_as_his_record(self):
        self.assertIn(bc.PERSON_URL, bc.render_about_profile(self._about()))


class Breadcrumbs(unittest.TestCase):
    """Every page a stranger can land on says where it sits.

    Search Console's live test reported "Breadcrumbs: 1 valid item" for
    /hadi-bakhtzadeh, /mahsoolat and /karnameh, and "URL has no enhancements"
    for /about. The gap was invisible from inside the repository because
    nothing asked the question. A breadcrumb is what turns a bare URL under a
    result into a readable trail, so the company's own page was getting a
    worse presentation than the pages built after it.

    The homepage is exempt on purpose: it is the root of the trail.
    """

    PAGES = ["about.html", "hadi-bakhtzadeh.html", "mahsoolat.html",
             "karnameh.html"]

    def _root(self):
        return pathlib.Path(bc.__file__).resolve().parent.parent

    def test_every_static_page_but_the_homepage_has_one(self):
        for name in self.PAGES:
            path = self._root() / name
            if not path.exists():
                continue
            with self.subTest(page=name):
                self.assertIn("BreadcrumbList", path.read_text("utf-8"),
                              f"{name} has no breadcrumb")

    def test_the_homepage_does_not(self):
        self.assertNotIn(
            "BreadcrumbList",
            (self._root() / "index.html").read_text("utf-8"))


class PageContract(unittest.TestCase):
    """docs/page-contract.md, enforced rather than remembered.

    Each page has one audience and one job. The record — concerts, theatre,
    the Iranian registration — belongs on /karnameh and nowhere else: a buyer
    evaluating an AI system should never have to work out what a concert has
    to do with it, and a vendor reviewing the company should see one focused
    business. Twice already a rule of this kind lived only in a conversation
    and was lost; this one fails the build instead.
    """

    RECORD_WORDS = ("کنسرت", "تئاتر", "تهیه‌کننده", "۱۴۸۴۰", "کیمیایی",
                    "کامکارها", "نوازنده")

    def _root(self):
        return pathlib.Path(bc.__file__).resolve().parent.parent

    def test_the_record_stays_off_the_product_page(self):
        page = bc.render_products_page()
        for word in self.RECORD_WORDS:
            self.assertNotIn(word, page,
                             f"«{word}» روی صفحهٔ محصول آمده — قرارداد صفحه‌ها")

    def test_the_record_stays_off_the_homepage(self):
        home = (self._root() / "index.html").read_text("utf-8")
        for word in self.RECORD_WORDS:
            self.assertNotIn(word, home,
                             f"«{word}» روی صفحهٔ اصلی آمده — قرارداد صفحه‌ها")

    def test_the_record_stays_off_the_company_page(self):
        about = (self._root() / "about.html").read_text("utf-8")
        for word in self.RECORD_WORDS:
            self.assertNotIn(word, about,
                             f"«{word}» روی /about آمده — قرارداد صفحه‌ها")

    def test_the_iranian_company_is_not_declared_as_an_organization(self):
        # Text on the record page: fine, it is personal history. A second
        # Organization node in the graph: not fine — the operating company for
        # this business is the Turkish one, and a reviewer screening the vendor
        # should not find two.
        page = bc.render_record_page()
        self.assertIn("۱۴۸۴۰", page)          # visible text: personal history
        graph = json.loads(
            page.split('<script type="application/ld+json">')[1]
                .split("</script>")[0])
        orgs = [n for n in graph["@graph"] if n.get("@type") == "Organization"]
        self.assertEqual(len(orgs), 1)
        # The one Organization is the Turkish operating company and carries
        # only its own registrations. The İzmir chamber it belongs to is
        # nested inside it, which is a membership, not a second company.
        self.assertEqual(orgs[0]["@id"], bc.SITE + "/#organization")
        # The number may appear in prose — `abstract` mirrors the visible
        # answer block, and matching visible text is a requirement, not a
        # leak. What must never happen is the number appearing as a company
        # identifier, which is what a vendor screening reads.
        orgs_blob = json.dumps(orgs, ensure_ascii=False)
        for form in ("14840", "۱۴۸۴۰"):
            self.assertNotIn(form, orgs_blob)
        person = [n for n in graph["@graph"]
                  if n.get("@id") == bc.SITE + "/#person"][0]
        self.assertNotIn("14840", json.dumps(person, ensure_ascii=False))

    def test_only_one_page_is_the_persons_profile(self):
        # Two ProfilePage nodes on one @id is the defect that had /about
        # describing him differently from every other page.
        graph = json.loads(
            bc.render_record_page()
              .split('<script type="application/ld+json">')[1]
              .split("</script>")[0])["@graph"]
        # No node on this page declares itself the person's profile. The
        # Person's own mainEntityOfPage still names /hadi-bakhtzadeh, which is
        # the point: one @id, one profile page, referenced from here.
        for node in graph:
            self.assertNotEqual(node.get("@type"), "ProfilePage")
        page_node = [n for n in graph if n.get("@id") == bc.RECORD_URL][0]
        self.assertEqual(page_node["@type"], "WebPage")
        self.assertEqual(page_node["about"]["@id"], bc.SITE + "/#person")
        person = [n for n in graph if n.get("@id") == bc.SITE + "/#person"][0]
        self.assertEqual(person["mainEntityOfPage"]["@id"], bc.PERSON_URL)

    def test_the_record_links_to_entities_a_graph_already_knows(self):
        # The mechanism the page exists for: an unknown entity is placed by
        # its edges to known ones.
        page = bc.render_record_page()
        self.assertIn('"mentions"', page)
        self.assertIn("fa.wikipedia.org", page)

    def test_no_rounded_years_anywhere_in_the_record(self):
        page = bc.render_record_page()
        for phrase in ("۲۵ سال", "بیش از دو دهه", "۲۰ سال"):
            self.assertNotIn(phrase, page)


class OneEntityOneDeclaration(unittest.TestCase):
    """No entity is described twice, anywhere.

    Three separate instances of one defect were found in this repository, all
    in about.html: a hand-kept Person that had drifted to `sameAs: []`, a
    ProfilePage competing with the person's real profile page, and a
    hand-written Organization missing the registry identifiers the generated
    one carries. Each was invisible until the file was read whole. These tests
    read it whole every time.
    """

    def _pages(self):
        root = pathlib.Path(bc.__file__).resolve().parent.parent
        return [root / n for n in ("about.html", "hadi-bakhtzadeh.html",
                                   "mahsoolat.html", "karnameh.html")
                if (root / n).exists()]

    def _nodes(self, path):
        import re
        out = []
        text = path.read_text("utf-8")
        for blob in re.findall(
                r'<script type="application/ld\+json">(.*?)</script>',
                text, re.S):
            data = json.loads(blob)          # also asserts it parses
            queue = list(data.get("@graph") or [data])
            while queue:
                node = queue.pop()
                if not isinstance(node, dict):
                    continue
                out.append(node)
                main = node.get("mainEntity")
                if isinstance(main, dict):
                    queue.append(main)
        return out

    def test_every_block_is_valid_json(self):
        for page in self._pages():
            self._nodes(page)               # raises if any block is malformed

    def test_no_page_declares_an_entity_twice(self):
        for page in self._pages():
            for kind in ("Person", "Organization"):
                full = [n for n in self._nodes(page)
                        if n.get("@type") == kind and len(n) > 2]
                self.assertLessEqual(
                    len(full), 1,
                    f"{page.name}: {kind} دو بار کامل اعلام شده")

    def test_only_the_person_page_is_a_profile_page(self):
        for page in self._pages():
            profiles = [n for n in self._nodes(page)
                        if n.get("@type") == "ProfilePage"
                        and n.get("@id", "").rstrip("/") != ""
                        and "#" not in n.get("@id", "#")]
            if page.name == "hadi-bakhtzadeh.html":
                self.assertEqual(len(profiles), 1)
                self.assertEqual(profiles[0]["@id"], bc.PERSON_URL)
            else:
                self.assertFalse(
                    profiles,
                    f"{page.name}: ProfilePage دوم — کدام صفحه پروفایل است؟")

    def test_the_person_id_is_the_same_on_every_page(self):
        ids = set()
        for page in self._pages():
            for node in self._nodes(page):
                if node.get("@type") == "Person":
                    ids.add(node.get("@id"))
        self.assertEqual(ids, {bc.SITE + "/#person"})


class SitemapFreshness(unittest.TestCase):
    """Every URL carries a lastmod.

    changefreq and priority are hints a crawler is free to ignore; lastmod is
    the one it uses to decide whether a page is worth fetching again. Nine of
    eighteen URLs had none — including the four newest pages, which were
    published, listed, announced through IndexNow, and still giving a crawler
    no reason to return.
    """

    def _sitemap(self):
        return (pathlib.Path(bc.__file__).resolve().parent.parent
                / "sitemap.xml").read_text("utf-8")

    def test_it_is_valid_xml(self):
        import xml.etree.ElementTree as ET
        ET.fromstring(self._sitemap())

    def test_every_url_has_a_lastmod(self):
        xml = self._sitemap()
        self.assertEqual(xml.count("<loc>"), xml.count("<lastmod>"),
                         "آدرسی بدون lastmod در sitemap هست")

    def test_the_identity_pages_are_listed(self):
        xml = self._sitemap()
        for url in (bc.PERSON_URL, bc.PRODUCTS_URL, bc.RECORD_URL):
            self.assertIn(f"<loc>{url}</loc>", xml)


# WHY THIS SITS AT THE VERY BOTTOM
# --------------------------------
# It used to sit in the middle of the file. Python runs a module top to
# bottom, so unittest.main() fired before the classes below it had been
# defined and they were never collected — five whole classes, including the
# ones guarding the page contract, the single-entity rule and sitemap
# freshness. They passed by not existing. Nothing about the output said so:
# it printed OK, and a green run of a shrinking suite reads exactly like a
# green run of a growing one. Anything new goes above this line.
if __name__ == "__main__":
    unittest.main(verbosity=2)

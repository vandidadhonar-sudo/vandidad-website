#!/usr/bin/env python3
"""Tests for the publishing pipeline.

These cover the parts that only ever run unattended, on a schedule, with
nobody watching — where a mistake is discovered by its absence: an article
that quietly never published, or two pages competing for one phrase.

Run: python3 tools/test_pipeline.py
"""

from __future__ import annotations

import json
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
        self.assertIn('href="/about" rel="author"', self._render())

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

    def test_the_six_articles_written_before_the_rule_still_build(self):
        # Listed, not exempted quietly: each leaves LEGACY_SHORT by being
        # expanded. A test guards that the list is what lets them through.
        a = bc.Article(slug="chatbot-vs-digital-twin", collection="hamzad",
                       title="ت", description="د", published=date(2026, 8, 12),
                       body_md="کلمه " * 200 + "برای کسب‌وکار ایرانی یعنی چه",
                       summary_en="An English summary.")
        bc.validate(a)


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


if __name__ == "__main__":
    unittest.main(verbosity=2)

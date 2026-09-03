#!/usr/bin/env python3
"""Releases the next queued article, one per day, unattended.

WHY A QUEUE AND NOT A WRITING ROBOT
-----------------------------------
The ask was an article a day. The obvious way to get that is to have a model
write one every morning, and it is the wrong way: Google's spam policy of March
2024 names scaled content abuse — mass-produced pages made mainly to rank —
as grounds for action against a whole site, and the pages would be worth
reading to nobody anyway. So writing stays deliberate and only *release* is
automated. Articles are written, reviewed against the same gate as everything
else, and parked in content/queue/ with the date they should appear. This tool
moves the one that is due.

The effect the owner asked for is the same — a new article every morning
whether or not any laptop is switched on — because GitHub's runners do the
work, not anyone's machine.

WHAT IT DOES
------------
- picks the queued article whose publish_on has arrived, earliest first
- rewrites date/updated to today, drops publish_on, and moves it into its
  collection, where the renderer will find it
- prints how many days of queue remain, and warns when that is short

It moves exactly one article per run. A backlog that built up while something
was broken should not empty itself onto the site in one morning — six articles
appearing at 09:00 and none for a week is a pattern that looks automated,
which is the thing being avoided.
"""

from __future__ import annotations

import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
QUEUE = ROOT / "content" / "queue"
CONTENT = ROOT / "content"

FRONT = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.S)
LOW_RUNWAY = 3


def _field(front: str, name: str) -> str | None:
    m = re.search(rf"^{name}\s*:\s*(.+?)\s*$", front, re.M)
    return m.group(1).strip().strip("'\"") if m else None


def queued() -> list[tuple[date, Path, str]]:
    """Every queued article with a readable publish_on, earliest first.

    A file with no publish_on, or an unreadable one, is reported rather than
    silently skipped — a queued article that never publishes because of a typo
    in its date is exactly the failure this whole thing exists to prevent.
    """
    out, bad = [], []
    if not QUEUE.exists():
        return out
    for path in sorted(QUEUE.glob("*.md")):
        if path.name.endswith(".social.md"):
            continue
        m = FRONT.match(path.read_text(encoding="utf-8"))
        if not m:
            bad.append(f"{path.name}: no front matter")
            continue
        raw = _field(m.group(1), "publish_on")
        if not raw:
            bad.append(f"{path.name}: no publish_on line")
            continue
        try:
            out.append((date.fromisoformat(raw), path, m.group(1)))
        except ValueError:
            bad.append(f"{path.name}: publish_on «{raw}» is not YYYY-MM-DD")
    for b in bad:
        print(f"::warning::صف — {b}", file=sys.stderr)
    return sorted(out, key=lambda t: t[0])


def release(path: Path, front: str, today: date) -> Path:
    """Move one queued article into its collection, dated today."""
    collection = _field(front, "collection")
    if not collection:
        raise SystemExit(f"{path.name}: front matter has no collection line.")
    target_dir = CONTENT / collection
    if not target_dir.is_dir():
        raise SystemExit(
            f"{path.name}: collection «{collection}» has no folder at "
            f"content/{collection}/."
        )
    target = target_dir / path.name
    if target.exists():
        raise SystemExit(
            f"{target} already exists. Two articles cannot share a URL; "
            "rename the queued file."
        )

    text = path.read_text(encoding="utf-8")
    stamp = today.isoformat()
    # The publish date is the day it actually appeared, not the day it was
    # drafted — a reader and a crawler both take that date literally.
    text = re.sub(r"^date\s*:.*$", f"date: {stamp}", text, count=1, flags=re.M)
    text = re.sub(r"^updated\s*:.*$", f"updated: {stamp}", text, count=1, flags=re.M)
    text = re.sub(r"^publish_on\s*:.*\n", "", text, count=1, flags=re.M)

    target.write_text(text, encoding="utf-8")
    path.unlink()
    return target


def main() -> int:
    today = date.today()
    items = queued()
    due = [it for it in items if it[0] <= today]

    if not due:
        nxt = f"، بعدی {items[0][0].isoformat()}" if items else ""
        print(f"امروز چیزی برای انتشار نیست. در صف: {len(items)}{nxt}")
        if len(items) < LOW_RUNWAY:
            print(f"::warning::صف رو به اتمام است — فقط {len(items)} مقاله مانده.")
        return 0

    when, path, front = due[0]
    if when < today:
        print(f"::warning::{path.name} برای {when.isoformat()} بود و دیر منتشر می‌شود.")
    target = release(path, front, today)
    remaining = len(items) - 1
    print(f"منتشر شد: {target.relative_to(ROOT)} · {remaining} مقاله در صف مانده")
    if remaining < LOW_RUNWAY:
        print(f"::warning::صف رو به اتمام است — فقط {remaining} مقاله مانده.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

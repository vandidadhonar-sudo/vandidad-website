#!/usr/bin/env python3
"""Reads — and, when asked, turns off — Cloudflare's AI-crawler block.

WHY THIS EXISTS
---------------
tools/reachability.py found that Googlebot gets 200 on every path while
GPTBot and OAI-SearchBot get 403 on every path except robots.txt. That is
the entire reason a model searching the live web found nothing about this
site: OpenAI's crawler has never reached it.

robots.txt names those crawlers and allows them, and robots.txt is the one
file that answers — Cloudflare lets it through so a crawler can read the
rules it is then blocked from following. Permission in a file and a door
that opens are different things.

Cloudflare exposes this as a zone setting, `ai_bots_protection`, so it can
be read and changed without anyone clicking through a dashboard. Doing it
here rather than by instruction means the change is recorded, repeatable,
and verifiable by the same check that found the problem.

WHAT IT PRINTS AND WHAT IT NEVER PRINTS
---------------------------------------
It prints settings. It never prints the token, and never echoes a response
field that could carry one. A failed call reports the status and Cloudflare's
own error message, which is the difference between "the token cannot do this"
and "the setting is not what we thought" — two answers that need two
different next steps.

WHY IT ALSO LISTS THE FIREWALL RULES
------------------------------------
`ai_bots_protection` is the likely cause but not the only possible one: a
custom WAF rule can produce exactly the same 403. Listing the custom rules
means a run either finds the switch or shows what else is there, instead of
turning one thing off and declaring victory on a site that is still closed.

Run:  python3 tools/cloudflare_ai_bots.py            # read only
      python3 tools/cloudflare_ai_bots.py --apply    # unblock, then re-read
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

API = "https://api.cloudflare.com/client/v4"
ZONE_NAME = "vandidad.xyz"


def call(method: str, path: str, body: dict | None = None) -> tuple[int, dict]:
    token = os.environ.get("CLOUDFLARE_API_TOKEN", "")
    if not token:
        print("CLOUDFLARE_API_TOKEN تنظیم نشده", file=sys.stderr)
        sys.exit(2)
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        API + path, data=data, method=method,
        headers={"Authorization": f"Bearer {token}",
                 "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode())
        except Exception:
            return e.code, {}
    except Exception as e:
        return 0, {"errors": [{"message": f"{type(e).__name__}: {e}"}]}


def errors(payload: dict) -> str:
    return "؛ ".join(
        str(er.get("message", er)) for er in payload.get("errors", [])
    ) or "بدون پیام"


def main() -> int:
    apply = "--apply" in sys.argv

    status, payload = call("GET", f"/zones?name={ZONE_NAME}")
    zones = payload.get("result") or []
    if status != 200 or not zones:
        print(f"✗ زون پیدا نشد ({status}): {errors(payload)}")
        return 1
    zone = zones[0]["id"]
    print(f"زون: {ZONE_NAME}  (پلن: {zones[0].get('plan', {}).get('name', '؟')})\n")

    status, payload = call("GET", f"/zones/{zone}/bot_management")
    if status != 200:
        print(f"✗ خواندن تنظیماتِ ربات‌ها ناموفق ({status}): {errors(payload)}")
        print("\nاین یعنی توکنِ این مخزن اجازهٔ این بخش را ندارد. توکن برای")
        print("انتشار ورکر ساخته شده؛ تغییر باید از داشبورد انجام شود.")
        return 1

    current = payload.get("result", {})
    print("تنظیمات فعلی ربات‌ها:")
    for key in ("ai_bots_protection", "crawler_protection", "fight_mode",
                "enable_js", "sbfm_definitely_automated"):
        if key in current:
            print(f"  {key}: {current[key]}")

    blocking = current.get("ai_bots_protection") == "block"
    print(f"\nمسدودسازی خزنده‌های هوش مصنوعی: "
          f"{'روشن — همین مقصر است' if blocking else 'خاموش'}")

    # A custom WAF rule can 403 exactly the same way, so a clean
    # ai_bots_protection is not on its own proof that nothing else blocks.
    status, payload = call(
        "GET", f"/zones/{zone}/rulesets/phases/http_request_firewall_custom/entrypoint")
    if status == 200:
        rules = payload.get("result", {}).get("rules") or []
        if rules:
            print("\nقواعد دستیِ فایروال:")
            for r in rules:
                print(f"  - {r.get('description', '(بی‌نام)')}: "
                      f"{r.get('action')}  [{'فعال' if r.get('enabled') else 'غیرفعال'}]")
        else:
            print("\nقاعدهٔ دستیِ فایروال: ندارد")

    if not apply:
        if blocking:
            print("\nبرای خاموش کردن: python3 tools/cloudflare_ai_bots.py --apply")
        return 0

    if not blocking:
        print("\nچیزی برای خاموش کردن نیست.")
        return 0

    print("\nخاموش کردن…")
    status, payload = call("PUT", f"/zones/{zone}/bot_management",
                           {"ai_bots_protection": "disabled"})
    if status != 200 or not payload.get("success"):
        print(f"✗ تغییر ناموفق ({status}): {errors(payload)}")
        return 1

    # Read it back rather than trusting the write's own answer.
    status, payload = call("GET", f"/zones/{zone}/bot_management")
    now = payload.get("result", {}).get("ai_bots_protection")
    print(f"مقدار پس از تغییر: {now}")
    if now == "block":
        print("✗ هنوز روشن است.")
        return 1
    print("✓ خاموش شد. حالا tools/reachability.py باید سبز شود.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

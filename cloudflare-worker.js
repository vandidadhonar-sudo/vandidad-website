/**
 * vandidad.xyz — Cloudflare Worker
 * Vandidad Group | م.هادی بخت‌زاده
 *
 * The site is served straight from this repository's `main` branch: the Worker
 * fetches the HTML from raw.githubusercontent on demand and caches it briefly.
 * Merging to main IS the deployment — there is no build step.
 *
 * STATIC PAGES ARE DATA, NOT CODE
 * -------------------------------
 * Previously every new page (`/about`) meant editing this Worker and pasting it
 * back into the Cloudflare dashboard by hand — and because the dashboard copy
 * drifted ahead of the repository, the file here stopped being the truth.
 * Now a page is one entry in PAGES below, and any file listed there is served
 * from the repo. Adding /privacy, /terms or anything later needs a commit and
 * nothing else.
 *
 * CACHING
 * -------
 * HTML: 60 seconds at the edge and in the browser, so a merge is live within a
 * minute without hammering GitHub. Media: one year, immutable.
 */

const RAW = "https://raw.githubusercontent.com/vandidadhonar-sudo/vandidad-website/main";
const INDEX_URL = RAW + "/index.html";

// Route → file in the repository. One line per page, forever.
const PAGES = {
  "/about": "/about.html",
  "/privacy": "/privacy.html",
  "/terms": "/terms.html",
  "/data-deletion": "/data-deletion.html",
};

const MEDIA = { "/hero.mp4": "video/mp4", "/hero-poster.jpg": "image/jpeg" };

const HTML_HEADERS = {
  "Content-Type": "text/html; charset=utf-8",
  "Cache-Control": "public, max-age=60",
  "X-Frame-Options": "DENY",
};

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);

    if (url.hostname.startsWith("www.")) {
      return Response.redirect(
        url.protocol + "//" + url.hostname.slice(4) + url.pathname + url.search,
        301
      );
    }

    if (url.pathname === "/__alive") {
      return new Response("ok", { headers: { "Content-Type": "text/plain" } });
    }

    if (MEDIA[url.pathname]) {
      const cache = caches.default;
      let res = await cache.match(request);
      if (!res) {
        const up = await fetch(RAW + url.pathname, {
          cf: { cacheTtl: 86400, cacheEverything: true },
        });
        res = new Response(up.body, {
          status: up.status,
          headers: {
            "Content-Type": MEDIA[url.pathname],
            "Cache-Control": "public, max-age=31536000, immutable",
            "Accept-Ranges": "bytes",
          },
        });
        ctx.waitUntil(cache.put(request, res.clone()));
      }
      return res;
    }

    // Static pages — trailing slash tolerated, so /privacy/ works too.
    const clean = url.pathname.replace(/\/+$/, "") || "/";
    if (PAGES[clean]) {
      const up = await fetch(RAW + PAGES[clean], {
        cf: { cacheTtl: 60, cacheEverything: true },
        headers: { Accept: "text/html" },
      });
      if (up.ok) {
        return new Response(up.body, { status: 200, headers: HTML_HEADERS });
      }
      // A page listed but missing from the repo is a 404, never a silent
      // fallback to the homepage — Meta's review follows these URLs literally.
      return new Response("Not found", { status: 404 });
    }

    // Everything else is the single-page app.
    const country =
      (request.cf && request.cf.country) || request.headers.get("CF-IPCountry") || "";
    const finalize = (html) => {
      if (country && html.indexOf("</head>") !== -1) {
        html = html.replace(
          "</head>",
          "<script>window.__CF_COUNTRY__=" + JSON.stringify(country) + ";</script></head>"
        );
      }
      return new Response(html, { headers: HTML_HEADERS });
    };

    const cache = caches.default;
    const cacheKey = new Request(new URL("/__indexcache", url).toString(), request);
    const cached = await cache.match(cacheKey);
    if (cached) return finalize(await cached.text());

    try {
      const upstream = await fetch(INDEX_URL, {
        cf: { cacheTtl: 60, cacheEverything: true },
        headers: { Accept: "text/html" },
      });
      if (upstream.ok) {
        const html = await upstream.text();
        ctx.waitUntil(
          cache.put(cacheKey, new Response(html, { headers: HTML_HEADERS }))
        );
        return finalize(html);
      }
    } catch (e) {
      /* fall through to the holding page */
    }

    return new Response(
      "<!DOCTYPE html><meta charset='utf-8'><body style='background:#050C08;color:#BFA05C;" +
        "font-family:Tahoma;text-align:center;padding-top:20vh'>در حال بارگذاری… لطفاً چند لحظه بعد دوباره تلاش کنید.</body>",
      { status: 503, headers: { "Content-Type": "text/html; charset=utf-8", "Retry-After": "5" } }
    );
  },
};

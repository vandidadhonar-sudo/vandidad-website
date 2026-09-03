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
 * MEDIA COMES FROM R2, NOT FROM GITHUB
 * ------------------------------------
 * The hero video is 2.7 MB and plays on every first visit. Two reasons it does
 * not belong on the raw-GitHub path any more: raw.githubusercontent is a source
 * host, not a CDN, and Cloudflare's own agreement (§2.8) limits serving
 * disproportionate non-HTML content through the plan's CDN — with content
 * stored in R2 called out as the supported way to do it.
 *
 * The R2 bucket is reached through the `MEDIA` binding, and the objects are put
 * there by the same GitHub Action that deploys this file. If the binding is
 * missing, or an object has not been uploaded yet, this falls back to the old
 * GitHub path — so the code can be deployed before the upload, or the upload
 * done before the deploy, in either order, without a moment where the video is
 * broken.
 *
 * Unlike the old path, R2 honours Range requests, so a viewer can seek in the
 * video and iOS Safari gets the 206 it insists on before it will play at all.
 *
 * ARTICLES
 * --------
 * /blog/<slug> and /hamzad/<slug> are served from content/ in the repository,
 * so publishing an article is a commit and nothing else. The slug is checked
 * against a strict pattern before it is put in a URL: without that, a crafted
 * path could walk out of the content directory and serve any file in the repo.
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

// Files that crawlers and language models look for by exact name. They are not
// HTML, so they get their own content types rather than the HTML headers.
const FILES = {
  "/robots.txt": "text/plain; charset=utf-8",
  "/llms.txt": "text/plain; charset=utf-8",
  "/sitemap.xml": "application/xml; charset=utf-8",
  "/feed.xml": "application/atom+xml; charset=utf-8",
  // IndexNow proves we own the domain by serving this key back at its own
  // name. It is a public verification file, not a secret. Without it the
  // instant-indexing pings are rejected and new articles wait weeks for a
  // crawler instead of hours — which matters because ChatGPT's live search
  // reads Bing, and Bing is what IndexNow notifies.
  "/e1f25c1e9599de7ac40a9f13dd647f7c7fa1f352213a90ca3c667c623d1f933e.txt":
    "text/plain; charset=utf-8",
};

// Article collections. /blog/a-slug is content/blog/a-slug.html in the repo,
// and /blog on its own is that folder's index.
const COLLECTIONS = { blog: "/content/blog", hamzad: "/content/hamzad" };

// Lowercase letters, digits and single hyphens. Anything else — a dot, a
// slash, an encoded one — is not a slug and never reaches a fetch.
const SLUG = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;

// Route → object key in the R2 bucket, and the type to serve it as. The key is
// the path without its leading slash, so the bucket mirrors the URL space.
const MEDIA = { "/hero.mp4": "video/mp4", "/hero-poster.jpg": "image/jpeg" };

const MEDIA_HEADERS = {
  "Cache-Control": "public, max-age=31536000, immutable",
  "Accept-Ranges": "bytes",
};

const HTML_HEADERS = {
  "Content-Type": "text/html; charset=utf-8",
  "Cache-Control": "public, max-age=60",
  "X-Frame-Options": "DENY",
  // A browser that sniffs a served type can be talked into treating a page as
  // something it is not; nosniff closes that. The referrer policy keeps the
  // full path of a private case-file page out of the Referer header when a
  // reader clicks an outbound link.
  "X-Content-Type-Options": "nosniff",
  "Referrer-Policy": "strict-origin-when-cross-origin",
};

// Serve an object out of R2. Returns null — never throws — when R2 cannot
// answer, which is the caller's signal to fall back to the GitHub origin.
async function fromR2(bucket, key, contentType, request) {
  if (!bucket) return null;

  let object;
  try {
    object = await bucket.get(key, {
      range: request.headers,
      onlyIf: request.headers,
    });
  } catch (e) {
    return null;
  }
  if (!object) return null;

  const headers = new Headers(MEDIA_HEADERS);
  object.writeHttpMetadata(headers);
  headers.set("Content-Type", contentType); // ours wins over whatever was uploaded
  headers.set("ETag", object.httpEtag);

  // onlyIf matched, so R2 returned metadata without a body: the browser already
  // holds this exact object.
  if (!object.body) return new Response(null, { status: 304, headers });

  const r = object.range;
  if (request.headers.get("Range") && r) {
    const start = r.offset !== undefined ? r.offset : object.size - r.suffix;
    const length = r.length !== undefined ? r.length : object.size - start;
    headers.set("Content-Range", `bytes ${start}-${start + length - 1}/${object.size}`);
    headers.set("Content-Length", String(length));
    return new Response(object.body, { status: 206, headers });
  }

  headers.set("Content-Length", String(object.size));
  return new Response(object.body, { status: 200, headers });
}

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

    // Search Console and Bing verify ownership by asking for a file back at a
    // name they choose, so the name cannot be known in advance and cannot live
    // in FILES. The two patterns below are exactly what those two services
    // issue — a strict shape, so this cannot be used to fetch anything else out
    // of the repository. Drop the file the service gives you in the repo root
    // and verification is a commit, with no DNS change and no dashboard paste.
    const VERIFY = /^\/(google[0-9a-f]{16}\.html|BingSiteAuth\.xml|yandex_[0-9a-f]{16}\.html)$/;
    if (VERIFY.test(url.pathname)) {
      const up = await fetch(RAW + url.pathname, {
        cf: { cacheTtl: 300, cacheEverything: true },
      });
      if (!up.ok) return new Response("Not found", { status: 404 });
      return new Response(up.body, {
        status: 200,
        headers: {
          "Content-Type": url.pathname.endsWith(".xml")
            ? "application/xml; charset=utf-8"
            : "text/html; charset=utf-8",
          "Cache-Control": "public, max-age=300",
          "X-Content-Type-Options": "nosniff",
        },
      });
    }

    if (FILES[url.pathname]) {
      const up = await fetch(RAW + url.pathname, {
        cf: { cacheTtl: 300, cacheEverything: true },
      });
      if (!up.ok) return new Response("Not found", { status: 404 });
      return new Response(up.body, {
        status: 200,
        headers: {
          "Content-Type": FILES[url.pathname],
          "Cache-Control": "public, max-age=300",
          "X-Content-Type-Options": "nosniff",
        },
      });
    }

    if (MEDIA[url.pathname]) {
      const type = MEDIA[url.pathname];
      const key = url.pathname.slice(1);

      const served = await fromR2(env && env.MEDIA, key, type, request);
      if (served) return served;

      // R2 has nothing for this key yet — the old GitHub path, unchanged. Range
      // requests are not answered here, so this stays a plain 200.
      const cache = caches.default;
      let res = await cache.match(request);
      if (!res) {
        const up = await fetch(RAW + url.pathname, {
          cf: { cacheTtl: 86400, cacheEverything: true },
        });
        res = new Response(up.body, {
          status: up.status,
          headers: { ...MEDIA_HEADERS, "Content-Type": type },
        });
        if (up.ok) ctx.waitUntil(cache.put(request, res.clone()));
      }
      return res;
    }

    // Static pages and articles — trailing slash tolerated, so /privacy/ works.
    const clean = url.pathname.replace(/\/+$/, "") || "/";

    let file = PAGES[clean];
    if (!file) {
      // /blog, /blog/a-slug, /hamzad, /hamzad/a-slug — and nothing deeper.
      const parts = clean.split("/"); // ["", "blog", "a-slug"]
      const dir = COLLECTIONS[parts[1]];
      if (dir && parts.length === 2) file = dir + "/index.html";
      else if (dir && parts.length === 3 && SLUG.test(parts[2])) {
        file = dir + "/" + parts[2] + ".html";
      }
    }

    if (file) {
      const up = await fetch(RAW + file, {
        cf: { cacheTtl: 60, cacheEverything: true },
        headers: { Accept: "text/html" },
      });
      if (up.ok) {
        return new Response(up.body, { status: 200, headers: HTML_HEADERS });
      }
      // A page that is routed but missing from the repo is a 404, never a
      // silent fallback to the homepage — Meta's review follows these URLs
      // literally, and a search engine told 200 would index the wrong page.
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

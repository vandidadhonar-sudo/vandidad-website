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
 * The R2 bucket is reached through the `MEDIA` binding. If that binding is
 * missing, or the object has not been uploaded yet, this falls back to the old
 * GitHub path — so the code can be deployed before the upload, or the upload
 * done before the deploy, in either order, without a moment where the video is
 * broken.
 *
 * Unlike the old path, R2 honours Range requests, so a viewer can seek in the
 * video and iOS Safari gets the 206 it insists on before it will play at all.
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

    // Copies the files in MEDIA from the repository into the R2 bucket, so the
    // owner never has to download a video and drag it into a dashboard: commit
    // a new hero.mp4, open this once, done.
    //
    // Closed by default. It does nothing at all unless MEDIA_SEED_KEY is set as
    // a Worker variable, and even then it only ever reads from this repository
    // and only ever writes the two keys named in MEDIA — there is no path here
    // that lets a caller choose what gets written or where it comes from.
    if (url.pathname === "/__seed-media") {
      const secret = env && env.MEDIA_SEED_KEY;
      if (!secret || url.searchParams.get("key") !== secret) {
        return new Response("Not found", { status: 404 });
      }
      if (!env.MEDIA) {
        return new Response("no R2 binding named MEDIA on this Worker\n", { status: 500 });
      }
      const report = [];
      for (const path of Object.keys(MEDIA)) {
        const up = await fetch(RAW + path, { cf: { cacheEverything: false } });
        if (!up.ok) {
          report.push(`${path} — FAILED, repository answered ${up.status}`);
          continue;
        }
        await env.MEDIA.put(path.slice(1), up.body, {
          httpMetadata: { contentType: MEDIA[path] },
        });
        report.push(`${path} — stored (${up.headers.get("Content-Length") || "?"} bytes)`);
      }
      return new Response(report.join("\n") + "\n", {
        headers: { "Content-Type": "text/plain; charset=utf-8" },
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

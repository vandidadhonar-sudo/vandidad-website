const INDEX_URL = "https://raw.githubusercontent.com/vandidadhonar-sudo/vandidad-website/main/index.html";

// Map the visitor's country (Cloudflare CF-IPCountry — free on every plan) into
// the page so the frontend can use it as a zero-cost language fallback. The base
// HTML is cached WITHOUT the country; the per-request country is injected after
// cache retrieval, so one visitor's country is never cached for everyone.
export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);

    if (url.pathname === "/__alive") {
      return new Response("ok", { headers: { "Content-Type": "text/plain" } });
    }

    const country =
      (request.cf && request.cf.country) ||
      request.headers.get("CF-IPCountry") ||
      "";

    const finalize = (html) => {
      if (country && html.indexOf("</head>") !== -1) {
        html = html.replace(
          "</head>",
          "<script>window.__CF_COUNTRY__=" + JSON.stringify(country) + ";</script></head>"
        );
      }
      return new Response(html, {
        headers: {
          "Content-Type": "text/html; charset=utf-8",
          "Cache-Control": "public, max-age=60",
          "X-Frame-Options": "DENY"
        }
      });
    };

    const cache = caches.default;
    const cacheKey = new Request(new URL("/__indexcache", url).toString(), request);

    const cached = await cache.match(cacheKey);
    if (cached) return finalize(await cached.text());

    try {
      const upstream = await fetch(INDEX_URL, {
        cf: { cacheTtl: 60, cacheEverything: true },
        headers: { "Accept": "text/html" }
      });
      if (upstream.ok) {
        const html = await upstream.text();
        // Cache the BASE html (country-free) so all visitors share one cache entry.
        const base = new Response(html, {
          headers: { "Content-Type": "text/html; charset=utf-8", "Cache-Control": "public, max-age=60" }
        });
        ctx.waitUntil(cache.put(cacheKey, base.clone()));
        return finalize(html);
      }
    } catch (e) {}

    return new Response(
      "<!DOCTYPE html><meta charset='utf-8'><body style='background:#0A1220;color:#D69A66;font-family:Tahoma;text-align:center;padding-top:20vh'>در حال بارگذاری… لطفاً چند لحظه بعد دوباره تلاش کنید.</body>",
      { status: 503, headers: { "Content-Type": "text/html; charset=utf-8", "Retry-After": "5" } }
    );
  }
};

const INDEX_URL = "https://raw.githubusercontent.com/vandidadhonar-sudo/vandidad-website/main/index.html";

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);

    if (url.pathname === "/__alive") {
      return new Response("ok", { headers: { "Content-Type": "text/plain" } });
    }

    const cache = caches.default;
    const cacheKey = new Request(new URL("/__indexcache", url).toString(), request);

    let cached = await cache.match(cacheKey);
    if (cached) return withHeaders(cached);

    try {
      const upstream = await fetch(INDEX_URL, {
        cf: { cacheTtl: 60, cacheEverything: true },
        headers: { "Accept": "text/html" }
      });
      if (upstream.ok) {
        const html = await upstream.text();
        const resp = new Response(html, {
          headers: {
            "Content-Type": "text/html; charset=utf-8",
            "Cache-Control": "public, max-age=60",
            "X-Frame-Options": "DENY"
          }
        });
        ctx.waitUntil(cache.put(cacheKey, resp.clone()));
        return withHeaders(resp);
      }
    } catch (e) {}

    return new Response(
      "<!DOCTYPE html><meta charset='utf-8'><body style='background:#0A1220;color:#D69A66;font-family:Tahoma;text-align:center;padding-top:20vh'>در حال بارگذاری… لطفاً چند لحظه بعد دوباره تلاش کنید.</body>",
      { status: 503, headers: { "Content-Type": "text/html; charset=utf-8", "Retry-After": "5" } }
    );
  }
};

function withHeaders(resp) {
  const r = new Response(resp.body, resp);
  r.headers.set("X-Frame-Options", "DENY");
  r.headers.set("Content-Type", "text/html; charset=utf-8");
  return r;
}

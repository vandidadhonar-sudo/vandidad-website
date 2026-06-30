// Cloudflare Pages middleware — runs before every request.
// Unifies the domain on the apex (non-www) so www and non-www are never split,
// and adds light security headers. The chat POST proxy (index.js) still runs
// for apex requests via context.next().
export async function onRequest(context) {
  const url = new URL(context.request.url);

  // www.vandidad.xyz  →  vandidad.xyz  (single canonical domain, 301 permanent).
  if (url.hostname.toLowerCase().startsWith("www.")) {
    url.hostname = url.hostname.replace(/^www\./i, "");
    return Response.redirect(url.toString(), 301);
  }

  const resp = await context.next();
  try {
    const h = new Headers(resp.headers);
    h.set("X-Content-Type-Options", "nosniff");
    h.set("Referrer-Policy", "strict-origin-when-cross-origin");
    h.set("Strict-Transport-Security", "max-age=31536000; includeSubDomains");
    return new Response(resp.body, { status: resp.status, statusText: resp.statusText, headers: h });
  } catch (e) {
    return resp;
  }
}

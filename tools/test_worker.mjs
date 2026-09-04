/**
 * Exercises the Worker's routing without deploying it.
 *
 * WHY THIS EXISTS
 * ---------------
 * The Worker is the whole site: a mistake in it does not degrade a page, it
 * takes the domain down. Until now the only check before a deploy was
 * `wrangler --dry-run`, which proves the file parses and nothing more — a
 * route that returns the wrong thing parses perfectly. So the routing is
 * exercised here against stubs, and a wrong answer is caught on a laptop
 * rather than by a visitor.
 *
 * The stubs are deliberately dumb: fetch reports the URL it was asked for,
 * and the bucket is a Map. What is being tested is which URL the Worker
 * decides to ask for and what it decides to answer — not Cloudflare.
 *
 * Run: node tools/test_worker.mjs
 */

import worker from "../cloudflare-worker.js";

let failures = 0;
function check(name, condition, detail = "") {
  if (condition) {
    console.log(`  ok   ${name}`);
  } else {
    failures++;
    console.log(`  FAIL ${name}${detail ? " — " + detail : ""}`);
  }
}

// --- stubs ------------------------------------------------------------

const asked = [];
globalThis.fetch = async (url) => {
  asked.push(String(url));
  // A path that would 404 upstream, so the "routed but missing" branch is
  // reachable in a test.
  if (String(url).includes("does-not-exist")) {
    return new Response("no", { status: 404 });
  }
  return new Response(`body-of:${url}`, { status: 200 });
};

globalThis.caches = {
  default: { match: async () => undefined, put: async () => {} },
};

const ctx = { waitUntil: () => {} };

function bucket(keys) {
  return {
    get: async (key) =>
      keys.has(key)
        ? {
            body: `r2-body:${key}`,
            size: 1234,
            httpEtag: '"abc"',
            range: undefined,
            writeHttpMetadata: () => {},
          }
        : null,
  };
}

const req = (path, init) => new Request("https://vandidad.xyz" + path, init);
const call = (path, env = {}, init) =>
  worker.fetch(req(path, init), env, ctx);

// --- the routes that matter -------------------------------------------

console.log("\nfonts");
{
  const env = { MEDIA: bucket(new Set(["fonts/vazirmatn-regular.woff2"])) };
  const r = await call("/fonts/vazirmatn-regular.woff2", env);
  check("served from R2 with the right type",
    r.status === 200 && r.headers.get("Content-Type") === "font/woff2",
    `${r.status} ${r.headers.get("Content-Type")}`);
  check("cached for a year, immutable",
    (r.headers.get("Cache-Control") || "").includes("immutable"),
    r.headers.get("Cache-Control"));

  asked.length = 0;
  const r2 = await call("/fonts/vazirmatn-bold.woff2", { MEDIA: bucket(new Set()) });
  check("falls back to GitHub when the bucket has no object yet",
    r2.status === 200 && asked.some(u => u.endsWith("/fonts/vazirmatn-bold.woff2")),
    asked.join(", "));

  const r3 = await call("/fonts/vazirmatn-regular.woff2", {});
  check("survives a missing R2 binding", r3.status === 200, String(r3.status));
}

console.log("\nthe hero video still behaves");
{
  const env = { MEDIA: bucket(new Set(["hero.mp4"])) };
  const r = await call("/hero.mp4", env);
  check("served from R2 as video/mp4",
    r.status === 200 && r.headers.get("Content-Type") === "video/mp4",
    `${r.status} ${r.headers.get("Content-Type")}`);
  const p = await call("/hero-poster.jpg", { MEDIA: bucket(new Set(["hero-poster.jpg"])) });
  check("poster served as image/jpeg",
    p.headers.get("Content-Type") === "image/jpeg");
}

console.log("\narticles");
{
  asked.length = 0;
  const r = await call("/hamzad/some-slug");
  check("a good slug is fetched from content/hamzad",
    r.status === 200 && asked.some(u => u.endsWith("/content/hamzad/some-slug.html")),
    asked.join(", "));

  // The property that matters is what the Worker asks the origin for, not
  // what status it returns. An earlier version of this test asserted 404 and
  // failed; the traversal is in fact refused — the slug pattern rejects it and
  // the request never becomes a file fetch — after which the path falls
  // through to the single-page app like any other unrecognised URL. That is
  // the design, so the test now checks the refusal rather than the status.
  asked.length = 0;
  const bad = await call("/hamzad/..%2F..%2Fwrangler.toml");
  check("a path that tries to climb out never becomes a file fetch",
    !asked.some(u => u.includes("wrangler") || u.includes("..")),
    asked.join(", "));
  check("...and it falls through to the app, which is the catch-all",
    bad.status === 200 && asked.some(u => u.endsWith("/index.html")),
    `${bad.status} ${asked.join(", ")}`);

  asked.length = 0;
  const dotted = await call("/hamzad/some.file");
  check("a slug with a dot is not routed to a file either",
    !asked.some(u => u.includes("some.file")), asked.join(", "));

  const deep = await call("/hamzad/a/b");
  check("nothing deeper than one slug is routed as an article",
    deep.status !== 200 || !asked.some(u => u.includes("/a/b")));

  const missing = await call("/hamzad/does-not-exist");
  check("a routed but missing article is a 404, never the homepage",
    missing.status === 404, String(missing.status));
}

console.log("\nthe rest");
{
  const alive = await call("/__alive");
  check("health check answers", alive.status === 200);

  const robots = await call("/robots.txt");
  check("robots.txt is served as text/plain",
    (robots.headers.get("Content-Type") || "").startsWith("text/plain"));

  const home = await call("/");
  check("the homepage is served", home.status === 200);

  const priv = await call("/privacy/");
  check("a trailing slash still finds the page", priv.status === 200);
}

console.log(
  failures ? `\n${failures} FAILED\n` : "\nall worker routes behave\n");
process.exit(failures ? 1 : 0);

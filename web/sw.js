/* Kvale service worker (chunk 7): makes the app work offline after one visit.

   tools/build_site.py fills in the three values below when it builds _site/:
   VERSION (a hash of the site files, so every deploy installs a new worker),
   PRECACHE (every site file) and CDN_CACHE (named after the PyScript release).

   - Site files are cached when the worker installs, in a cache per VERSION.
   - Files from other servers (PyScript, Pyodide and its packages such as
     Pillow, the fonts) are kept in CDN_CACHE the first time they are fetched.
     Their URLs carry a version, so they never go stale. The page also sends
     the files it loaded before this worker took over ("warm"), and the worker
     fetches Pillow ahead of time so "Save image" works offline too.
   - A new worker waits until the page asks it to take over (the "new version"
     toast in pwa.js), so a deploy never swaps files under a running app. */

const VERSION = "__KVALE_VERSION__";
const PRECACHE = __KVALE_PRECACHE__;
const CDN_CACHE = "__KVALE_CDN_CACHE__";
const SITE_CACHE = "kvale-site-" + VERSION;
// Pyodide packages fetched ahead of time (with what they depend on).
const PREFETCH_PACKAGES = ["pillow"];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(SITE_CACHE).then((cache) =>
      cache.addAll(PRECACHE.map((path) => new Request(path, { cache: "reload" })))
    )
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys()
      .then((names) => Promise.all(
        names
          .filter((name) => name.startsWith("kvale-") && name !== SITE_CACHE && name !== CDN_CACHE)
          .map((name) => caches.delete(name))
      ))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("message", (event) => {
  const data = event.data || {};
  if (data.type === "skip-waiting") {
    self.skipWaiting();
  } else if (data.type === "version") {
    reply(event, { version: VERSION });
  } else if (data.type === "warm") {
    event.waitUntil(warm(data.urls || []).then((count) => reply(event, { cached: count })));
  }
});

function reply(event, message) {
  if (event.ports && event.ports[0]) event.ports[0].postMessage(message);
}

self.addEventListener("fetch", (event) => {
  const request = event.request;
  if (request.method !== "GET") return;
  const url = new URL(request.url);
  if (!url.protocol.startsWith("http")) return;
  if (url.origin === self.location.origin) {
    event.respondWith(fromSite(request));
  } else {
    event.respondWith(fromCdn(request));
  }
});

async function fromSite(request) {
  const cache = await caches.open(SITE_CACHE);
  const navigate = request.mode === "navigate";
  let cached = await cache.match(request, { ignoreSearch: navigate, ignoreVary: true });
  if (!cached && navigate && new URL(request.url).pathname === new URL(self.registration.scope).pathname) {
    cached = await cache.match("index.html");
  }
  if (cached) return cached;
  return fetch(request);
}

async function fromCdn(request) {
  const cache = await caches.open(CDN_CACHE);
  const cached = await cache.match(request, { ignoreVary: true });
  if (cached) return cached;
  const response = await fetch(request);
  if (response.ok || response.type === "opaque") {
    cache.put(request, response.clone()).catch(() => {});
  }
  return response;
}

/* Cache files from other servers that the page loaded before this worker
   controlled it, plus PREFETCH_PACKAGES. Returns how many are cached. */
async function warm(urls) {
  const cache = await caches.open(CDN_CACHE);
  const wanted = new Set(urls.filter((url) => {
    try { return new URL(url).origin !== self.location.origin && url.startsWith("http"); } catch (e) { return false; }
  }));
  const lock = [...wanted].find((url) => new URL(url).pathname.endsWith("/pyodide-lock.json"));
  if (lock) {
    for (const url of await packageUrls(lock, cache)) wanted.add(url);
  }
  for (const url of [...wanted].filter((url) => new URL(url).hostname === "fonts.googleapis.com")) {
    for (const font of await fontUrls(url)) wanted.add(font);
  }
  let count = 0;
  await Promise.all([...wanted].map(async (url) => {
    if (await cache.match(url, { ignoreVary: true })) { count += 1; return; }
    try {
      let response;
      try {
        response = await fetch(url, { mode: "cors", credentials: "omit" });
      } catch (error) {
        response = await fetch(url, { mode: "no-cors" });  // e.g. a font CSS without CORS headers
      }
      if (response.ok || response.type === "opaque") {
        await cache.put(url, response);
        count += 1;
      }
    } catch (error) {
      // Offline or gone: it will be cached the next time the page fetches it.
    }
  }));
  return count;
}

/* The wheel URLs of PREFETCH_PACKAGES and their dependencies, from Pyodide's lock file. */
async function packageUrls(lockUrl, cache) {
  try {
    const response = (await cache.match(lockUrl, { ignoreVary: true })) || (await fetch(lockUrl));
    const lock = await response.clone().json();
    const packages = lock.packages || {};
    const base = lockUrl.slice(0, lockUrl.lastIndexOf("/") + 1);
    const found = new Set();
    const visit = (name) => {
      const info = packages[name];
      if (!info || found.has(name)) return;
      found.add(name);
      (info.depends || []).forEach(visit);
    };
    PREFETCH_PACKAGES.forEach(visit);
    return [...found].map((name) => new URL(packages[name].file_name, base).href);
  } catch (error) {
    return [];
  }
}

/* The Latin font files a Google Fonts style sheet points to (the page does not
   list them among its resources). Each block starts with a comment naming its
   character subset; nb, en and it need only "latin" and "latin-ext". */
async function fontUrls(cssUrl) {
  try {
    const response = await fetch(cssUrl, { mode: "cors", credentials: "omit" });
    const css = await response.text();
    const urls = [];
    for (const block of css.split("/*").slice(1)) {
      const subset = block.slice(0, block.indexOf("*/")).trim();
      if (subset !== "latin" && subset !== "latin-ext") continue;
      for (const match of block.matchAll(/url\((["']?)(https:[^)"']+)\1\)/g)) urls.push(match[2]);
    }
    return urls;
  } catch (error) {
    return [];
  }
}

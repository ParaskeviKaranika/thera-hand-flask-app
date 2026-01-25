/* ===============================
   TheraHand – Service Worker
   =============================== */

const CACHE_VERSION = "therahand-v2";
const STATIC_CACHE = `${CACHE_VERSION}-static`;

// 🔒 App Shell – σελίδες & assets που θες πάντα offline
const APP_SHELL = [
  "/",                // welcome
  "/menu",
  "/today",
  "/dashboard",

  // CSS
  "/static/menu-style.css",
  "/static/dashboard.css",

  // JS
  "/static/theme.js",
  "/static/chatbot.js",

  // Icons / images
  "/static/menu_images/planning.png",
  "/static/menu_images/statistic.png",
  "/static/menu_images/games.png",
  "/static/icons/icon-192.png",
  "/static/icons/icon-512.png"
];

/* ============ INSTALL ============ */
self.addEventListener("install", (event) => {
  console.log("🟢 TheraHand SW installing");

  event.waitUntil(
    caches.open(STATIC_CACHE).then((cache) => {
      return cache.addAll(APP_SHELL);
    })
  );

  self.skipWaiting();
});

/* ============ ACTIVATE ============ */
self.addEventListener("activate", (event) => {
  console.log("🟢 TheraHand SW activating");

  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys
          .filter((key) => !key.startsWith(CACHE_VERSION))
          .map((key) => caches.delete(key))
      )
    )
  );

  self.clients.claim();
});

/* ============ FETCH ============ */
self.addEventListener("fetch", (event) => {
  const req = event.request;
  const url = new URL(req.url);

  // ❌ Μην πιάνεις εξωτερικά requests
  if (url.origin !== self.location.origin) return;

  // 🔄 API → network first (να έχει φρέσκα stats)
  if (url.pathname.startsWith("/api/")) {
    event.respondWith(networkFirst(req));
    return;
  }

  // 📁 Static αρχεία → cache first
  if (url.pathname.startsWith("/static/")) {
  event.respondWith(staleWhileRevalidate(req));
  return;
}


  // 🌍 Pages → network first, fallback στο cache
  if (req.mode === "navigate") {
    event.respondWith(networkFirst(req));
    return;
  }

  // Default
  event.respondWith(cacheFirst(req));
});

/* ===============================
   STRATEGIES
   =============================== */

async function cacheFirst(req) {
  const cache = await caches.open(STATIC_CACHE);
  const cached = await cache.match(req);
  if (cached) return cached;

  const res = await fetch(req);
  if (res && res.status === 200) {
    cache.put(req, res.clone());
  }
  return res;
}

async function networkFirst(req) {
  const cache = await caches.open(STATIC_CACHE);
  try {
    const res = await fetch(req);
    if (res && res.status === 200) {
      cache.put(req, res.clone());
    }
    return res;
  } catch (err) {
    const cached = await cache.match(req);
    if (cached) return cached;

    return new Response(
      "Είσαι offline. Παρακαλώ έλεγξε τη σύνδεσή σου.",
      { status: 503, headers: { "Content-Type": "text/plain; charset=utf-8" } }
    );
  }
}
async function staleWhileRevalidate(req) {
  const cache = await caches.open(STATIC_CACHE);
  const cached = await cache.match(req);

  const networkFetch = fetch(req)
    .then((res) => {
      if (res && res.status === 200) {
        cache.put(req, res.clone());
      }
      return res;
    })
    .catch(() => cached);

  return cached || networkFetch;
}


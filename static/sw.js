/* Service Worker for Gustul Cărților PWA.
 * Scope: /
 * Strict privacy & offline safety rules:
 * - NO caching of authenticated HTML (child home, guardian dashboard, shelf, etc.)
 * - NO background sync or offline queueing of POST mutations (never fake a save)
 * - Safe fallback: only public static assets + public /offline/ shell cached
 */

const CACHE_NAME = "gustul-cartilor-static-v1";

const PRECACHE_ASSETS = [
  "/offline/",
  "/static/css/child.css",
  "/static/js/htmx.min.js",
  "/static/manifest.webmanifest",
  "/static/img/icons/icon-192.png",
  "/static/img/icons/icon-512.png",
  "/static/img/mascot/mascot-happy.svg",
  "/static/img/mascot/mascot-cheer.svg",
  "/static/img/mascot/mascot-think.svg",
  "/static/img/mascot/mascot-oops.svg",
  "/static/img/avatars/fox.svg",
  "/static/img/avatars/owl.svg",
  "/static/img/avatars/cat.svg",
  "/static/img/avatars/bear.svg",
  "/static/img/avatars/rabbit.svg",
  "/static/img/avatars/hedgehog.svg",
  "/static/img/avatars/squirrel.svg",
  "/static/img/avatars/turtle.svg"
];

// Install: precache offline shell and static visual assets only
self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(PRECACHE_ASSETS);
    }).then(() => self.skipWaiting())
  );
});

// Activate: clean up old caches
self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) => {
      return Promise.all(
        keys.map((key) => {
          if (key !== CACHE_NAME) {
            return caches.delete(key);
          }
        })
      );
    }).then(() => self.clients.claim())
  );
});

// Fetch: enforce strict privacy and offline fallback
self.addEventListener("fetch", (event) => {
  const request = event.request;

  // 1. NEVER intercept or cache non-GET requests (POST progress, login, PIN, etc.)
  if (request.method !== "GET") {
    return; // Pass through to browser network layer
  }

  const url = new URL(request.url);

  // 2. Navigation requests (HTML pages)
  if (request.mode === "navigate") {
    // Network-first; NEVER cache authenticated or personal HTML pages
    event.respondWith(
      fetch(request).catch(() => {
        // Safe fallback: return the static unauthenticated offline shell
        return caches.match("/offline/").then((fallback) => {
          return fallback || new Response("Nu am internet acum.", {
            status: 503,
            headers: { "Content-Type": "text/html; charset=utf-8" }
          });
        });
      })
    );
    return;
  }

  // 3. Static assets: Cache-first fallback to network
  if (url.pathname.startsWith("/static/") || url.pathname === "/offline/") {
    event.respondWith(
      caches.match(request).then((cachedResponse) => {
        if (cachedResponse) {
          return cachedResponse;
        }
        return fetch(request);
      })
    );
    return;
  }

  // 4. Any other GET: Network with graceful catch (no private caching)
  event.respondWith(fetch(request));
});


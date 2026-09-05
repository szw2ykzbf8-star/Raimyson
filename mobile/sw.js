const CACHE_NAME = "fintrack-v2";
const CACHE_FILES = [
  "index.html",
  "config.js",
  "manifest.json",
];

self.addEventListener("install", e => {
  e.waitUntil(
    caches.open(CACHE_NAME).then(c => c.addAll(CACHE_FILES))
  );
  self.skipWaiting();
});

self.addEventListener("activate", e => {
  e.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k)))
    )
  );
  self.clients.claim();
});

self.addEventListener("fetch", e => {
  // Estratégia: network-first, fallback para cache
  e.respondWith(
    fetch(e.request).catch(() => caches.match(e.request))
  );
});

self.addEventListener("message", e => {
  if (e.data && e.data.type === "QUEUE_GASTO") {
    self.clients.matchAll().then(clients => {
      clients.forEach(c => c.postMessage({ type: "QUEUED", data: e.data.payload }));
    });
  }
});

const CACHE = "fintrack-v1";
const OFFLINE_QUEUE_KEY = "fintrack_offline_queue";

self.addEventListener("install", e => {
  e.waitUntil(
    caches.open(CACHE).then(c => c.addAll(["/"]))
  );
  self.skipWaiting();
});

self.addEventListener("activate", e => {
  self.clients.claim();
});

self.addEventListener("fetch", e => {
  e.respondWith(
    fetch(e.request).catch(() => caches.match(e.request))
  );
});

// Recebe mensagem do app para salvar offline
self.addEventListener("message", e => {
  if (e.data && e.data.type === "QUEUE_GASTO") {
    // Notifica o cliente que ficou na fila
    self.clients.matchAll().then(clients => {
      clients.forEach(c => c.postMessage({ type: "QUEUED", data: e.data.payload }));
    });
  }
});

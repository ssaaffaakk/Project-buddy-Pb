/* ProjectBuddy service worker — offline shell + (later) push.
 *
 * Strategy, chosen for an authenticated dynamic app:
 *   - navigations       → network-first, fall back to a cached offline page
 *                         (never persist authed HTML, so users can't see each
 *                          other's cached pages).
 *   - /static/ assets   → stale-while-revalidate (fast, self-healing).
 *   - everything else   → straight to network.
 */
const CACHE = 'pb-static-v1';
const OFFLINE_URL = '/static/offline.html';
const PRECACHE = [
  OFFLINE_URL,
  '/static/css/pb-theme.css?v=4',
  '/static/css/mobile.css?v=4',
  '/static/js/pb-theme.js',
  '/static/images/icon-192.png',
  '/static/images/icon-512.png',
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE)
      .then((cache) => cache.addAll(PRECACHE))
      .then(() => self.skipWaiting())
      .catch(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (event) => {
  const req = event.request;
  if (req.method !== 'GET') return;

  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return;

  // Navigations: always try the network first so content is fresh and
  // per-user; only reach for the offline page when the network is gone.
  if (req.mode === 'navigate') {
    event.respondWith(fetch(req).catch(() => caches.match(OFFLINE_URL)));
    return;
  }

  // Static assets: serve cache immediately, refresh in the background.
  if (url.pathname.startsWith('/static/')) {
    event.respondWith(
      caches.open(CACHE).then((cache) =>
        cache.match(req).then((cached) => {
          const network = fetch(req)
            .then((res) => {
              if (res && res.ok) cache.put(req, res.clone());
              return res;
            })
            .catch(() => cached);
          return cached || network;
        })
      )
    );
  }
});

/* ── Web push (wired up in Item 4 push step) ─────────────────────────────── */
self.addEventListener('push', (event) => {
  let data = {};
  try { data = event.data ? event.data.json() : {}; } catch (e) { data = {}; }
  const title = data.title || 'ProjectBuddy';
  const options = {
    body: data.body || '',
    icon: '/static/images/icon-192.png',
    badge: '/static/images/icon-192.png',
    data: { url: data.url || '/dashboard' },
    tag: data.tag || undefined,
  };
  event.waitUntil(self.registration.showNotification(title, options));
});

self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  const target = (event.notification.data && event.notification.data.url) || '/dashboard';
  event.waitUntil(
    self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then((clients) => {
      for (const client of clients) {
        if (client.url.includes(target) && 'focus' in client) return client.focus();
      }
      if (self.clients.openWindow) return self.clients.openWindow(target);
    })
  );
});

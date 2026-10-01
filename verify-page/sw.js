// Offline copy of Pramaan Verify. The page itself is cached on the first visit; the records and the
// public key are fetched fresh when there is a connection and taken from the cache when there is not.
// (Browsers allow this only on https:// pages and on localhost.)
const CACHE = 'pramaan-verify-v1'
const SHELL = [
  './', 'index.html', 'style.css', 'app.js', 'verify.js', 'icon.svg',
  'fonts/hind-latin-400-normal.woff2', 'fonts/hind-latin-600-normal.woff2',
  'fonts/hind-devanagari-400-normal.woff2', 'fonts/hind-devanagari-600-normal.woff2',
  'fonts/poppins-latin-600-normal.woff2', 'fonts/poppins-latin-700-normal.woff2', 'fonts/ibm-plex-mono-latin-400-normal.woff2',
]
const FRESH = ['records.json', 'public-key.pem']

self.addEventListener('install', (event) => {
  event.waitUntil(caches.open(CACHE).then((cache) => cache.addAll([...SHELL, ...FRESH]).catch(() => cache.addAll(SHELL))))
  self.skipWaiting()
})

self.addEventListener('activate', (event) => {
  event.waitUntil(caches.keys().then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))))
  self.clients.claim()
})

self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url)
  if (event.request.method !== 'GET' || url.origin !== location.origin) return
  const fresh = FRESH.some((name) => url.pathname.endsWith('/' + name))
  if (fresh) {
    // network first, so newly signed or withdrawn records show up
    event.respondWith(
      fetch(event.request)
        .then((response) => {
          const copy = response.clone()
          caches.open(CACHE).then((cache) => cache.put(event.request, copy))
          return response
        })
        .catch(() => caches.match(event.request)),
    )
  } else {
    event.respondWith(caches.match(event.request, { ignoreSearch: true }).then((hit) => hit || fetch(event.request)))
  }
})

// Offline copy of Pramaan Verify. Everything is fetched fresh when there is a connection (so new
// records, withdrawals and page updates show up at once) and taken from the saved copy when there is not.
// (Browsers allow this only on https:// pages and on localhost.)
const CACHE = 'pramaan-verify-v2'
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
  // network first, the saved copy when offline
  event.respondWith(
    fetch(event.request)
      .then((response) => {
        const copy = response.clone()
        caches.open(CACHE).then((cache) => cache.put(event.request, copy))
        return response
      })
      .catch(() => caches.match(event.request, { ignoreSearch: true })),
  )
})

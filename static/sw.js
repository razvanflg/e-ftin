const CACHE='e-ftin-v10-text-icon-final';
const ASSETS=['/','/static/icon-512.png?v=10','/static/icon-192.png?v=10','/static/manifest.json?v=10','/static/logo.png','/inscrie-sofer','/trimite-colet'];
self.addEventListener('install',e=>{
  self.skipWaiting();
  e.waitUntil(caches.open(CACHE).then(c=>c.addAll(ASSETS)))
});
self.addEventListener('activate',e=>{
  e.waitUntil(caches.keys().then(keys=>Promise.all(keys.map(k=>{if(k!==CACHE)return caches.delete(k)}))))
});
self.addEventListener('fetch',e=>{
  e.respondWith(caches.match(e.request).then(r=>r||fetch(e.request)))
});

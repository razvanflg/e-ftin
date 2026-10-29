
const CACHE='e-ftin-v3';
const ASSETS=['/','/static/logo.png','/static/manifest.json','/inscrie-sofer','/trimite-colet'];
self.addEventListener('install',e=>{e.waitUntil(caches.open(CACHE).then(c=>c.addAll(ASSETS)))});
self.addEventListener('fetch',e=>{e.respondWith(caches.match(e.request).then(r=>r||fetch(e.request)))});


const CACHE='e-ftin-text-final-v1';
const ASSETS=[
  '/',
  '/static/icon-text-final-512.png?v=final',
  '/static/icon-text-final-192.png?v=final',
  '/static/manifest.json?v=final',
  '/static/logo.png',
  '/inscrie-sofer',
  '/trimite-colet'
];
self.addEventListener('install',e=>{
  self.skipWaiting();
  e.waitUntil(caches.open(CACHE).then(c=>c.addAll(ASSETS)));
});
self.addEventListener('activate',e=>{
  e.waitUntil(
    caches.keys().then(keys=>Promise.all(keys.map(k=>{
      if(k!==CACHE){
        console.log('Deleting old cache',k);
        return caches.delete(k);
      }
    })))
    .then(()=>self.clients.claim())
  );
});
self.addEventListener('fetch',e=>{
  e.respondWith(
    caches.match(e.request).then(r=>r||fetch(e.request))
  );
});

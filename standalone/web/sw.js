// Cache only public, versioned app shell assets. Never cache API state or commands.
const VERSION="pool-spa-0.1.6";
const ASSETS=["/","/style.css","/app.js","/icon.svg","/manifest.webmanifest"];
self.addEventListener("install",event=>{event.waitUntil(caches.open(VERSION).then(cache=>cache.addAll(ASSETS)).then(()=>self.skipWaiting()))});
self.addEventListener("activate",event=>{event.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(key=>key!==VERSION).map(key=>caches.delete(key)))).then(()=>self.clients.claim()))});
self.addEventListener("fetch",event=>{const req=event.request;if(req.method!=="GET"||new URL(req.url).pathname.startsWith("/api/"))return;event.respondWith(fetch(req).catch(()=>caches.match(req)))});

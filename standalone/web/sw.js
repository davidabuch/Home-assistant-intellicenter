// Cache only public, versioned app shell assets. Never cache API state or commands.
const VERSION="pool-spa-family-approved-icons-v2-layout-0.1.19";
const ASSETS=["/","/style.css?v=0.1.19","/app.js?v=0.1.19","/icons/approved-v2/icon-16.png","/icons/approved-v2/icon-32.png","/icons/approved-v2/icon-180.png","/icons/approved-v2/icon-192.png","/icons/approved-v2/icon-512.png","/favicon.ico","/apple-touch-icon.png?v=approved-v2","/apple-touch-icon-precomposed.png?v=approved-v2","/manifest.webmanifest","/backyard-scene.svg"];
self.addEventListener("install",event=>{event.waitUntil(caches.open(VERSION).then(async cache=>{await cache.addAll(ASSETS);try{await cache.add("/backyard-final.jpg")}catch(e){/* optional until image is uploaded */}}).then(()=>self.skipWaiting()))});
self.addEventListener("activate",event=>{event.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(key=>key!==VERSION).map(key=>caches.delete(key)))).then(()=>self.clients.claim()))});
self.addEventListener("fetch",event=>{const req=event.request;if(req.method!=="GET"||new URL(req.url).pathname.startsWith("/api/"))return;event.respondWith(fetch(req).catch(()=>caches.match(req)))});

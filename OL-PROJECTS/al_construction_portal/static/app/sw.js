/* Service worker del portal de obra: guarda la aplicación para abrirla sin
 * señal. Los datos y la cola de envíos los maneja la página (IndexedDB). */
const CACHE = "obra-app-v2";
const SHELL = [
    "/obra/app/",
    "/al_construction_portal/static/app/app.js",
    "/al_construction_portal/static/app/app.css",
    "/al_construction_portal/static/app/icon-192.png",
];

self.addEventListener("install", (event) => {
    event.waitUntil(caches.open(CACHE).then((cache) => cache.addAll(SHELL)));
    self.skipWaiting();
});

self.addEventListener("activate", (event) => {
    event.waitUntil(
        caches
            .keys()
            .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
    );
    self.clients.claim();
});

self.addEventListener("fetch", (event) => {
    const url = new URL(event.request.url);
    if (event.request.method !== "GET" || url.pathname.startsWith("/construction/api/")) {
        return;
    }
    // La aplicación: primero la red (para tomar la versión nueva) y, sin
    // señal, la copia guardada.
    event.respondWith(
        fetch(event.request)
            .then((response) => {
                const copy = response.clone();
                caches.open(CACHE).then((cache) => cache.put(event.request, copy));
                return response;
            })
            .catch(() => caches.match(event.request).then((hit) => hit || caches.match("/obra/app/")))
    );
});

// Android: envío en segundo plano cuando vuelve la señal.
self.addEventListener("sync", (event) => {
    if (event.tag === "obra-queue") {
        event.waitUntil(
            self.clients.matchAll().then((clients) => {
                clients.forEach((client) => client.postMessage({ type: "flush" }));
            })
        );
    }
});

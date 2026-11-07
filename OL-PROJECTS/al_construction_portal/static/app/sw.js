/* Service worker del portal de obra: guarda la aplicación para abrirla sin
 * señal. Los datos y la cola de envíos los maneja la página (IndexedDB). */
const CACHE = "obra-app-v10";
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

// Avisos al celular (paquete 6, CR-57): Odoo envía el mensaje con su título,
// texto y el registro; al tocarlo se abre la aplicación en esa pantalla.
self.addEventListener("push", (event) => {
    let data = {};
    try {
        data = event.data ? event.data.json() : {};
    } catch {
        data = { title: event.data ? event.data.text() : "Portal de obra" };
    }
    const options = data.options || {};
    event.waitUntil(
        self.registration.showNotification(data.title || "Portal de obra", {
            body: options.body || "",
            icon: "/al_construction_portal/static/app/icon-192.png",
            badge: "/al_construction_portal/static/app/icon-192.png",
            data: options.data || {},
            tag: options.data && options.data.model ? `${options.data.model}:${options.data.res_id}` : undefined,
        })
    );
});

self.addEventListener("notificationclick", (event) => {
    event.notification.close();
    const data = event.notification.data || {};
    const target = data.model ? `/obra/app/#open=${encodeURIComponent(data.model)}:${data.res_id || ""}` : "/obra/app/";
    event.waitUntil(
        self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((clients) => {
            const client = clients.find((c) => new URL(c.url).pathname.startsWith("/obra/app"));
            if (client) {
                client.postMessage({ type: "open", model: data.model, res_id: data.res_id });
                return client.focus();
            }
            return self.clients.openWindow(target);
        })
    );
});

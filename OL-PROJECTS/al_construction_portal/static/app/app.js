/* Portal de obra (requerimiento CREVAL v1.0, 4.11).
 *
 * Aplicación web instalable para capataces, contratas y oficina técnica.
 * Trabaja sin señal: guarda en el equipo los datos de la obra (partidas,
 * catálogo, cuadrilla, entregas y valorizaciones) y deja cada registro en una
 * cola con sus fotos comprimidas, que se envía al volver la conexión. Cada
 * registro lleva un identificador único: Odoo no lo duplica si el envío se
 * repite y vuelve a validar sus reglas al recibirlo.
 *
 * Las pantallas siguen el prototipo «Portal de obra CREVAL» (14 pantallas).
 * Usa solo los servicios JSON /construction/api/v1 (los mismos que usará una
 * aplicación nativa). */
(function () {
    "use strict";

    const API = "/construction/api/v1";
    const MAX_PHOTOS = { progress: 5, daily: 10, change: 8, deduction: 5, expense: 3 };
    const state = {
        session: null, // {token, name}
        remember: true, // «Mantener la sesión en este celular»
        me: null,
        projectId: null,
        data: null, // sincronización de la obra
        queue: [],
        route: "home",
        params: {},
        online: navigator.onLine,
        draft: {}, // formularios en curso
        cart: [], // requerimiento
    };

    // ------------------------------------------------------------------
    // Utilidades
    // ------------------------------------------------------------------
    const $app = () => document.getElementById("app");
    const esc = (value) =>
        String(value === null || value === undefined ? "" : value).replace(
            /[&<>"']/g,
            (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]
        );
    const num = (value, digits = 2) =>
        Number(value || 0).toLocaleString("es-PE", {
            minimumFractionDigits: digits,
            maximumFractionDigits: digits,
        });
    // Cantidades: sin decimales de más («3 bls», «18.50 m²»).
    const qtyText = (value) => num(value, Number(value) % 1 ? 2 : 0);
    const money = (value) => "S/ " + num(value, 2);
    const today = () => new Date(Date.now() - new Date().getTimezoneOffset() * 60000)
        .toISOString().slice(0, 10);
    const MONTHS = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "set", "oct", "nov", "dic"];
    const DAYS = ["domingo", "lunes", "martes", "miércoles", "jueves", "viernes", "sábado"];
    const asDate = (iso) => new Date(iso + "T12:00:00");
    // «24-oct», «sábado 24-oct-2026» y «del 22 al 28-oct».
    const dayMonth = (iso) => (iso ? `${asDate(iso).getDate()}-${MONTHS[asDate(iso).getMonth()]}` : "");
    const longDay = (iso) => (iso ? `${DAYS[asDate(iso).getDay()]} ${dayMonth(iso)}-${asDate(iso).getFullYear()}` : "");
    const range = (start, end) => {
        if (!start || !end) return "";
        const same = asDate(start).getMonth() === asDate(end).getMonth();
        return `del ${same ? asDate(start).getDate() : dayMonth(start)} al ${dayMonth(end)}`;
    };
    const clock = (iso) => (iso ? new Date(iso).toLocaleTimeString("es-PE", { hour: "2-digit", minute: "2-digit", hour12: false }) : "");
    const initials = (name) =>
        String(name || "")
            .split(/[^\p{L}\p{N}]+/u)
            .filter(Boolean)
            .slice(0, 2)
            .map((w) => w[0])
            .join("")
            .toUpperCase();
    const uuid = () =>
        (crypto.randomUUID && crypto.randomUUID()) ||
        "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => {
            const r = (Math.random() * 16) | 0;
            return (c === "x" ? r : (r & 0x3) | 0x8).toString(16);
        });
    const role = (name) => state.data && state.data.roles.includes(name);
    // Empresa del sitio (antes de ingresar viene en la página).
    // Sin la forma societaria: «Personal propio Constructora Andina».
    const shortName = (name) => String(name || "").replace(/[\s,]+(S\.?\s?A\.?\s?C?\.?|S\.?\s?A\.?\s?A\.?|E\.?\s?I\.?\s?R\.?\s?L\.?|S\.?\s?R\.?\s?L\.?)$/i, "");
    const brand = () => ({
        name: (state.me && state.me.company.name) || $app().dataset.company || "Portal de obra",
        initials: (state.me && state.me.company.initials) || $app().dataset.initials || "OB",
    });

    // ------------------------------------------------------------------
    // Almacenamiento en el equipo (IndexedDB)
    // ------------------------------------------------------------------
    let dbPromise = null;
    function db() {
        if (!dbPromise) {
            dbPromise = new Promise((resolve, reject) => {
                const request = indexedDB.open("obra-portal", 1);
                request.onupgradeneeded = () => {
                    request.result.createObjectStore("queue", { keyPath: "uuid" });
                    request.result.createObjectStore("cache");
                };
                request.onsuccess = () => resolve(request.result);
                request.onerror = () => reject(request.error);
            });
        }
        return dbPromise;
    }
    async function store(name, mode, fn) {
        const database = await db();
        return new Promise((resolve, reject) => {
            const tx = database.transaction(name, mode);
            const result = fn(tx.objectStore(name));
            tx.oncomplete = () => resolve(result && result.result !== undefined ? result.result : result);
            tx.onerror = () => reject(tx.error);
        });
    }
    const cacheGet = (key) =>
        db().then(
            (database) =>
                new Promise((resolve) => {
                    const request = database.transaction("cache").objectStore("cache").get(key);
                    request.onsuccess = () => resolve(request.result);
                    request.onerror = () => resolve(undefined);
                })
        );
    const cachePut = (key, value) => store("cache", "readwrite", (s) => s.put(value, key));
    const queueAll = () =>
        db().then(
            (database) =>
                new Promise((resolve) => {
                    const request = database.transaction("queue").objectStore("queue").getAll();
                    request.onsuccess = () =>
                        resolve(request.result.sort((a, b) => a.created.localeCompare(b.created)));
                    request.onerror = () => resolve([]);
                })
        );
    const queuePut = (item) => store("queue", "readwrite", (s) => s.put(item));
    const queueDelete = (key) => store("queue", "readwrite", (s) => s.delete(key));

    // La sesión dura 90 días en el celular; sin «Mantener la sesión», solo
    // mientras la aplicación esté abierta.
    function loadSession() {
        try {
            const saved = localStorage.getItem("obra-session") || sessionStorage.getItem("obra-session");
            state.session = JSON.parse(saved || "null");
            state.remember = !sessionStorage.getItem("obra-session");
            state.projectId = Number(localStorage.getItem("obra-project")) || null;
        } catch {
            state.session = null;
        }
    }
    function saveSession() {
        try {
            localStorage.removeItem("obra-session");
            sessionStorage.removeItem("obra-session");
            if (state.session) {
                (state.remember ? localStorage : sessionStorage).setItem(
                    "obra-session", JSON.stringify(state.session));
            }
            if (state.projectId) {
                localStorage.setItem("obra-project", String(state.projectId));
            }
        } catch {
            // Navegación privada: la sesión dura lo que dure la página.
        }
    }

    // ------------------------------------------------------------------
    // Servicios
    // ------------------------------------------------------------------
    async function call(path, body, method) {
        const headers = { "Content-Type": "application/json" };
        if (state.session) {
            headers.Authorization = "Bearer " + state.session.token;
        }
        const response = await fetch(API + path, {
            method: method || (body ? "POST" : "GET"),
            headers,
            body: body ? JSON.stringify(body) : undefined,
        });
        let data = {};
        try {
            data = await response.json();
        } catch {
            data = {};
        }
        if (!response.ok) {
            const error = new Error(data.error || "Error " + response.status);
            error.status = response.status;
            throw error;
        }
        return data;
    }
    // PDF con el token del portal (el visor del celular no manda la cabecera).
    async function openPdf(path) {
        const win = window.open("", "_blank");
        try {
            const response = await fetch(API + path, {
                headers: { Authorization: "Bearer " + state.session.token },
            });
            if (!response.ok) {
                throw new Error((await response.json().catch(() => ({}))).error || "Error " + response.status);
            }
            const url = URL.createObjectURL(await response.blob());
            if (win) win.location = url;
            else location.href = url;
        } catch (error) {
            if (win) win.close();
            state.params.error = state.online ? error.message : "Sin señal: abra el PDF con conexión.";
            render();
        }
    }

    async function refresh() {
        if (!state.session) {
            return;
        }
        try {
            state.me = await call("/me");
            await cachePut("me", state.me);
            if (!state.projectId || !state.me.projects.some((p) => p.id === state.projectId)) {
                state.projectId = state.me.projects.length ? state.me.projects[0].id : null;
            }
            if (state.projectId) {
                state.data = await call("/sync/" + state.projectId);
                await cachePut("sync:" + state.projectId, state.data);
            }
            saveSession();
        } catch (error) {
            if (error.status === 401) {
                return logout(error.message);
            }
            await loadCache();
        }
    }
    async function loadCache() {
        state.me = state.me || (await cacheGet("me")) || null;
        if (state.projectId) {
            state.data = (await cacheGet("sync:" + state.projectId)) || state.data;
        }
    }

    // Cola de envíos.
    async function enqueue(kind, path, payload, label) {
        const item = {
            uuid: payload.uuid,
            kind,
            path,
            payload,
            label,
            status: "pending",
            error: "",
            created: new Date().toISOString(),
        };
        await queuePut(item);
        state.queue = await queueAll();
        flush();
        if (navigator.serviceWorker && navigator.serviceWorker.ready) {
            navigator.serviceWorker.ready
                .then((reg) => reg.sync && reg.sync.register("obra-queue"))
                .catch(() => {});
        }
    }
    let flushing = false;
    async function flush() {
        if (flushing || !navigator.onLine || !state.session) {
            return;
        }
        flushing = true;
        let stockChanged = false;
        try {
            for (const item of await queueAll()) {
                if (item.status !== "pending") {
                    continue;
                }
                try {
                    const result = await call(item.path, item.payload);
                    item.status = "done";
                    item.result = result;
                    item.sent = new Date().toISOString();
                    await queuePut(item);
                    stockChanged = stockChanged || item.kind === "reception" || item.kind === "return";
                } catch (error) {
                    if (error.status === 401) {
                        break;
                    }
                    if (error.status === 403 || error.status === 422 || error.status === 404) {
                        item.status = "rejected";
                        item.error = error.message;
                        await queuePut(item);
                    } else {
                        break; // sin señal o servidor caído: se reintenta después
                    }
                }
            }
        } finally {
            flushing = false;
            state.queue = await queueAll();
            // Lo recibido o devuelto cambia el material de la obra: sin esperar a «Actualizar».
            if (stockChanged) {
                await refresh();
            }
            render();
        }
    }

    // Fotos: comprimidas en el equipo (lado mayor según la compañía).
    function compress(file) {
        const max = (state.me && state.me.params.photo_max_px) || 1600;
        return new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onerror = reject;
            reader.onload = () => {
                const img = new Image();
                img.onerror = reject;
                img.onload = () => {
                    const scale = Math.min(1, max / Math.max(img.width, img.height));
                    const canvas = document.createElement("canvas");
                    canvas.width = Math.round(img.width * scale);
                    canvas.height = Math.round(img.height * scale);
                    canvas.getContext("2d").drawImage(img, 0, 0, canvas.width, canvas.height);
                    resolve({
                        name: (file.name || "foto").replace(/\.[^.]+$/, "") + ".jpg",
                        mimetype: "image/jpeg",
                        data: canvas.toDataURL("image/jpeg", 0.8),
                        taken: new Date().toISOString(),
                    });
                };
                img.src = reader.result;
            };
            reader.readAsDataURL(file);
        });
    }
    function locate() {
        return new Promise((resolve) => {
            if (!navigator.geolocation) {
                return resolve(null);
            }
            navigator.geolocation.getCurrentPosition(
                (pos) => resolve({ latitude: pos.coords.latitude, longitude: pos.coords.longitude }),
                () => resolve(null),
                { enableHighAccuracy: true, timeout: 10000, maximumAge: 60000 }
            );
        });
    }
    function distance(a, b) {
        const rad = (x) => (x * Math.PI) / 180;
        const dLat = rad(b.latitude - a.latitude);
        const dLon = rad(b.longitude - a.longitude);
        const h =
            Math.sin(dLat / 2) ** 2 +
            Math.cos(rad(a.latitude)) * Math.cos(rad(b.latitude)) * Math.sin(dLon / 2) ** 2;
        return 2 * 6371000 * Math.asin(Math.sqrt(h));
    }

    // ------------------------------------------------------------------
    // Navegación
    // ------------------------------------------------------------------
    function go(route, params) {
        stopScanner();
        state.route = route;
        state.params = params || {};
        window.scrollTo(0, 0);
        render();
    }
    async function logout(message) {
        if (state.session) {
            call("/logout", {}).catch(() => {});
        }
        state.session = null;
        state.data = null;
        saveSession();
        state.route = "login";
        state.params = { error: message || "" };
        render();
    }

    // ------------------------------------------------------------------
    // Piezas de las pantallas
    // ------------------------------------------------------------------
    const icon = {
        back: '<path d="M15 18l-6-6 6-6"/>',
        next: '<path d="M9 18l6-6-6-6"/>',
        down: '<path d="M6 9l6 6 6-6"/>',
        home: '<path d="M3 10.5L12 3l9 7.5V21h-6v-6H9v6H3z"/>',
        chart: '<path d="M3 3v18h18"/><path d="M7 15l4-4 3 3 6-6"/>',
        cart: '<path d="M3 4h2l2.4 11.2a2 2 0 0 0 2 1.6h7.7a2 2 0 0 0 2-1.5L21 8H6.2"/><circle cx="10" cy="20.5" r="1"/><circle cx="18" cy="20.5" r="1"/>',
        sync: '<path d="M21 12a9 9 0 1 1-3-6.7L21 8"/><path d="M21 3v5h-5"/>',
        camera:
            '<path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"/><circle cx="12" cy="13" r="4"/>',
        report: '<rect x="5" y="3" width="14" height="18" rx="2"/><path d="M9 3v3h6V3M9 11h6M9 15h4"/>',
        crew: '<circle cx="9" cy="8" r="3.5"/><path d="M2.5 20a6.5 6.5 0 0 1 13 0"/><circle cx="17.5" cy="9" r="2.5"/><path d="M17 14a5 5 0 0 1 4.5 5"/>',
        truck: '<rect x="1" y="6" width="14" height="10"/><path d="M15 9h4l3 3v4h-7"/><circle cx="5.5" cy="18" r="2"/><circle cx="18.5" cy="18" r="2"/>',
        undo: '<path d="M9 14L4 9l5-5"/><path d="M4 9h10.5a5.5 5.5 0 0 1 0 11H11"/>',
        doc: '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6M8 13h8M8 17h5"/>',
        offline: '<path d="M1 1l22 22M16.7 11.1A11 11 0 0 1 19 12.6M5 12.6a11 11 0 0 1 5.2-2.5M10.7 5.1A16 16 0 0 1 22.6 9M1.4 9a16 16 0 0 1 4.4-2.8M8.5 16.1a5 5 0 0 1 7 0M12 20h.01"/>',
        eye: '<path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/>',
        qr: '<rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/><path d="M14 14h3v3h-3zM20 14v.01M14 20h.01M17 20h4v-3"/>',
        phone: '<rect x="5" y="2" width="14" height="20" rx="2"/><path d="M12 18h.01"/>',
        pin: '<path d="M21 10c0 7-9 13-9 13S3 17 3 10a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/>',
        check: '<path d="M20 6L9 17l-5-5"/>',
        clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
        search: '<circle cx="11" cy="11" r="7"/><path d="M21 21l-4.3-4.3"/>',
        inbox: '<path d="M22 12h-6l-2 3h-4l-2-3H2"/><path d="M5.5 5.1L2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.5-6.9A2 2 0 0 0 16.8 4H7.2a2 2 0 0 0-1.7 1.1z"/>',
        site: '<path d="M3 21h18M5 21V9l7-5 7 5v12"/><path d="M9 21v-6h6v6"/>',
        alert: '<path d="M10.3 3.9L1.8 18a2 2 0 0 0 1.7 3h16.9a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z"/><path d="M12 9v4M12 17h.01"/>',
        close: '<path d="M18 6L6 18M6 6l12 12"/>',
    };
    const svg = (name, size = 24) =>
        `<svg width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${icon[name]}</svg>`;

    function offlineBanner() {
        return state.online
            ? ""
            : `<div class="offline">${svg("offline", 20)}<span><b>Sin señal.</b> ${pendingText()}</span></div>`;
    }
    function header(title, sub, back, extra) {
        return `<header class="bar">${
            back
                ? `<button class="icon-btn" data-go="${back}" aria-label="Volver">${svg("back")}</button>`
                : `<div class="logo">${esc(brand().initials)}</div>`
        }<div class="bar-title"><span>${esc(title)}</span>${sub ? `<small>${esc(sub)}</small>` : ""}</div>${extra || ""}</header>${offlineBanner()}`;
    }
    function pendingText() {
        const count = state.queue.filter((q) => q.status === "pending").length;
        if (!count) {
            return "Lo que registre se enviará al volver la conexión.";
        }
        return count === 1 ? "1 registro espera para enviarse." : `${count} registros esperan para enviarse.`;
    }

    // Paquete 6, CR-48 (U2): el residente tiene su propia barra.
    const isResident = () => role("resident");
    const inboxTotal = () => {
        const r = (state.data && state.data.resident) || { progress: [], requests: [] };
        return r.progress.length + r.requests.length;
    };
    function nav(active) {
        const items = isResident()
            ? [
                  ["home", "home", "Inicio"],
                  ["inbox", "inbox", "Bandejas"],
                  ["site", "site", "Obra"],
                  ["queue", "sync", "Por enviar"],
              ]
            : [
                  ["home", "home", "Inicio"],
                  ["partidas", "chart", "Avance"],
                  ["catalog", "cart", "Pedidos"],
                  ["queue", "sync", "Por enviar"],
              ];
        const pending = state.queue.filter((q) => q.status !== "done").length;
        const inbox = isResident() ? inboxTotal() : 0;
        return `<nav class="nav" aria-label="Navegación principal">${items
            .map(
                ([route, ic, label]) =>
                    `<button data-go="${route}" class="${active === route ? "active" : ""}">${svg(ic)}<span>${label}${
                        route === "queue" && pending ? ` (${pending})` : route === "inbox" && inbox ? ` (${inbox})` : ""
                    }</span></button>`
            )
            .join("")}</nav>`;
    }
    const projectName = () =>
        (state.data && state.data.project.name) ||
        (state.me && (state.me.projects.find((p) => p.id === state.projectId) || {}).name) ||
        "";
    // «096-26 BOSCH - Implementación nueva oficina Perú» → código y descripción.
    const projectParts = () => {
        const [code, ...rest] = projectName().split(" - ");
        return { code, description: rest.join(" - ") };
    };
    const member = (roleName) => ((state.data && state.data.members) || []).find((m) => m.role === roleName);
    function scopeText() {
        if (role("contractor")) {
            const m = member("contractor");
            return m && m.partner ? m.partner : "";
        }
        if (role("foreman")) {
            return "cuadrilla de " + ((member("foreman") || {}).name || (state.me && state.me.user.name) || "");
        }
        return "";
    }
    const join = (...parts) => parts.filter(Boolean).join(" · ");
    // Partida legible (CR-17): código y nombre, y debajo su nivel superior y
    // el rol; nunca la ruta interna. Los datos de antes de la versión 1.1 no
    // traen task_code y caen en item/name.
    const taskCode = (p) => (p.task_code !== undefined ? p.task_code : p.item) || "";
    const taskName = (p) => p.task_name || p.name || "";
    const taskSub = (p) => join(p.parent_label, p.role_label || (p.activity !== p.name ? p.activity : ""));
    const matches = (q, ...parts) => !q || parts.filter(Boolean).join(" ").toLowerCase().includes(q);
    const pill = (text, kind) => `<span class="pill ${kind || ""}">${esc(text)}</span>`;
    const stepper = (attr, value, label, small) =>
        `<div class="stepper ${small ? "small" : ""}"><button ${attr} data-delta="-1" aria-label="Restar">−</button>
         <b aria-label="${esc(label)}">${qtyText(value)}</b><button ${attr} data-delta="1" aria-label="Sumar">+</button></div>`;

    // ------------------------------------------------------------------
    // Pantallas
    // ------------------------------------------------------------------
    const screens = {};

    // 1. Ingreso con usuario y clave.
    screens.login = () => `
        <header class="bar"><div class="logo">${esc(brand().initials)}</div><div class="bar-title"><span>${esc(brand().name)}</span></div></header>
        <main class="page login">
            <div><h1>Portal de obra</h1>
            <p class="muted lead">Avance, parte diario, cuadrilla, requerimientos y recepción de la obra.</p></div>
            <form class="card form" data-form="login">
                <label>Usuario<input name="login" autocomplete="username" autocapitalize="off" required></label>
                <label>Contraseña<span class="pwd"><input name="password" type="password" autocomplete="current-password" required>
                    <button type="button" class="icon-btn" data-action="toggle-password" aria-label="Mostrar u ocultar la contraseña">${svg("eye", 22)}</button></span></label>
                <label class="check"><input type="checkbox" name="remember" ${state.remember ? "checked" : ""}> Mantener la sesión en este celular</label>
                ${state.params.error ? `<p class="error">${esc(state.params.error)}</p>` : ""}
                <button class="primary" type="submit">Ingresar</button>
                <a class="link center" href="/web/reset_password">¿Olvidó su contraseña?</a>
            </form>
            <div class="or"><span>o</span></div>
            <button class="secondary with-icon" data-go="qr">${svg("qr", 22)} Ingresar con el QR de la obra</button>
            <p class="hint with-icon">${svg("phone", 20)}<span>Instálelo en el celular con «Agregar a la pantalla de inicio». Lo que registre sin señal se envía solo al volver la conexión.</span></p>
        </main>`;

    // 2. Ingreso con el QR de la obra, su nombre y su PIN.
    screens.qr = () => {
        const site = state.params.site;
        if (!site) {
            const camera = "BarcodeDetector" in window && navigator.mediaDevices;
            return `${header("Ingresar con el QR de la obra", "", "login")}
            <main class="page">
                ${
                    camera
                        ? `<div class="scanner ${state.params.scanning ? "on" : ""}"><video id="qr-video" playsinline muted></video>
                           <div class="frame" aria-hidden="true"></div><span>Apunte al QR del cartel de la obra</span></div>
                           <button class="primary" data-action="scan-qr">${state.params.scanning ? "Leyendo el QR…" : "Leer el QR"}</button>`
                        : ""
                }
                <p class="muted center">El QR identifica la obra. Después elige su nombre y escribe su PIN de 4 dígitos.</p>
                <form class="card form" data-form="qr-code">
                    <label>${camera ? "O escriba el código de la obra" : "Código de la obra"}<input name="code" required autocapitalize="off" value="${esc(state.params.code || "")}"></label>
                    ${state.params.error ? `<p class="error">${esc(state.params.error)}</p>` : ""}
                    <button class="secondary" type="submit">Continuar</button>
                </form>
            </main>`;
        }
        return `${header("Ingresar con el QR de la obra", "", "login")}
            <main class="page">
                <div class="card read-ok"><span class="ok-icon">${svg("check", 22)}</span><span><small>Obra leída</small><b>${esc(site.project)}</b></span></div>
                <h2>¿Quién es usted?</h2>
                <form data-form="pin" class="form">
                    <div class="card list">${site.members
                        .map(
                            (m) => `<label class="pick"><span class="avatar">${esc(initials(m.name))}</span>
                            <span class="grow"><b>${esc(m.name)}</b><small>${esc(m.role)}${m.locked ? " · bloqueado" : ""}</small></span>
                            <input type="radio" name="member_id" value="${m.id}" ${m.locked ? "disabled" : ""} required></label>`
                        )
                        .join("")}</div>
                    <label>PIN de 4 dígitos<input class="pin" name="pin" type="password" inputmode="numeric" pattern="[0-9]{4}" maxlength="4" required autocomplete="one-time-code"></label>
                    ${state.params.error ? `<p class="error">${esc(state.params.error)}</p>` : ""}
                    <button class="primary" type="submit">Ingresar</button>
                </form>
            </main>`;
    };

    // 3. Inicio de la obra.
    screens.home = () => {
        if (!state.me) {
            return `${header("Portal de obra")}<main class="page"><p class="muted">Cargando…</p></main>`;
        }
        const data = state.data;
        const projects = state.me.projects;
        const tiles = [];
        if (data) {
            tiles.push(["partidas", "chart", "Avance"]);
            if (role("foreman") || role("office") || role("contractor")) {
                tiles.push(["daily", "report", "Parte diario"]);
            }
            if (role("foreman")) {
                tiles.push(["crew", "crew", "Cuadrilla y tareo"]);
            }
            if (role("foreman") || role("office")) {
                tiles.push(["catalog", "cart", "Requerimientos"]);
                tiles.push(["reception", "truck", "Recepción"]);
                tiles.push(["return", "undo", "Devolución"]);
            }
        }
        const c = (data && data.counters) || {};
        const counter = (n, one, many, accent) =>
            `<div class="card stat"><b class="${accent && n ? "accent" : ""}">${n || 0}</b><small>${n === 1 ? one : many}</small></div>`;
        const parts = projectParts();
        const week = data ? range(data.project.week_start, data.project.week_end) : "";
        const avatar = `<span class="avatar small" aria-label="${esc(state.me.user.name)}">${esc(state.me.user.initials || initials(state.me.user.name))}</span>`;
        return `${header("Portal de obra", "", "", avatar)}
            <main class="page">
                <label class="card project">
                    <small class="eyebrow">Obra</small>
                    <b>${esc(parts.code)}</b>
                    <small>${esc(join(parts.description, week ? "semana " + week : ""))}</small>
                    ${projects.length > 1 ? `<span class="chevron">${svg("down", 20)}</span>` : ""}
                    ${
                        projects.length > 1
                            ? `<select data-change="project" aria-label="Cambiar de obra">${projects
                                  .map((p) => `<option value="${p.id}" ${p.id === state.projectId ? "selected" : ""}>${esc(p.name)}</option>`)
                                  .join("")}</select>`
                            : ""
                    }
                </label>
                ${data ? pushCard() : ""}
                ${data && isResident() ? myDay(data, c) : ""}
                ${
                    data && !isResident()
                        ? `<div class="stats">${counter(c.progress_to_validate, "avance por validar", "avances por validar")}
                           ${counter(c.requests_to_approve, "pedido en aprobación", "pedidos en aprobación")}
                           ${counter(c.deliveries_today, "entrega por recibir hoy", "entregas por recibir hoy", true)}</div>`
                        : ""
                }
                ${
                    data
                        ? `${isResident() ? "<h2>Registrar y consultar</h2>" : ""}<div class="tiles">${tiles
                               .map(([route, ic, label]) => `<button class="tile" data-go="${route}">${svg(ic, 28)}<span>${label}</span></button>`)
                               .join("")}</div>
                           ${
                               role("contractor")
                                   ? `<button class="card row-link" data-go="valuations"><span class="teal">${svg("doc", 26)}</span><span><b>Valorizaciones y pagos</b><small>Su orden, fondo de garantía y deductivos</small></span>${svg("next", 20)}</button>`
                                   : ""
                           }
                           <p class="hint">Datos de la obra del ${esc((data.synced_at || "").replace("T", " ").slice(0, 16))}.
                           <button class="link" data-action="sync">Actualizar</button></p>`
                        : `<p class="muted">${projects.length ? "Sin datos de la obra: conéctese para descargarlos." : "No está en el portal de ninguna obra."}</p>`
                }
                <button class="link" data-action="logout">Salir</button>
            </main>${nav("home")}`;
    };

    // ------------------------------------------------------------------
    // Avisos al celular (paquete 6, CR-57)
    // ------------------------------------------------------------------
    const pushSupported = () => "serviceWorker" in navigator && "PushManager" in window && "Notification" in window;
    const isIos = () => /iphone|ipad|ipod/i.test(navigator.userAgent);
    const isStandalone = () => window.matchMedia("(display-mode: standalone)").matches || navigator.standalone === true;
    function pushCard() {
        let dismissed = false;
        try {
            dismissed = localStorage.getItem("obra-push-dismissed") === "1";
        } catch {
            dismissed = false;
        }
        if (dismissed || state.params.pushDone) return "";
        if (isIos() && !isStandalone()) {
            return `<div class="card push-card"><b>Avisos en el celular</b><small>En iPhone, agregue la aplicación a la pantalla de inicio (Compartir ▸ Agregar a inicio) y ábrala desde ahí para recibir avisos.</small>
                <button class="link" data-action="push-dismiss">Ahora no</button></div>`;
        }
        if (!pushSupported() || Notification.permission !== "default") return "";
        return `<div class="card push-card"><b>Avisos en el celular</b><small>Reciba en el celular, con la aplicación cerrada, los pedidos urgentes, las entregas en camino y la validación de sus avances.</small>
            <div class="row two"><button class="secondary compact" data-action="push-dismiss">Ahora no</button><button class="primary compact" data-action="push-enable">Activar avisos</button></div>
            ${state.params.pushError ? `<p class="error">${esc(state.params.pushError)}</p>` : ""}</div>`;
    }
    function urlBase64ToUint8Array(base64) {
        const padding = "=".repeat((4 - (base64.length % 4)) % 4);
        const raw = atob((base64 + padding).replace(/-/g, "+").replace(/_/g, "/"));
        return Uint8Array.from([...raw].map((c) => c.charCodeAt(0)));
    }
    async function enablePush() {
        const permission = await Notification.requestPermission();
        if (permission !== "granted") {
            throw new Error("Sin permiso para los avisos: actívelo en los ajustes del navegador.");
        }
        const { public_key: key } = await call("/push/key");
        const registration = await navigator.serviceWorker.ready;
        const send = (subscription) => {
            const json = subscription.toJSON();
            return call("/push/subscribe", { endpoint: json.endpoint, keys: json.keys, expirationTime: json.expirationTime || null, vapid_public_key: key });
        };
        const subscribe = () => registration.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: urlBase64ToUint8Array(key) });
        const current = await registration.pushManager.getSubscription();
        try {
            await send(current || (await subscribe()));
        } catch (error) {
            // Cambiaron las claves de Odoo o venció la suscripción: se rehace.
            if (!current || error.status === 401) throw error;
            await current.unsubscribe();
            await send(await subscribe());
        }
    }
    // Pantalla del registro del aviso: el residente va a su bandeja; los
    // demás, a la pantalla donde trabajan ese registro.
    function openRecord(model, resId) {
        const id = Number(resId) || 0;
        if (model === "construction.task.progress") {
            return isResident() ? go("inbox", { tab: "progress", id }) : go("queue", {});
        }
        if (model === "construction.material.request") {
            return isResident() ? go("inbox", { tab: "requests", id }) : go("queue", {});
        }
        if (model === "stock.picking") return go("reception", { id });
        if (model === "construction.daily.report") return isResident() ? go("parts", {}) : go("daily", {});
        return go("home");
    }

    // ------------------------------------------------------------------
    // Residente (paquete 6): «Mi día» y bandejas
    // ------------------------------------------------------------------
    // Fotos de los avances: se piden con el token y quedan en memoria.
    const photoUrls = {};
    function photoUrl(id, size) {
        const key = `${id}:${size || "full"}`;
        if (photoUrls[key]) {
            return photoUrls[key] === "loading" || photoUrls[key] === "error" ? "" : photoUrls[key];
        }
        if (!state.online || !state.session) return "";
        photoUrls[key] = "loading";
        fetch(`${API}/photo/${state.projectId}/${id}${size ? "?size=" + size : ""}`, {
            headers: { Authorization: "Bearer " + state.session.token },
        })
            .then((r) => (r.ok ? r.blob() : Promise.reject(r.status)))
            .then((blob) => {
                photoUrls[key] = URL.createObjectURL(blob);
                render();
            })
            .catch(() => {
                photoUrls[key] = "error";
            });
        return "";
    }
    const photoBox = (id, label, size) => {
        const url = photoUrl(id, size || "thumb");
        return `<button class="thumb photo-btn" data-photo="${id}" style="${url ? `background-image:url(${url})` : ""}" aria-label="Ver ${esc(label)}">
            ${url ? "" : `<em>${state.online ? "Cargando…" : "Con señal"}</em>`}<span>${esc(label)}</span></button>`;
    };

    // «Mi día» (CR-48, U1): contadores y agenda de hoy por urgencia.
    function myDay(data, c) {
        const r = data.resident || { agenda: [] };
        const stat = (n, one, many, go, tab, accent) =>
            go
                ? `<button class="card stat" data-go="${go}" ${tab ? `data-tab-go="${tab}"` : ""}><b class="${accent && n ? "accent" : ""}">${n || 0}</b><small>${n === 1 ? one : many}</small></button>`
                : `<div class="card stat"><b>${n || 0}</b><small>${n === 1 ? one : many}</small></div>`;
        const AGENDA = { urgent: ["alert", "bad"], cutoff: ["doc", "warn"], delivery: ["truck", ""], start: ["chart", "ok"] };
        const agenda = (r.agenda || [])
            .map((item) => {
                const [ic, cls] = AGENDA[item.kind] || ["clock", ""];
                const target =
                    item.kind === "urgent" ? `data-go="inbox" data-tab-go="requests" data-id="${item.id}"`
                    : item.kind === "cutoff" ? `data-go="inbox" data-tab-go="progress"`
                    : item.kind === "delivery" ? `data-go="reception" data-id="${item.id}"`
                    : `data-go="partidas"`;
                return `<button class="agenda-row" ${target}><span class="${cls}">${svg(ic, 22)}</span><span class="grow"><b>${esc(item.title)}</b><small>${esc(item.kind === "cutoff" ? item.sub.replace(/(\d{4}-\d{2}-\d{2})/, (d) => dayMonth(d)) : item.sub)}</small></span>${svg("next", 18)}</button>`;
            })
            .join("");
        return `<div class="stats">${stat(c.inbox_progress, "por validar", "por validar", "inbox", "progress", true)}
            ${stat(c.inbox_requests, "por aprobar", "por aprobar", "inbox", "requests", true)}
            ${stat(c.daily_to_review, "parte por revisar", "partes por revisar", "parts", null, true)}</div>
            ${quickActions()}
            <h2>Hoy</h2>
            <div class="card list">${agenda || '<small class="muted">Nada urgente para hoy.</small>'}</div>`;
    }

    // Avisos de un avance (CR-49, punto 5).
    const warningPills = (row) =>
        (row.warnings || []).map((w) => `<small class="warn-line ${w.blocking ? "bad" : "warn"}">${svg("alert", 16)} ${esc(w.text)}</small>`).join("");
    const sendingNote = () =>
        state.online ? "" : `<p class="notice box">Sin señal: su decisión queda en «Por enviar» y Odoo la confirma al volver la conexión. Si el registro cambió, la rechaza con el motivo.</p>`;

    function progressCard(row, selected, picked) {
        const free = !(row.warnings || []).length;
        return `<div class="card inbox-card ${selected ? "on" : ""}">
            <div class="row top">${free ? `<input type="checkbox" class="pick-box" data-pick="${row.id}" ${picked ? "checked" : ""} aria-label="Elegir para validar en lote">` : ""}
            <button class="grow plain" data-go="inbox" data-tab-go="progress" data-id="${row.id}">
                <b class="clamp2">${esc(taskName(row))}${taskCode(row) ? ` · ${esc(taskCode(row))}` : ""}</b>
                <small>${esc(join(row.partner || row.reported_by, row.role_label))}</small>
                <small class="strong">${qtyText(row.qty)} ${esc(row.uom)} · ${esc(dayMonth(row.date))}${row.cutoff ? ` · corte ${esc(dayMonth(row.cutoff))}` : ""}${row.is_rework ? " · re-trabajo" : ""}</small>
                ${warningPills(row)}
            </button></div></div>`;
    }

    function progressDetail(row) {
        const d = (state.draft["val" + row.id] = state.draft["val" + row.id] || { qty: row.qty, reason: "", comment: "", mode: "" });
        const reasons = (state.data.resident.reasons || {});
        const corrected = d.qty < row.qty - 1e-6;
        const blocking = (row.warnings || []).some((w) => w.blocking);
        const options = (list, value) => `<option value="">Elija el motivo</option>${(list || []).map(([id, name]) => `<option value="${id}" ${String(value) === String(id) ? "selected" : ""}>${esc(name)}</option>`).join("")}`;
        const radius = state.data.project.radius_m;
        return `<div class="card detail">
            <div class="row between"><small class="eyebrow">${esc(row.name)}</small>${row.is_rework ? pill("Re-trabajo", "warn") : ""}</div>
            <b class="title">${esc(taskName(row))}${taskCode(row) ? ` · ${esc(taskCode(row))}` : ""}</b>
            <small>${esc(join(row.parent_label, row.role_label))}</small>
            <small>${esc(join("Reportó " + row.reported_by, row.partner, longDay(row.date)))}</small>
            <div class="grid4"><span>Plan<b>${qtyText(row.planned)}</b></span><span>Validado<b>${qtyText(row.validated)}</b></span>
            <span>Reportado<b class="warn">${qtyText(row.qty)}</b></span><span>Saldo ${esc(row.uom)}<b class="accent">${qtyText(row.balance)}</b></span></div>
            ${warningPills(row)}
            <b>Evidencia</b>
            <div class="photos">${row.photos.map((ph, i) => photoBox(ph.id, `Foto ${i + 1} · ${clock(ph.taken)}`)).join("")}
            ${row.last_photo ? photoBox(row.last_photo.id, `Última validada · ${dayMonth(row.last_photo.date)}`) : ""}</div>
            <small class="gps ${row.has_gps ? (radius && row.distance_m > radius ? "warn" : "ok") : "warn"}">${svg("pin", 18)} ${
                row.has_gps ? `A ${row.distance_m} m de la obra${radius ? ` (radio ${radius} m)` : ""}` : "Sin ubicación GPS"
            }</small>
        </div>
        <div class="card form">
            <b>Cantidad a validar</b>
            <div class="stepper"><button data-valqty="${row.id}" data-delta="-1" aria-label="Restar">−</button>
            <input type="number" step="0.01" min="0" max="${row.qty}" inputmode="decimal" data-bind="val${row.id}.qty" value="${d.qty}" aria-label="Cantidad a validar">
            <button data-valqty="${row.id}" data-delta="1" aria-label="Sumar">+</button></div>
            <small>Solo se corrige a la baja; reportado ${qtyText(row.qty)} ${esc(row.uom)}.</small>
            ${corrected ? `<label>Motivo de la corrección<select data-bind="val${row.id}.reason">${options(reasons.progress_correct, d.reason)}</select></label>` : ""}
            ${
                d.mode === "reject"
                    ? `<label>Motivo del rechazo<select data-bind="val${row.id}.reason">${options(reasons.progress_reject, d.reason)}</select></label>`
                    : d.mode === "rework"
                    ? `<label>Motivo del re-trabajo<select data-bind="val${row.id}.rework">${`<option value="">Elija el motivo</option>` + (state.data.rework_reasons || []).map(([code, label]) => `<option value="${code}" ${d.rework === code ? "selected" : ""}>${esc(label)}</option>`).join("")}</select></label>
                       <small>El re-trabajo se valida con 0 a liquidar, como en el escritorio.</small>`
                    : ""
            }
            <label>Comentario<textarea rows="2" data-bind="val${row.id}.comment" placeholder="Opcional; puede dictarlo con el micrófono del teclado">${esc(d.comment)}</textarea></label>
        </div>
        ${sendingNote()}
        ${state.params.error ? `<p class="error">${esc(state.params.error)}</p>` : ""}
        <div class="action-bar">${
            d.mode
                ? `<button class="secondary" data-set="val${row.id}.mode=">Volver</button>
                   <button class="primary ${d.mode === "reject" ? "danger" : ""}" data-action="resident-progress" data-id="${row.id}" data-kind="${d.mode}">${d.mode === "reject" ? "Rechazar" : "Validar como re-trabajo"}</button>`
                : `<button class="secondary" data-set="val${row.id}.mode=reject">Rechazar</button>
                   <button class="secondary" data-set="val${row.id}.mode=rework">Re-trabajo</button>
                   <button class="primary" data-action="resident-progress" data-id="${row.id}" data-kind="validate" ${blocking ? "disabled" : ""}>Validar</button>`
        }</div>`;
    }

    function requestCard(row, selected) {
        const kinds = { partida: "De partida", epp: "EPP", office: "Útiles y aseo", text: "Fuera de catálogo", internal: "Interno" };
        return `<button class="card inbox-card plain ${selected ? "on" : ""}" data-go="inbox" data-tab-go="requests" data-id="${row.id}">
            <div class="row between"><b>${esc(row.name)}</b>${row.urgent ? pill("Urgente", "bad") : ""}</div>
            <small>${esc(join(kinds[row.kind] || row.type_label, "pidió " + row.requested_by))}</small>
            <small>${esc(join(`${row.lines.length} ${row.lines.length === 1 ? "línea" : "líneas"}`, row.date_required ? "para el " + dayMonth(row.date_required) : ""))}</small>
            ${row.lines.some((l) => l.excess > 0 || l.out_of_plan) ? `<small class="warn-line warn">${svg("alert", 16)} Con exceso o fuera del plan</small>` : ""}
        </button>`;
    }

    function requestDetail(row) {
        const d = (state.draft["apr" + row.id] = state.draft["apr" + row.id] || {
            qty: Object.fromEntries(row.lines.map((l) => [l.id, l.qty])), reason: "", comment: "", mode: "",
        });
        const reasons = (state.data.resident.reasons || {}).request_reject || [];
        return `<div class="card detail">
            <div class="row between"><b class="title">${esc(row.name)}</b>${row.urgent ? pill("Urgente", "bad") : ""}</div>
            <small>${esc(join(row.type_label, "pidió " + row.requested_by, row.date_required ? "para el " + dayMonth(row.date_required) : ""))}</small>
            ${row.note ? `<p class="muted note">${esc(row.note)}</p>` : ""}
        </div>
        ${row.lines
            .map((l) => {
                const value = d.qty[l.id];
                const hasPlan = l.plan_remaining !== null && l.plan_remaining !== undefined;
                const balance = hasPlan ? Math.max(0, Math.min(l.qty, l.plan_remaining)) : null;
                return `<div class="card req-line">
                    <b>${esc(l.name)}</b>
                    <small>${esc(join(l.task_code ? `${l.task_name} · ${l.task_code}` : l.task_name, `pedido ${qtyText(l.qty)} ${l.uom}`))}</small>
                    ${hasPlan ? `<small>Saldo del plan <b>${qtyText(l.plan_remaining)} ${esc(l.uom)}</b>${l.excess > 0 ? ` · <span class="bad">exceso ${qtyText(l.excess)}</span>` : ""}</small>` : l.out_of_plan ? `<small class="bad">Fuera del plan</small>` : ""}
                    <div class="row between"><div class="pills">
                        <button class="pill-btn ${Math.abs(value - l.qty) < 1e-6 ? "ok" : ""}" data-aprset="${row.id}:${l.id}:${l.qty}">Lo pedido</button>
                        ${balance !== null && balance > 0 && balance < l.qty ? `<button class="pill-btn ${Math.abs(value - balance) < 1e-6 ? "ok" : ""}" data-aprset="${row.id}:${l.id}:${balance}">El saldo</button>` : ""}
                    </div>${stepper(`data-aprqty="${row.id}:${l.id}"`, value, "Cantidad aprobada", true)}</div>
                </div>`;
            })
            .join("")}
        ${
            d.mode === "reject"
                ? `<div class="card form"><label>Motivo del rechazo<select data-bind="apr${row.id}.reason"><option value="">Elija el motivo</option>${reasons
                      .map(([id, name]) => `<option value="${id}" ${String(d.reason) === String(id) ? "selected" : ""}>${esc(name)}</option>`)
                      .join("")}</select></label>
                   <label>Comentario<textarea rows="2" data-bind="apr${row.id}.comment" placeholder="Opcional; puede dictarlo con el micrófono del teclado">${esc(d.comment)}</textarea></label></div>`
                : `<div class="card form"><label>Comentario<textarea rows="2" data-bind="apr${row.id}.comment" placeholder="Opcional">${esc(d.comment)}</textarea></label></div>`
        }
        ${sendingNote()}
        ${state.params.error ? `<p class="error">${esc(state.params.error)}</p>` : ""}
        <div class="action-bar sticky">${
            d.mode === "reject"
                ? `<button class="secondary" data-set="apr${row.id}.mode=">Volver</button>
                   <button class="primary danger" data-action="resident-request" data-id="${row.id}" data-kind="reject">Rechazar</button>`
                : `<button class="secondary" data-set="apr${row.id}.mode=reject">Rechazar</button>
                   <button class="primary" data-action="resident-request" data-id="${row.id}" data-kind="approve">Aprobar</button>`
        }</div>`;
    }

    // Bandejas (CR-49 y CR-50): lista y, en la tablet, el detalle al lado (U6).
    screens.inbox = () => {
        const r = (state.data && state.data.resident) || { progress: [], requests: [] };
        const tab = state.params.tab || (r.progress.length || !r.requests.length ? "progress" : "requests");
        const id = Number(state.params.id) || 0;
        const tabs = [["progress", `Por validar (${r.progress.length})`], ["requests", `Por aprobar (${r.requests.length})`]];
        let list = "";
        let detail = "";
        if (tab === "progress") {
            const order = state.params.order || "cutoff";
            let rows = r.progress.slice();
            if (order === "item") rows.sort((a, b) => (taskName(a) + taskCode(a)).localeCompare(taskName(b) + taskCode(b)) || a.id - b.id);
            if (order === "warn") rows = rows.filter((x) => (x.warnings || []).length);
            const picked = state.draft.picked || [];
            const chip = (key, label) => `<button class="chip ${order === key ? "on" : ""}" data-order="${key}" aria-pressed="${order === key}">${label}</button>`;
            list = `<div class="chips">${chip("cutoff", "Por corte")}${chip("item", "Por partida")}${chip("warn", "Con aviso")}</div>
                ${rows.map((row) => progressCard(row, row.id === id, picked.includes(row.id))).join("") || '<p class="muted">No hay avances por validar.</p>'}
                ${picked.length ? `<button class="primary" data-action="resident-batch">Validar seleccionados (${picked.length})</button>` : ""}`;
            const row = r.progress.find((x) => x.id === id);
            detail = row ? progressDetail(row) : "";
        } else {
            list = r.requests.map((row) => requestCard(row, row.id === id)).join("") || '<p class="muted">No hay requerimientos por aprobar.</p>';
            const row = r.requests.find((x) => x.id === id);
            detail = row ? requestDetail(row) : "";
        }
        const back = detail ? `<button class="link only-phone" data-go="inbox" data-tab-go="${tab}">‹ Volver a la lista</button>` : "";
        return `${header("Bandejas", join(projectParts().code, state.data ? "datos del " + clock(String(state.data.synced_at).replace(" ", "T") + "Z") : ""), "home")}
            <div class="tabs" role="tablist">${tabs.map(([key, label]) => `<button role="tab" aria-selected="${tab === key}" class="${tab === key ? "on" : ""}" data-go="inbox" data-tab-go="${key}">${label}</button>`).join("")}</div>
            <main class="page split ${detail ? "has-detail" : ""}">
                <section class="split-list">${state.params.flash ? `<p class="hint">${esc(state.params.flash)}</p>` : ""}${list}</section>
                <section class="split-detail">${back}${detail || '<p class="muted only-tablet">Elija un registro de la lista.</p>'}</section>
            </main>${photoOverlay()}${nav("inbox")}`;
    };

    function photoOverlay() {
        if (!state.params.photo) return "";
        const url = photoUrl(state.params.photo);
        return `<div class="overlay" role="dialog" aria-label="Foto"><button class="icon-btn close" data-photo-close="1" aria-label="Cerrar">${svg("close")}</button>
            ${url ? `<img src="${url}" alt="Foto del avance">` : `<p>${state.online ? "Cargando la foto…" : "La foto se ve con señal."}</p>`}</div>`;
    }

    // Lo decidido sale de la bandeja en el equipo; Odoo lo confirma al recibirlo.
    function dropFromInbox(kind, ids) {
        const r = state.data.resident;
        r[kind] = r[kind].filter((x) => !ids.includes(x.id));
        const c = state.data.counters;
        c.inbox_progress = r.progress.length;
        c.inbox_requests = r.requests.length;
        cachePut("sync:" + state.projectId, state.data);
    }

    // ------------------------------------------------------------------
    // Residente, entrega 2: partes del día, cambio del cliente, deductivo y
    // solicitudes de contrata o cuadrilla (paquete 6, CR-51 a CR-53, CR-56)
    // ------------------------------------------------------------------
    const resident = () => (state.data && state.data.resident) || {};
    const features = () => resident().features || {};
    // Partidas de la obra (una por tarea), nombre primero y código al final.
    function taskOptions() {
        const seen = new Map();
        ((state.data && state.data.partidas) || []).forEach((p) => {
            if (p.task_id && !seen.has(p.task_id)) seen.set(p.task_id, p);
        });
        return [...seen.values()].sort((a, b) => taskName(a).localeCompare(taskName(b)));
    }
    function taskPicker(key, selected) {
        const q = (state.params.tq || "").toLowerCase();
        const rows = taskOptions().filter((p) => selected.includes(p.task_id) || matches(q, taskName(p), taskCode(p), p.parent_label));
        return `<label class="search">${svg("search", 20)}<input type="search" placeholder="Buscar partida" value="${esc(state.params.tq || "")}" data-input="tq" aria-label="Buscar partida"></label>
            <div class="card list pick-list">${rows
                .slice(0, 40)
                .map((p) => `<label class="pick"><input type="checkbox" data-taskpick="${key}:${p.task_id}" ${selected.includes(p.task_id) ? "checked" : ""}>
                    <span class="grow"><b>${esc(taskName(p))}${taskCode(p) ? ` · ${esc(taskCode(p))}` : ""}</b><small>${esc(p.parent_label || "")}</small></span></label>`)
                .join("") || '<small class="muted">Sin partidas.</small>'}</div>`;
    }
    function signatureCard(key, title) {
        const d = state.draft[key];
        return `<div class="card form"><b>${esc(title)}</b><div class="sign-wrap"><canvas id="signature" data-sign="${key}" class="signature" width="340" height="140" aria-label="Firma"></canvas>
            ${d.signature ? "" : '<span class="sign-hint" aria-hidden="true">Firme con el dedo aquí</span>'}</div>
            <button class="link" data-clear-sign="${key}">Borrar la firma</button></div>`;
    }

    // U13: registros del residente a un toque desde el inicio.
    function quickActions() {
        const f = features();
        const items = [
            f.change_order && ["change", "doc", "Cambio del cliente"],
            f.deduction && ["deduction", "undo", "Deductivo"],
            f.crew_request && ["crewreq", "crew", "Pedir cuadrilla o contrata"],
            f.expense && ["expense", "doc", "Gasto con mi fondo"],
        ].filter(Boolean);
        return items.length
            ? `<div class="quick">${items.map(([go, ic, label]) => `<button class="quick-btn" data-go="${go}">${svg(ic, 22)}<span>${label}</span></button>`).join("")}</div>`
            : "";
    }

    // CR-56 (U10, U16): partes del día y parte diario de obra.
    screens.parts = () => {
        const p = resident().parts || { reports: [], missing: [] };
        const id = Number(state.params.id) || 0;
        const d = (state.draft.closeDay = state.draft.closeDay || { comment: (p.site && p.site.comment) || "" });
        const closed = p.site && p.site.state === "closed";
        const card = (r) => `<button class="card inbox-card plain ${r.id === id ? "on" : ""}" data-go="parts" data-id="${r.id}">
            <div class="row between"><b>${esc(r.name)}</b>${pill(r.state === "sent" ? "Por revisar" : "Revisado", r.state === "sent" ? "warn" : "ok")}</div>
            <small>${esc(join(r.role, r.partner, "a las " + clock(String(r.sent_at).replace(" ", "T") + "Z")))}</small>
            <small>${esc(join(`${r.staff_total} personas`, r.restrictions.join(", ")))}</small></button>`;
        const row = p.reports.find((r) => r.id === id);
        const detail = row
            ? `<div class="card detail"><b class="title">${esc(row.name)}</b><small>${esc(join(row.role, row.partner, row.weather))}</small>
                ${row.staff.map((s) => `<div class="kv"><span>${esc(s.name)}</span><b>${s.count}</b></div>`).join("")}
                ${row.restrictions.length ? `<small class="warn-line warn">${svg("alert", 16)} ${esc(row.restrictions.join(", "))}</small>` : ""}
                ${row.occurrences ? `<p class="note">${esc(row.occurrences)}</p>` : ""}
                ${row.photos.length ? `<div class="photos">${row.photos.map((ph, i) => photoBox(ph.id, `Foto ${i + 1}`)).join("")}</div>` : ""}</div>`
            : "";
        const summary = `<div class="card"><small class="eyebrow">Parte diario de obra · ${esc(longDay(p.date))}</small>
            <div class="grid4"><span>Partes<b>${p.reports.length}</b></span><span>Sin parte<b class="${p.missing.length ? "warn" : ""}">${p.missing.length}</b></span>
            <span>Validados<b>${p.validated || 0}</b></span><span>Por validar<b class="warn">${p.pending || 0}</b></span></div>
            <small>${esc(join(`Asistencia propia de hoy: ${p.own_today || 0}`, p.client_contact ? "se envía a " + p.client_contact : "la obra no tiene contacto del cliente: el PDF queda en la obra"))}</small></div>
            ${p.missing.length ? `<div class="card list">${p.missing.map((m) => `<div class="queue-row"><span class="dot" aria-hidden="true"></span><div class="grow"><b>${esc(m.name)}</b><small>${esc(join(m.role, m.partner, "sin parte"))}</small></div></div>`).join("")}</div>` : ""}
            ${
                closed
                    ? `<p class="hint">El día ya se cerró y se envió.</p>`
                    : `<div class="card form"><label>Comentario del residente<textarea rows="3" data-bind="closeDay.comment" placeholder="Puede dictarlo con el micrófono del teclado">${esc(d.comment)}</textarea></label></div>
                       ${sendingNote()}${state.params.error ? `<p class="error">${esc(state.params.error)}</p>` : ""}
                       <button class="primary" data-action="close-day">Cerrar el día y enviar al cliente</button>`
            }`;
        return `${header("Partes del día", join(projectParts().code, longDay(p.date)), "home")}
            <main class="page split ${row ? "has-detail" : ""}">
                <section class="split-list">${state.params.flash ? `<p class="hint">${esc(state.params.flash)}</p>` : ""}${p.reports.map(card).join("") || '<p class="muted">Aún no llegan partes hoy.</p>'}${summary}</section>
                <section class="split-detail">${row ? `<button class="link only-phone" data-go="parts">‹ Volver a los partes</button>` : ""}${detail || '<p class="muted only-tablet">Elija un parte para ver el detalle.</p>'}</section>
            </main>${photoOverlay()}${nav("home")}`;
    };

    // CR-53 (U11): cambio pedido por el cliente, con su firma.
    screens.change = () => {
        const d = (state.draft.change = state.draft.change || {
            kind: "additional", description: "", task_ids: [], new_item: "", qty_estimate: "", rep_name: "", rep_role: "", photos: [], signature: "",
        });
        return `${header("Cambio del cliente", projectParts().code, "home")}
            <main class="page">
                <div class="card form">
                    <div class="toggle"><button class="${d.kind === "additional" ? "on" : ""}" data-set="change.kind=additional" aria-pressed="${d.kind === "additional"}">Adicional</button>
                    <button class="${d.kind === "deductive" ? "on" : ""}" data-set="change.kind=deductive" aria-pressed="${d.kind === "deductive"}">Deductivo</button></div>
                    <label>Qué pide el cliente<textarea rows="3" data-bind="change.description" placeholder="Puede dictarlo con el micrófono del teclado">${esc(d.description)}</textarea></label>
                </div>
                <h2>Partidas afectadas</h2>
                ${taskPicker("change", d.task_ids)}
                <div class="card form">
                    <label>O partida nueva<input data-bind="change.new_item" value="${esc(d.new_item)}" placeholder="Lo que no está en el presupuesto"></label>
                    <label>Metrado estimado<input data-bind="change.qty_estimate" value="${esc(d.qty_estimate)}" placeholder="Ej.: 12 m²"></label>
                </div>
                ${photosCard("change", d, true)}
                <div class="card form">
                    <label>Lo pidió (nombre)<input data-bind="change.rep_name" value="${esc(d.rep_name)}" autocomplete="off"></label>
                    <label>Cargo<input data-bind="change.rep_role" value="${esc(d.rep_role)}" placeholder="Ej.: supervisor del cliente"></label>
                </div>
                ${signatureCard("change", "Firma de quien lo pidió")}
                <p class="hint">Queda en borrador: lo valoriza el coordinador en Odoo. Al llegar a Odoo, el cliente recibe la constancia en PDF.</p>
                ${sendingNote()}${state.params.error ? `<p class="error">${esc(state.params.error)}</p>` : ""}
                <button class="primary" data-action="save-change">Registrar el cambio</button>
            </main>`;
    };

    // CR-51: deductivo de contrata con foto.
    screens.deduction = () => {
        const r = resident();
        const orders = r.orders || [];
        const d = (state.draft.deduction = state.draft.deduction || {
            order: orders.length === 1 ? String(orders[0].id) : "", line: "", type: "", mode: "amount", amount: "", qty: "", description: "", photos: [],
        });
        const order = orders.find((o) => String(o.id) === String(d.order));
        const line = order && order.lines.find((l) => String(l.id) === String(d.line));
        return `${header("Deductivo de contrata", projectParts().code, "home")}
            <main class="page">
                <div class="card form">
                    <label>Contrata y orden<select data-bind="deduction.order" data-rerender="1"><option value="">Elija la orden</option>${orders
                        .map((o) => `<option value="${o.id}" ${String(o.id) === String(d.order) ? "selected" : ""}>${esc(o.partner)} · ${esc(o.name)}</option>`)
                        .join("")}</select></label>
                    ${order ? `<label>Partida<select data-bind="deduction.line" data-rerender="1"><option value="">Sin partida</option>${order.lines
                        .map((l) => `<option value="${l.id}" ${String(l.id) === String(d.line) ? "selected" : ""}>${esc(join(l.task_name, l.task_code))}</option>`)
                        .join("")}</select></label>` : ""}
                    <label>Motivo<select data-bind="deduction.type"><option value="">Elija el motivo</option>${(r.deduction_types || [])
                        .map(([id, name]) => `<option value="${id}" ${String(id) === String(d.type) ? "selected" : ""}>${esc(name)}</option>`)
                        .join("")}</select></label>
                    ${line ? `<div class="toggle"><button class="${d.mode === "amount" ? "on" : ""}" data-set="deduction.mode=amount">Monto</button><button class="${d.mode === "qty" ? "on" : ""}" data-set="deduction.mode=qty">Cantidad (${esc(line.uom)})</button></div>` : ""}
                    ${
                        line && d.mode === "qty"
                            ? `<label>Cantidad<input type="number" inputmode="decimal" step="0.01" min="0" data-bind="deduction.qty" value="${esc(d.qty)}"></label>`
                            : `<label>Monto sin IGV<input type="number" inputmode="decimal" step="0.01" min="0" data-bind="deduction.amount" value="${esc(d.amount)}"></label>`
                    }
                    <label>Descripción<textarea rows="2" data-bind="deduction.description" placeholder="Qué no hizo o qué se descuenta">${esc(d.description)}</textarea></label>
                </div>
                ${photosCard("deduction", d, true)}
                <p class="hint">Queda pendiente y entra en la siguiente valorización de la contrata, como el del escritorio.</p>
                ${sendingNote()}${state.params.error ? `<p class="error">${esc(state.params.error)}</p>` : ""}
                <button class="primary" data-action="save-deduction">Registrar el deductivo</button>
            </main>`;
    };

    // CR-55: caja chica y entrega a rendir del residente.
    screens.expense = () => {
        const cash = resident().cash || { funds: [], doc_types: [] };
        const funds = cash.funds || [];
        const d = (state.draft.expense = state.draft.expense || {
            fund: funds.length ? String(funds[0].id) : "", doc_type: "", ruc: "", number: "", date: today(), amount: "",
            general: false, task_ids: [], description: "", photos: [], picked: [],
        });
        const fund = funds.find((f) => String(f.id) === String(d.fund));
        const head = header("Gasto con mi fondo", projectParts().code, "home");
        if (!funds.length) {
            return `${head}<main class="page"><p class="muted">No tiene una caja chica ni una entrega a rendir entregada. Pídala a Contabilidad.</p></main>`;
        }
        const cur = (n) => `${fund.currency} ${num(n)}`;
        const pending = fund.receipts.filter((r) => r.state === "registered");
        const cls = { registered: "warn", sent: "", approved: "ok" };
        return `${head}
            <main class="page">
                ${funds.length > 1 ? `<div class="card form"><label>Fondo<select data-bind="expense.fund" data-rerender="1">${funds
                    .map((f) => `<option value="${f.id}" ${String(f.id) === String(d.fund) ? "selected" : ""}>${esc(join(f.type_label, f.name))}</option>`)
                    .join("")}</select></label></div>` : ""}
                <div class="card"><small class="eyebrow">${esc(join(fund.type_label, fund.name))}</small>
                    <div class="grid4"><span>Entregado<b>${cur(fund.delivered)}</b></span><span>Rendido<b>${cur(fund.sent)}</b></span>
                    <span>Aprobado<b class="ok">${cur(fund.approved)}</b></span><span>Por rendir<b class="accent">${cur(fund.balance)}</b></span></div>
                    ${fund.overdue ? `<small class="warn-line bad">${svg("alert", 16)} Rendición vencida desde el ${esc(dayMonth(fund.date_due))}</small>` : fund.date_due ? `<small>Rendir hasta el ${esc(dayMonth(fund.date_due))}</small>` : ""}</div>
                <h2>Registrar un comprobante</h2>
                ${photosCard("expense", d, true, "Foto del comprobante")}
                <div class="card form">
                    <label>Tipo de comprobante<select data-bind="expense.doc_type"><option value="">Elija el tipo</option>${(cash.doc_types || [])
                        .map(([id, name]) => `<option value="${id}" ${String(id) === String(d.doc_type) ? "selected" : ""}>${esc(name)}</option>`)
                        .join("")}</select></label>
                    <label>RUC del emisor<input inputmode="numeric" maxlength="11" data-bind="expense.ruc" value="${esc(d.ruc)}" placeholder="11 dígitos"></label>
                    <label>Serie y número<input data-bind="expense.number" value="${esc(d.number)}" placeholder="Ej.: B001-123" autocapitalize="characters"></label>
                    <label>Fecha<input type="date" data-bind="expense.date" value="${esc(d.date)}" max="${today()}"></label>
                    <label>Monto total<input type="number" inputmode="decimal" step="0.01" min="0" data-bind="expense.amount" value="${esc(d.amount)}"></label>
                    <label>Qué se compró<input data-bind="expense.description" value="${esc(d.description)}" placeholder="Opcional"></label>
                    <label class="check"><input type="checkbox" data-bind="expense.general" data-rerender="1" ${d.general ? "checked" : ""}> Gastos generales de la obra (sin partida)</label>
                </div>
                ${d.general ? "" : `<h2>Partida</h2>${taskPicker("expense", d.task_ids)}`}
                ${sendingNote()}${state.params.error ? `<p class="error">${esc(state.params.error)}</p>` : ""}
                <button class="primary" data-action="save-expense">Registrar el comprobante</button>
                <h2>Mis comprobantes</h2>
                <div class="card list">${fund.receipts
                    .map((r) => `<label class="pick">${r.state === "registered" ? `<input type="checkbox" data-settlepick="${r.id}" ${d.picked.includes(r.id) ? "checked" : ""}>` : ""}
                        <span class="grow"><b>${esc(join(r.number, r.partner))}</b><small>${esc(join(r.doc_type, dayMonth(r.date), r.task))}</small></span>
                        <span class="right"><b>${cur(r.amount)}</b>${pill(r.state_label, cls[r.state])}</span></label>`)
                    .join("") || '<small class="muted">Aún no registra comprobantes con este fondo.</small>'}</div>
                ${pending.length ? `<button class="secondary" data-action="settle" ${d.picked.length ? "" : "disabled"}>Rendir ${d.picked.length || ""} ${d.picked.length === 1 ? "comprobante" : "comprobantes"}</button>
                    <small class="muted center">Marque los comprobantes por rendir. Contabilidad los revisa y aprueba la rendición.</small>` : ""}
            </main>`;
    };

    // CR-52: solicitud de contrata o cuadrilla adicional.
    screens.crewreq = () => {
        const d = (state.draft.crewreq = state.draft.crewreq || {
            kind: "crew", task_ids: [], date_needed: today(), people: [{ role: "operario", count: 1 }], scope: "", comment: "",
        });
        const mine = resident().crew_requests || [];
        const cls = { assigned: "ok", requested: "warn", cancelled: "" };
        return `${header("Pedir cuadrilla o contrata", projectParts().code, "home")}
            <main class="page">
                <div class="toggle"><button class="${d.kind === "crew" ? "on" : ""}" data-set="crewreq.kind=crew">Cuadrilla adicional</button>
                <button class="${d.kind === "contract" ? "on" : ""}" data-set="crewreq.kind=contract">Contrata</button></div>
                <h2>Partidas</h2>
                ${taskPicker("crewreq", d.task_ids)}
                <div class="card form">
                    <label>Se necesita el<input type="date" data-bind="crewreq.date_needed" value="${esc(d.date_needed)}" min="${today()}"></label>
                    ${
                        d.kind === "crew"
                            ? d.people.map((p, i) => `<div class="row staff"><input class="grow" data-bind="crewreq.people.${i}.role" value="${esc(p.role)}" aria-label="Rol">${stepper(`data-person="${i}"`, p.count, "Personas", true)}</div>`).join("") +
                              `<button class="link" data-action="add-person">+ Agregar otro rol</button>`
                            : `<label>Metrado que hará la contrata<input data-bind="crewreq.scope" value="${esc(d.scope)}" placeholder="Ej.: 120 m² de tarrajeo"></label>`
                    }
                    <label>Comentario<textarea rows="2" data-bind="crewreq.comment">${esc(d.comment)}</textarea></label>
                </div>
                <p class="hint">Le llega al planificador de la obra como actividad en la partida; la asignación la hace en Odoo.</p>
                ${sendingNote()}${state.params.error ? `<p class="error">${esc(state.params.error)}</p>` : ""}
                <button class="primary" data-action="save-crewreq">Enviar la solicitud</button>
                ${mine.length ? `<h2>Mis solicitudes</h2><div class="card list">${mine
                    .map((m) => `<div class="queue-row"><div class="grow"><div class="row between"><b>${esc(m.kind_label.charAt(0).toUpperCase() + m.kind_label.slice(1))} · ${esc(dayMonth(m.date_needed))}</b>${pill(m.state_label, cls[m.state])}</div>
                        <small>${esc(join(m.detail, m.tasks.join(", ")))}</small></div></div>`)
                    .join("")}</div>` : ""}
            </main>`;
    };

    // ------------------------------------------------------------------
    // Obra en el portal del residente (paquete 6, CR-58 y CR-54): Resumen,
    // Semana, Tareas y Gantt, de solo lectura y con los datos de la última
    // sincronización.
    // ------------------------------------------------------------------
    const pct = (value) => `${Math.round(100 * (value || 0))} %`;
    // Programado y real: azul y naranja de la paleta validada (contraste y
    // daltonismo); la línea discontinua y la leyenda los distinguen sin color.
    const SERIES = { real: "#2a78d6", programmed: "#eb6834" };
    const COLUMNS = [
        ["todo", "Por iniciar"],
        ["doing", "En curso"],
        ["ending", "Por terminar esta semana"],
        ["done", "Terminadas"],
    ];

    function siteCurve(curve) {
        if (!curve.length) return "";
        const w = 340, h = 160, pad = { l: 34, r: 10, t: 10, b: 22 };
        const x = (i) => pad.l + (i * (w - pad.l - pad.r)) / Math.max(1, curve.length - 1);
        const y = (v) => pad.t + (1 - v) * (h - pad.t - pad.b);
        const path = (key) => curve
            .map((p, i) => (p[key] === null || p[key] === undefined ? null : `${x(i).toFixed(1)},${y(p[key]).toFixed(1)}`))
            .filter(Boolean).join(" L ");
        const grid = [0, 0.5, 1].map((v) => `<line x1="${pad.l}" x2="${w - pad.r}" y1="${y(v)}" y2="${y(v)}" class="grid"/><text x="${pad.l - 6}" y="${y(v) + 4}" text-anchor="end" class="axis">${v * 100}%</text>`).join("");
        const first = curve[0].week, last = curve[curve.length - 1].week;
        const todayIndex = curve.findIndex((p) => p.week >= today());
        const realPts = curve.filter((p) => p.real !== null && p.real !== undefined);
        const lastReal = realPts[realPts.length - 1];
        const hits = curve.map((p, i) => `<rect x="${x(i) - 8}" y="${pad.t}" width="16" height="${h - pad.t - pad.b}" class="hit"><title>Semana al ${dayMonth(p.week)} · programado ${pct(p.programmed)}${p.real === null || p.real === undefined ? "" : ` · real ${pct(p.real)}`}</title></rect>`).join("");
        return `<svg viewBox="0 0 ${w} ${h}" class="chart" role="img" aria-label="Curva de avance programado y real">
            ${grid}
            ${todayIndex >= 0 ? `<line x1="${x(todayIndex)}" x2="${x(todayIndex)}" y1="${pad.t}" y2="${h - pad.b}" class="today"/>` : ""}
            <path d="M ${path("programmed")}" fill="none" stroke="${SERIES.programmed}" stroke-width="2" stroke-dasharray="5 4"/>
            <path d="M ${path("real")}" fill="none" stroke="${SERIES.real}" stroke-width="2"/>
            ${lastReal ? `<circle cx="${x(curve.indexOf(lastReal))}" cy="${y(lastReal.real)}" r="4" fill="${SERIES.real}" stroke="#fff" stroke-width="2"/>` : ""}
            <text x="${pad.l}" y="${h - 6}" class="axis">${dayMonth(first)}</text><text x="${w - pad.r}" y="${h - 6}" text-anchor="end" class="axis">${dayMonth(last)}</text>
            ${hits}</svg>
            <div class="legend"><span><i class="swatch" style="background:${SERIES.real}"></i>Real validado</span><span><svg width="16" height="8" aria-hidden="true"><line x1="0" x2="16" y1="4" y2="4" stroke="${SERIES.programmed}" stroke-width="2" stroke-dasharray="4 3"/></svg>Programado</span></div>
            <details class="table-view"><summary>Ver como tabla</summary><table class="lines"><thead><tr><th>Semana al</th><th>Programado</th><th>Real</th></tr></thead><tbody>${curve
                .map((p) => `<tr><td>${esc(dayMonth(p.week))}</td><td>${pct(p.programmed)}</td><td>${p.real === null || p.real === undefined ? "—" : pct(p.real)}</td></tr>`)
                .join("")}</tbody></table></details>`;
    }

    function pairBar(real, programmed) {
        return `<div class="pair-bar" title="Real ${pct(real)} · programado ${pct(programmed)}"><div class="bar-bg"><div class="bar-fill real" style="width:${Math.min(100, 100 * real)}%"></div></div>
            <div class="bar-bg thin"><div class="bar-fill programmed" style="width:${Math.min(100, 100 * programmed)}%"></div></div></div>`;
    }

    function siteTaskCard(t, compact) {
        const who = t.partners.length ? t.partners.join(", ") : t.own_staff ? "Personal propio" : "";
        return `<button class="card task-card plain" data-task="${t.id}">
            <b class="clamp2">${esc(t.task_name)}${t.task_code ? ` · ${esc(t.task_code)}` : ""}</b>
            ${compact ? "" : `<small>${esc(join(who, t.start ? `${dayMonth(t.start)} → ${dayMonth(t.end)}` : "sin fechas"))}</small>`}
            <div class="bar-bg"><div class="bar-fill" style="width:${Math.min(100, 100 * t.progress)}%"></div></div>
            <small class="row between"><span>${pct(t.progress)} validado</span>${t.late ? `<span class="strong bad">${svg("alert", 14)} atrasada ${t.late_days} d</span>` : t.warning ? `<span class="strong warn">${esc(t.warning)}</span>` : ""}</small>
        </button>`;
    }

    function siteGantt(site) {
        const zoom = state.params.zoom || "week";
        const perDay = zoom === "week" ? 22 : 6;
        const rows = site.tasks.filter((t) => t.start && t.end);
        if (!rows.length) return '<p class="muted">Las partidas no tienen fechas en el plan.</p>';
        const day0 = asDate(site.start || rows[0].start);
        const days = (iso) => Math.round((asDate(iso) - day0) / 86400000);
        const span = Math.max(...rows.map((t) => days(t.end))) + 7;
        const rowH = 30, labelW = 0, top = 26;
        const width = labelW + span * perDay;
        const height = top + rows.length * rowH + 10;
        const ticks = [];
        for (let d = 0; d <= span; d += zoom === "week" ? 7 : 30) {
            const iso = new Date(day0.getTime() + d * 86400000).toISOString().slice(0, 10);
            ticks.push(`<line x1="${d * perDay}" x2="${d * perDay}" y1="${top - 6}" y2="${height}" class="grid"/><text x="${d * perDay + 3}" y="${top - 10}" class="axis">${esc(dayMonth(iso))}</text>`);
        }
        const todayX = days(today()) * perDay;
        const bars = rows
            .map((t, i) => {
                const x = days(t.start) * perDay;
                const w = Math.max(perDay, (days(t.end) - days(t.start) + 1) * perDay);
                const y = top + i * rowH + 6;
                return `<g class="gantt-row"><title>${esc(t.task_name)} · ${dayMonth(t.start)} → ${dayMonth(t.end)} · ${pct(t.progress)} validado${t.late ? ` · atrasada ${t.late_days} d` : ""}</title>
                    <rect x="${x}" y="${y}" width="${w}" height="18" rx="4" class="track ${t.late ? "late" : ""}"/>
                    <rect x="${x}" y="${y}" width="${(w * Math.min(1, t.progress)).toFixed(1)}" height="18" rx="4" fill="${SERIES.real}"/></g>`;
            })
            .join("");
        const milestones = (site.milestones || [])
            .map((m) => {
                const mx = days(m.date) * perDay;
                return `<g><title>Hito: ${esc(m.name)} · ${dayMonth(m.date)}${m.reached ? " · alcanzado" : ""}</title><path d="M ${mx} ${top - 4} l 6 6 l -6 6 l -6 -6 z" class="milestone ${m.reached ? "reached" : ""}"/><text x="${mx + 9}" y="${top + 6}" class="axis">${esc(m.name.length > 24 ? m.name.slice(0, 23) + "…" : m.name)}</text></g>`;
            })
            .join("");
        const labels = rows
            .map((t) => `<div class="gantt-label ${t.late ? "late" : ""}" style="height:${rowH}px"><span class="clamp1">${esc(t.task_name)}</span><small>${esc(t.task_code)}</small></div>`)
            .join("");
        return `<div class="chips"><button class="chip ${zoom === "week" ? "on" : ""}" data-zoom="week">Semana</button><button class="chip ${zoom === "month" ? "on" : ""}" data-zoom="month">Mes</button></div>
            <div class="gantt"><div class="gantt-labels" style="padding-top:${top}px">${labels}</div>
            <div class="gantt-scroll" data-today-x="${todayX}"><svg width="${width}" height="${height}" class="gantt-svg" role="img" aria-label="Gantt de la obra">${ticks.join("")}${bars}
            ${todayX >= 0 && todayX <= width ? `<line x1="${todayX}" x2="${todayX}" y1="${top - 6}" y2="${height}" class="today"/><text x="${todayX + 3}" y="${height - 2}" class="axis strong">hoy</text>` : ""}
            ${milestones}</svg></div></div>
            <div class="legend"><span><i class="swatch" style="background:${SERIES.real}"></i>Avance validado</span><span><i class="swatch track"></i>Programado</span><span><i class="swatch late"></i>Atrasada</span><span>◆ Hito</span></div>`;
    }

    screens.site = () => {
        const site = state.data && state.data.site;
        const view = state.params.view || "summary";
        const tabs = [["summary", "Resumen"], ["week", "Semana"], ["tasks", "Tareas"], ["gantt", "Gantt"]];
        const head = `${header("Obra", join(projectParts().code, site ? "datos del " + clock(String(site.as_of || "").replace(" ", "T") + "Z") : ""), "home")}
            <div class="tabs" role="tablist">${tabs.map(([key, label]) => `<button role="tab" aria-selected="${view === key}" class="${view === key ? "on" : ""}" data-view="${key}">${label}</button>`).join("")}</div>`;
        if (!site) {
            return `${head}<main class="page"><p class="muted">Sin datos de la obra: conéctese para descargarlos.</p></main>${nav("site")}`;
        }
        if (!site.has_plan) {
            return `${head}<main class="page"><p class="muted">La obra aún no tiene un plan aprobado.</p></main>${nav("site")}`;
        }
        let body = "";
        if (view === "summary") {
            const s = site.summary;
            const behind = s.programmed - s.real;
            const stat = (n, label, cls) => `<div class="card stat"><b class="${cls || ""}">${n}</b><small>${label}</small></div>`;
            body = `<div class="card hero">
                    <div class="row between"><span><small class="eyebrow">Avance físico real</small><b class="hero-num">${pct(s.real)}</b></span>
                    <span class="right"><small class="eyebrow">Programado a hoy</small><b class="hero-num muted-num">${pct(s.programmed)}</b></span></div>
                    ${pairBar(s.real, s.programmed)}
                    <small class="${behind > 0.05 ? "warn strong" : ""}">${behind > 0.005 ? `${Math.round(100 * behind)} puntos por debajo de lo programado` : behind < -0.005 ? `${Math.round(-100 * behind)} puntos por encima de lo programado` : "Al día con lo programado"}</small></div>
                <div class="stats four">${stat(s.late, "partidas atrasadas", s.late ? "bad" : "")}${stat(s.to_validate, "avances por validar")}${stat(s.open_requests, "pedidos abiertos")}${stat(s.staff_today, "personas hoy")}</div>
                ${s.amounts ? `<div class="card"><small class="eyebrow">Montos del plan</small>
                    <div class="kv"><span>Planificado</span><b>${money(s.amounts.planned)}</b></div><div class="kv"><span>Comprometido</span><b>${money(s.amounts.committed)}</b></div>
                    <div class="kv"><span>Real</span><b>${money(s.amounts.actual)}</b></div><div class="kv"><span>Saldo del plan</span><b>${money(s.amounts.remaining)}</b></div></div>` : ""}
                <div class="card"><b>Curva de avance</b>${siteCurve(site.curve)}</div>
                <div class="card"><b>Avance por especialidad</b>${site.specialties
                    .map((g) => `<div class="spec"><div class="row between"><span class="clamp1">${esc(g.name)}</span><small class="strong">${pct(g.real)} <span class="muted">/ ${pct(g.programmed)}</span></small></div>${pairBar(g.real, g.programmed)}</div>`)
                    .join("")}
                    <div class="legend"><span><i class="swatch" style="background:${SERIES.real}"></i>Real</span><span><i class="swatch" style="background:${SERIES.programmed}"></i>Programado a hoy</span></div></div>`;
        } else if (view === "week") {
            const w = site.week;
            body = `<p class="muted">Semana ${esc(range(site.week_start, site.week_end))}</p>
                <h2>Inician esta semana (${w.starting.length})</h2>${w.starting.map((t) => siteTaskCard(t)).join("") || '<p class="muted">Ninguna.</p>'}
                <h2>Terminan esta semana (${w.ending.length})</h2>${w.ending.map((t) => siteTaskCard(t)).join("") || '<p class="muted">Ninguna.</p>'}
                <h2>Inician la semana siguiente (${(w.next_starting || []).length})</h2>${(w.next_starting || []).map((t) => siteTaskCard(t)).join("") || '<p class="muted">Ninguna.</p>'}`;
        } else if (view === "tasks") {
            const filter = state.params.tfilter || "all";
            const rows = site.tasks.filter((t) => filter === "all" || (filter === "crew" ? t.own_staff : filter === "contract" ? t.partners.length : t.late));
            const chip = (key, label) => `<button class="chip ${filter === key ? "on" : ""}" data-tfilter="${key}" aria-pressed="${filter === key}">${label}</button>`;
            body = `<div class="chips">${chip("all", "Todas")}${chip("crew", "Personal propio")}${chip("contract", "Por contrata")}${chip("late", "Atrasadas")}</div>
                <p class="hint">Las columnas las calcula Odoo con las fechas del plan y el avance validado. Toque una partida para registrar su avance.</p>
                <div class="kanban">${COLUMNS.map(([key, label]) => {
                    const items = rows.filter((t) => t.column === key);
                    return `<section class="kanban-col"><h3>${label} <span class="muted">${items.length}</span></h3>${items.slice(0, 60).map((t) => siteTaskCard(t, true)).join("") || '<small class="muted">—</small>'}${items.length > 60 ? `<small class="muted">y ${items.length - 60} más</small>` : ""}</section>`;
                }).join("")}</div>`;
        } else {
            body = siteGantt(site);
        }
        return `${head}<main class="page ${view === "tasks" || view === "gantt" ? "wide" : ""}">${body}</main>${nav("site")}`;
    };

    // 4. Mis partidas.
    function partidaState(p) {
        if (p.pending > 0) return [`${qtyText(p.pending)} ${p.uom} por validar`, "warn"];
        if (!p.validated) return ["Sin avance", "muted"];
        if (p.last_validated) return [`Validado al ${dayMonth(p.last_validated)}`, "ok"];
        return [`Saldo ${qtyText(p.balance)} ${p.uom}`, "muted"];
    }
    screens.partidas = () => {
        const data = state.data || { partidas: [] };
        const filter = state.params.filter || "all";
        const q = (state.params.q || "").toLowerCase();
        const rows = data.partidas.filter(
            (p) =>
                (filter === "all" || (filter === "pending" ? p.pending > 0 : p.balance > 0)) &&
                matches(q, taskCode(p), taskName(p), p.parent_label, p.activity)
        );
        const chip = (key, label) =>
            `<button class="chip ${filter === key ? "on" : ""}" data-filter="${key}" aria-pressed="${filter === key}">${label}</button>`;
        return `${header("Avance", join(projectParts().code, scopeText()), "home")}
            <main class="page">
                <label class="search">${svg("search", 20)}<input type="search" placeholder="Buscar partida o ítem" value="${esc(state.params.q || "")}" data-input="q" aria-label="Buscar partida"></label>
                <div class="chips">${chip("all", "Todas")}${chip("pending", "Por validar")}${chip("balance", "Con saldo")}</div>
                ${rows
                    .map((p) => {
                        const done = p.validated + p.pending;
                        const pct = p.planned ? Math.min(100, (100 * done) / p.planned) : 0;
                        const [stateText, cls] = partidaState(p);
                        return `<button class="card partida" data-go="progress" data-id="${p.id}">
                            <div class="row top">${taskCode(p) ? `<span class="tag">${esc(taskCode(p))}</span>` : ""}<b class="grow clamp2">${esc(taskName(p))}</b>${svg("next", 18)}</div>
                            ${taskSub(p) ? `<small class="muted">${esc(taskSub(p))}</small>` : ""}
                            <div class="bar-bg"><div class="bar-fill" style="width:${pct}%"></div></div>
                            <div class="row between"><small>${qtyText(done)} de ${qtyText(p.planned)} ${esc(p.uom)}</small>
                            <small class="strong ${cls}">${esc(stateText)}</small></div>
                        </button>`;
                    })
                    .join("") || '<p class="muted">Sin partidas.</p>'}
            </main>${nav("partidas")}`;
    };

    // 5. Registrar avance.
    function progressCheck(line, d) {
        // Lo que se suma hoy y si pasa el saldo o el saldo más la tolerancia del
        // plan. Más allá, según la política del plan: se bloquea, solo alerta o
        // lo aprueba la jefatura (el re-trabajo no cuenta).
        const qty = d.mode === "pct"
            ? (line.planned * Number(d.pct || 0)) / 100 - line.validated - line.pending
            : Number(d.qty || 0);
        if (d.rework) return { qty, over: false, blocked: false };
        const tolerance = line.tolerance || 0;
        const exceeds = qty > line.balance + tolerance + 1e-6;
        const policy = line.exceed_policy || "block";
        return { qty, over: qty > line.balance + 1e-6, exceeds, policy, blocked: exceeds && policy === "block" };
    }
    screens.progress = () => {
        const line = ((state.data && state.data.partidas) || []).find((p) => p.id === Number(state.params.id));
        if (!line) {
            return screens.partidas();
        }
        const d = (state.draft.progress = state.draft.progress || {
            date: today(), mode: "qty", qty: 0, pct: 0, photos: [], rework: false, reason: "", note: "",
        });
        const value = d.mode === "pct" ? d.pct : d.qty;
        const check = progressCheck(line, d);
        const tolerance = line.tolerance || 0;
        return `${header("Registrar avance", "", "partidas")}
            <main class="page">
                <div class="card">
                    <div class="row">${taskCode(line) ? `<span class="tag">${esc(taskCode(line))}</span>` : ""}<small>${esc(line.parent_label || "")}</small></div>
                    <b class="title">${esc(taskName(line))}</b>${line.role_label || (line.activity && line.activity !== line.name) ? `<small>${esc(line.role_label || line.activity)}</small>` : ""}
                    <div class="grid4"><span>Plan<b>${qtyText(line.planned)}</b></span><span>Validado<b>${qtyText(line.validated)}</b></span>
                    <span>Por validar<b class="warn">${qtyText(line.pending)}</b></span><span>Saldo ${esc(line.uom)}<b class="accent">${qtyText(line.balance)}</b></span></div>
                </div>
                <div class="card form">
                    <label>Fecha de ejecución<input type="date" data-bind="progress.date" value="${esc(d.date)}" max="${today()}"></label>
                    <div class="toggle"><button class="${d.mode === "qty" ? "on" : ""}" data-set="progress.mode=qty" aria-pressed="${d.mode === "qty"}">Metrado (${esc(line.uom)})</button>
                    <button class="${d.mode === "pct" ? "on" : ""}" data-set="progress.mode=pct" aria-pressed="${d.mode === "pct"}">Porcentaje</button></div>
                    <div class="stepper big"><button data-step="-1" aria-label="Restar">−</button>
                    <span class="value"><input type="number" step="0.01" min="0" inputmode="decimal" data-bind="progress.${d.mode}" value="${value}" aria-label="Cantidad"><small>${d.mode === "pct" ? "% acumulado" : esc(line.uom) + " hoy"}</small></span>
                    <button data-step="1" aria-label="Sumar">+</button></div>
                    ${
                        check.blocked
                            ? `<p class="alert box">Supera el saldo de la partida${tolerance ? ` y la tolerancia del plan (${qtyText(tolerance)} ${esc(line.uom)})` : ""}: Odoo no lo acepta. Si es trabajo adicional, pida al residente el adicional; si se rehace, márquelo como re-trabajo.</p>`
                            : check.exceeds && check.policy === "approval"
                            ? `<p class="alert box">Supera el saldo de la partida${tolerance ? ` y la tolerancia del plan (${qtyText(tolerance)} ${esc(line.uom)})` : ""}: se envía como exceso y lo aprueba la jefatura antes de validarse.</p>`
                            : check.exceeds
                            ? `<p class="notice box">Supera el saldo de la partida${tolerance ? ` y la tolerancia del plan` : ""}: se envía con una alerta para el residente.</p>`
                            : check.over
                            ? `<p class="notice box">Supera el saldo de la partida; entra en la tolerancia del plan (${qtyText(tolerance)} ${esc(line.uom)}) y lo revisa el residente al validarlo.</p>`
                            : ""
                    }
                </div>
                ${photosCard("progress", d, true)}
                <div class="card form">
                    <label class="check"><input type="checkbox" data-bind="progress.rework" ${d.rework ? "checked" : ""}> Es re-trabajo (no se paga)</label>
                    ${
                        d.rework
                            ? `<label>Motivo<select data-bind="progress.reason"><option value="">Elija el motivo</option>${(state.data.rework_reasons || [])
                                  .map(([code, label]) => `<option value="${code}" ${d.reason === code ? "selected" : ""}>${esc(label)}</option>`)
                                  .join("")}</select></label>`
                            : ""
                    }
                    <label>Observación<textarea rows="2" data-bind="progress.note" placeholder="Opcional">${esc(d.note)}</textarea></label>
                </div>
                ${state.params.error ? `<p class="error">${esc(state.params.error)}</p>` : ""}
                <button class="primary" data-action="save-progress" ${check.blocked ? "disabled" : ""}>Guardar avance</button>
            </main>`;
    };

    function gpsText(draft) {
        const gps = draft.gps;
        if (!gps) return "";
        if (gps.denied) {
            return `<small class="gps warn">${svg("pin", 18)} Sin ubicación: active el GPS del celular para registrar dónde se tomó la foto.</small>`;
        }
        if (gps.distance === undefined) {
            return `<small class="gps ok">${svg("pin", 18)} Ubicación tomada.</small>`;
        }
        const radius = state.data.project.radius_m;
        const meters = Math.round(gps.distance);
        return gps.out
            ? `<small class="gps warn">${svg("pin", 18)} Ubicación tomada: fuera del radio de la obra (a ${meters} m; radio ${radius} m).</small>`
            : `<small class="gps ok">${svg("pin", 18)} Ubicación tomada: dentro del radio de la obra (${meters} m).</small>`;
    }
    function photosCard(key, draft, required, title) {
        const max = MAX_PHOTOS[key] || 5;
        const full = draft.photos.length >= max;
        return `<div class="card form"><div class="row between"><b>${esc(title || "Fotos")}</b><small class="muted">${
            required ? "obligatoria al menos una" : `${draft.photos.length} de ${max}`
        }</small></div>
            <div class="photos">${draft.photos
                .map(
                    (p, i) => `<div class="thumb" style="background-image:url(${p.data})"><span>Foto ${i + 1}${p.taken ? " · " + clock(p.taken) : ""}</span>
                    <button data-remove-photo="${key}:${i}" aria-label="Quitar la foto ${i + 1}">×</button></div>`
                )
                .join("")}
            ${
                full
                    ? ""
                    : `<label class="add-photo">${svg("camera", 26)}<span>Tomar foto</span><input type="file" accept="image/*" capture="environment" multiple data-photos="${key}" hidden></label>`
            }</div>
            ${gpsText(draft)}</div>`;
    }

    // 6. Avance guardado y «Por enviar».
    const SAVED_TEXT = {
        progress: ["Avance", "queda por validar por el residente"],
        daily_report: ["Parte diario", "le llega al residente"],
        crew_day: ["Tareo", "se carga como costo de personal de cada partida"],
        material_request: ["Requerimiento", "va a la aprobación del coordinador de la obra"],
        reception: ["Recepción", "lo que faltó queda pendiente de entrega"],
        return: ["Devolución", "el almacén la recibe"],
        resident_progress: ["Validación", "Odoo la vuelve a comprobar al recibirla"],
        resident_request: ["Aprobación", "Odoo la vuelve a comprobar al recibirla"],
        close_day: ["Parte diario de obra", "sale en PDF al contacto del cliente"],
        deduction: ["Deductivo", "entra en la siguiente valorización de la contrata"],
        crew_request: ["Solicitud", "le llega al planificador de la obra"],
        change_order: ["Cambio del cliente", "queda en borrador y el cliente recibe la constancia"],
        expense: ["Comprobante", "Contabilidad lo revisa; queda por rendir en su fondo"],
        settle: ["Rendición", "Contabilidad la revisa y la aprueba"],
    };
    function queueRow(item) {
        const photos = (item.payload && item.payload.photos ? item.payload.photos.length : 0);
        const status =
            item.status === "done"
                ? `enviado a las ${clock(item.sent)}${item.result && item.result.name ? " · " + item.result.name : ""}`
                : item.status === "rejected"
                ? "rechazado"
                : state.online
                ? "en cola, enviándose"
                : "en cola, sin señal";
        return `<div class="queue-row ${item.status}"><span class="dot" aria-hidden="true"></span>
            <div class="grow"><b>${esc(item.label)}</b><small>${esc(join(photos ? `${photos} ${photos === 1 ? "foto" : "fotos"}` : "", status))}</small>
            ${item.error ? `<p class="error">${esc(item.error)}</p>` : ""}
            ${
                item.status === "rejected"
                    ? `<span class="row"><button class="link" data-retry="${item.uuid}">Reintentar</button><button class="link" data-discard="${item.uuid}">Descartar</button></span>`
                    : item.status === "done" ? `<button class="link" data-discard="${item.uuid}">Quitar de la lista</button>` : ""
            }</div></div>`;
    }
    screens.queue = () => {
        const saved = state.params.saved;
        const items = state.queue.slice().reverse();
        const todays = items.filter((q) => q.created.slice(0, 10) === new Date().toISOString().slice(0, 10));
        const older = items.filter((q) => !todays.includes(q));
        const [what, next] = SAVED_TEXT[saved] || [];
        const lastSaved = saved && state.queue.slice().reverse().find((q) => q.kind === saved);
        const sent = lastSaved && lastSaved.status === "done";
        return `${header("Por enviar", "", "home")}
        <main class="page">
            ${
                saved
                    ? `<div class="card saved"><span class="saved-icon ${sent ? "ok" : ""}">${svg(sent ? "check" : "clock", 28)}</span>
                       <b>${esc(what)} ${sent ? "enviado" : "guardado en el celular"}</b>
                       <small>${sent ? `Ya está en Odoo: ${esc(next)}.` : state.online ? `Se está enviando; ${esc(next)}.` : `No hay señal. Se envía solo cuando vuelva la conexión y ${esc(next)}.`}</small></div>`
                    : `<p class="muted">${state.online ? "Con señal: se envía solo." : "Sin señal: se envía solo cuando vuelva la conexión."}</p>`
            }
            <h2>Registros de hoy</h2>
            <div class="card list">${todays.map(queueRow).join("") || '<small class="muted">Aún no registra nada hoy.</small>'}</div>
            ${older.length ? `<h2>Anteriores</h2><div class="card list">${older.map(queueRow).join("")}</div>` : ""}
            ${state.params.error ? `<p class="notice box">${esc(state.params.error)}</p>` : ""}
            <button class="secondary" data-action="flush">Reintentar el envío ahora</button>
            ${saved === "progress" ? '<button class="primary" data-go="partidas">Registrar otra partida</button>' : ""}
            <button class="link center" data-go="home">Volver al inicio</button>
        </main>${nav("queue")}`;
    };

    // 7. Parte diario de obra.
    function dailyDraft() {
        if (!state.draft.daily) {
            const daily = state.data.daily || { own_today: 0, contractors: [], work: [] };
            state.draft.daily = {
                date: today(), weather: "", restrictions: [], occurrences: "", photos: [], signature: "",
                staff: [
                    { name: "Personal propio " + shortName(brand().name), source: "own", sub: "de la asistencia de hoy", count: daily.own_today || 0 },
                    ...daily.contractors.map((c) => ({ name: c.name, source: "contract", sub: join("contrata", c.scope), count: 0 })),
                ],
            };
        }
        return state.draft.daily;
    }
    screens.daily = () => {
        const d = dailyDraft();
        const daily = state.data.daily || { work: [] };
        // Lo enviado (de toda la obra) y lo que aún está en la cola de este equipo.
        // Reportados y validados del día, con su estado (7.1).
        const work = daily.work.map((w) => ({ label: join(`${taskCode(w)} ${taskName(w)}`.trim(), w.partner), qty: join(`${qtyText(w.qty)} ${w.uom}`, w.state_label) }));
        state.queue
            .filter((q) => q.kind === "progress" && q.status === "pending" && q.payload.date === d.date)
            .forEach((q) => work.push({ label: q.label.split(":")[0].replace(/^Avance /, ""), qty: (q.label.split(": ")[1] || "") + " · por enviar" }));
        const total = d.staff.reduce((s, r) => s + Number(r.count || 0), 0);
        return `${header("Parte diario", join(projectParts().code, longDay(d.date)), "home")}
            <main class="page">
                <div class="card form"><b>Clima</b><div class="chips">${(state.data.weather || [])
                    .map(([code, label]) => `<button class="chip ${d.weather === code ? "on" : ""}" data-set="daily.weather=${code}" aria-pressed="${d.weather === code}">${esc(label)}</button>`)
                    .join("")}</div></div>
                <div class="card"><div class="row between"><b>Personal en obra</b><small>total ${total}</small></div>
                    ${d.staff
                        .map(
                            (r, i) => `<div class="row staff">${
                                r.custom
                                    ? `<input class="grow" value="${esc(r.name)}" data-bind="daily.staff.${i}.name" placeholder="Cuadrilla o contrata" aria-label="Cuadrilla o contrata">`
                                    : `<span class="grow"><b>${esc(r.name)}</b><small>${esc(r.sub || "")}</small></span>`
                            }${stepper(`data-staff="${i}"`, r.count, "Personas", true)}</div>`
                        )
                        .join("")}
                    <button class="link" data-action="add-staff">+ Agregar cuadrilla o contrata</button></div>
                <div class="card"><b>Trabajos del día</b><small class="muted">Se llenan con los avances registrados hoy.</small>
                    ${work.map((w) => `<div class="row between work"><span>${esc(w.label)}</span><b>${esc(w.qty)}</b></div>`).join("") || '<small class="muted">Sin avances registrados hoy.</small>'}</div>
                <div class="card form"><b>Restricciones del día</b>${[
                    ["material", "Falta de material"],
                    ["front", "Frente no liberado por el cliente"],
                    ["weather", "Lluvia o paralización"],
                ]
                    .map(([code, label]) => `<label class="check"><input type="checkbox" data-toggle="daily.restrictions=${code}" ${d.restrictions.includes(code) ? "checked" : ""}> ${label}</label>`)
                    .join("")}
                <label>Ocurrencias y visitas<textarea rows="3" data-bind="daily.occurrences">${esc(d.occurrences)}</textarea></label></div>
                ${photosCard("daily", d, false, "Fotos generales")}
                <div class="card form"><b>Firma del maestro de obra</b><div class="sign-wrap"><canvas id="signature" class="signature" width="340" height="140" aria-label="Firma"></canvas>
                ${d.signature ? "" : '<span class="sign-hint" aria-hidden="true">Firme con el dedo aquí</span>'}</div>
                <button class="link" data-action="clear-signature">Borrar la firma</button></div>
                ${state.params.error ? `<p class="error">${esc(state.params.error)}</p>` : ""}
                <button class="primary" data-action="save-daily">Enviar al residente</button>
            </main>`;
    };

    // Encabezado del tareo (7.2): cada columna dice partida y rol; la partida
    // con más de un rol se agrupa en una fila superior.
    function crewHead(lines) {
        const groups = [];
        lines.forEach((l) => {
            const key = taskCode(l) + "|" + taskName(l);
            const last = groups[groups.length - 1];
            if (last && last.key === key) last.lines.push(l);
            else groups.push({ key, lines: [l] });
        });
        const label = (l) => `${esc(taskCode(l))}<small>${esc(taskName(l))}</small>`;
        const role = (l) => esc(l.role_label || l.activity || "");
        if (groups.every((g) => g.lines.length === 1)) {
            return `<tr><th>Persona</th>${lines.map((l) => `<th>${label(l)}<small class="muted">${role(l)}</small></th>`).join("")}<th>Total</th></tr>`;
        }
        return `<tr><th rowspan="2">Persona</th>${groups.map((g) => `<th colspan="${g.lines.length}">${label(g.lines[0])}</th>`).join("")}<th rowspan="2">Total</th></tr>
            <tr>${groups.map((g) => g.lines.map((l) => `<th><small>${role(l)}</small></th>`).join("")).join("")}</tr>`;
    }

    // 8. Cuadrilla y tareo (pensada para tablet).
    screens.crew = () => {
        const crew = state.data.crew || [];
        // Agrupadas por partida para el encabezado (7.2).
        const lines = (state.data.partidas || []).filter((p) => p.kind === "labor")
            .sort((a, b) => (taskCode(a) + taskName(a)).localeCompare(taskCode(b) + taskName(b)) || a.id - b.id);
        const d = (state.draft.crew = state.draft.crew || {
            date: today(),
            attendance: Object.fromEntries(crew.map((w) => [w.id, { present: true, time: "07:30" }])),
            hours: {},
        });
        const hoursDay = 8;
        const present = (w) => d.attendance[w.id] && d.attendance[w.id].present;
        const total = (id) =>
            Object.entries(d.hours)
                .filter(([key]) => key.startsWith(id + ":"))
                .reduce((sum, [, h]) => sum + Number(h || 0), 0);
        const count = crew.filter(present).length;
        const actions = `<div class="bar-actions"><small class="strong">Presentes ${count} de ${crew.length}</small>
            <button class="primary compact" data-action="save-crew">Enviar tareo</button></div>`;
        const foreman = (member("foreman") || {}).name || (state.me && state.me.user.name) || "";
        return `${header("Cuadrilla y tareo", join(projectParts().code, foreman ? "cuadrilla de " + foreman : "", longDay(d.date)), "home", actions)}
            <main class="page wide crew-grid">
                <div class="card"><div class="row between"><b>Asistencia</b><small>hora de entrada</small></div>
                ${crew
                    .map((w) => {
                        const on = present(w);
                        return `<div class="row crew ${on ? "" : "absent"}"><span class="avatar">${esc(initials(w.name))}</span>
                        <span class="grow"><b>${esc(w.name)}</b><small>${esc(w.category || "")}${on ? "" : " · sin marcación"}</small></span>
                        ${on ? `<input class="time" type="time" value="${esc((d.attendance[w.id] || {}).time || "07:30")}" data-bind="crew.attendance.${w.id}.time" aria-label="Hora de entrada de ${esc(w.name)}">` : ""}
                        <button class="pill-btn ${on ? "ok" : "bad"}" data-presence="${w.id}" aria-pressed="${on}">${on ? "Presente" : "Falta"}</button></div>`;
                    })
                    .join("") || '<small class="muted">La cuadrilla no tiene personas con turno en la obra.</small>'}</div>
                <div class="card scroll"><div class="row between"><b>Horas por partida</b><small class="muted">jornada de ${hoursDay} horas; las horas extra van aparte</small></div>
                <table class="tareo"><thead>${crewHead(lines)}</thead>
                <tbody>${crew
                    .map((w) => {
                        const on = present(w);
                        const t = total(w.id);
                        return `<tr class="${on ? "" : "absent"}"><td>${esc(w.name)}</td>${lines
                            .map((l) => `<td><input type="number" min="0" max="12" step="0.5" value="${d.hours[w.id + ":" + l.id] || ""}" data-bind="crew.hours.${w.id}:${l.id}" aria-label="Horas de ${esc(w.name)} en ${esc(join(taskCode(l), l.role_label || l.activity))}" ${on ? "" : "disabled"}></td>`)
                            .join("")}<td class="strong ${on ? (t === hoursDay ? "ok" : "bad") : "muted"}" data-total="${w.id}">${on ? qtyText(t) : "—"}</td></tr>`;
                    })
                    .join("")}</tbody></table>
                <p class="hint">El tareo se valoriza con la tarifa de construcción civil de cada categoría y se carga como costo de personal propio de cada partida.</p></div>
                ${state.params.error ? `<p class="error">${esc(state.params.error)}</p>` : ""}
            </main>`;
    };

    // 9. Requerimientos: catálogo.
    function catalogItems(tab) {
        const cat = state.data.catalog;
        if (tab === "partida") {
            return cat.partida.map((p) => ({
                key: `partida:${p.product_id}:${p.task_id}`, catalog: "partida", product_id: p.product_id,
                task_id: p.task_id, name: p.name, uom: p.uom,
                dest: `Partida ${join(taskCode(p), p.task_name || p.task)}`,
                sub: join(`${p.uom} · saldo del plan ${qtyText(p.balance)}`, taskCode(p), p.task_name || p.task),
                search: [taskCode(p), p.task_name || p.task, p.parent_label].join(" "),
            }));
        }
        return cat[tab].products.map((p) => ({
            key: `${tab}:${p.product_id}`, catalog: tab, product_id: p.product_id, name: p.name, uom: p.uom,
            dest: "Gastos generales de la obra", sub: join(p.uom, p.note),
        }));
    }
    screens.catalog = () => {
        if (!state.data || !state.data.catalog) {
            return `${header("Requerimientos", projectName(), "home")}<main class="page"><p class="muted">Los requerimientos los piden el capataz y la oficina técnica.</p></main>${nav("catalog")}`;
        }
        const tab = state.params.tab || "partida";
        const qty = (key) => (state.cart.find((c) => c.key === key) || {}).qty || 0;
        const tabs = [["partida", "De la partida"], ["epp", "EPP"], ["office", "Útiles y aseo"]];
        const q = (state.params.q || "").toLowerCase();
        // Busca por producto y, en «De la partida», por código o nombre de la partida (CR-17).
        const items = catalogItems(tab).filter((it) => matches(q, it.name, it.search));
        const kits = tab === "partida" ? [] : state.data.catalog[tab].kits;
        return `${header("Requerimientos", join(projectParts().code, "para el almacén central o compra"), "home")}
            <div class="tabs" role="tablist">${tabs.map(([key, label]) => `<button role="tab" aria-selected="${tab === key}" class="${tab === key ? "on" : ""}" data-tab="${key}">${label}</button>`).join("")}</div>
            <main class="page">
                <label class="search">${svg("search", 20)}<input type="search" placeholder="Buscar producto o partida" value="${esc(state.params.q || "")}" data-input="q" aria-label="Buscar en el catálogo"></label>
                ${tab === "partida" ? `<p class="muted">Materiales de las recetas de su cuadrilla, con el saldo del plan de la obra.</p>` : ""}
                ${kits.length ? `<div class="chips">${kits.map((k) => `<button class="chip outline" data-kit="${tab}:${k.id}">+ ${esc(k.name)}</button>`).join("")}</div>` : ""}
                ${items
                    .map(
                        (it) => `<div class="card item"><span class="thumb-sm" aria-hidden="true"></span><span class="grow"><b>${esc(it.name)}</b><small>${esc(it.sub)}</small></span>
                        <div class="stepper small"><button data-cart="${esc(it.key)}" data-delta="-1" aria-label="Restar">−</button><b>${qtyText(qty(it.key))}</b>
                        <button data-cart="${esc(it.key)}" data-delta="1" data-item='${esc(JSON.stringify(it))}' aria-label="Sumar">+</button></div></div>`
                    )
                    .join("") || '<p class="muted">Sin productos en este catálogo.</p>'}
                ${
                    state.params.other
                        ? `<div class="card form"><label>Pedir algo que no está en la lista<input data-bind="cartText" value="${esc(state.draft.cartText || "")}" placeholder="Descripción y cantidad"></label>
                           <button class="secondary" data-action="add-text">Agregar al pedido</button></div>`
                        : `<button class="dashed" data-action="show-other">Pedir algo que no está en la lista</button>`
                }
            </main>
            <button class="cart-bar" data-go="cart" ${state.cart.length ? "" : "disabled"}><span>${state.cart.length} ${state.cart.length === 1 ? "ítem" : "ítems"} en el pedido</span><b>Revisar ›</b></button>${nav("catalog")}`;
    };

    // 10. Requerimiento por enviar.
    screens.cart = () => {
        const d = (state.draft.request = state.draft.request || { date_required: today(), priority: "normal", note: "" });
        return `${header("Revisar el requerimiento", "", "catalog")}
            <main class="page">
                <div class="card form"><label>Fecha en que se necesita<input type="date" data-bind="request.date_required" value="${esc(d.date_required)}" min="${today()}"></label>
                <b class="label">Prioridad</b>
                <div class="toggle priority"><button class="${d.priority === "normal" ? "on" : ""}" data-set="request.priority=normal" aria-pressed="${d.priority === "normal"}">Normal</button>
                <button class="${d.priority === "urgent" ? "on urgent" : ""}" data-set="request.priority=urgent" aria-pressed="${d.priority === "urgent"}">Urgente</button></div></div>
                ${["partida", "epp", "office", "text"]
                    .map((kind) => {
                        const rows = state.cart.filter((c) => c.catalog === kind);
                        if (!rows.length) return "";
                        return `<div class="card"><small class="eyebrow">${{ partida: "De la partida", epp: "EPP", office: "Útiles y aseo", text: "Fuera de catálogo" }[kind]}</small>${rows
                            .map((c) => `<div class="row between cart-row"><span class="grow">${esc(c.name)}<small>${esc(c.dest || "Lo revisa logística")}</small></span><b>${kind === "text" ? "" : `${qtyText(c.qty)} ${esc(c.uom || "")}`}</b></div>`)
                            .join("")}</div>`;
                    })
                    .join("")}
                <div class="card steps"><b>Qué pasa al enviarlo</b><ol><li>Lo aprueba el coordinador de la obra</li><li>Logística despacha del almacén o compra</li><li>Usted confirma la recepción en obra</li></ol></div>
                <div class="card form"><label>Nota para logística<textarea rows="2" data-bind="request.note" placeholder="Opcional">${esc(d.note)}</textarea></label></div>
                <button class="primary" data-action="save-request" ${state.cart.length ? "" : "disabled"}>Enviar a aprobación</button>
            </main>`;
    };

    // 11. Recepción en obra.
    function deliveryTitle(p) {
        return p.kind === "purchase"
            ? [`Compra a ${p.partner || "proveedor"}`, join("Directo a obra", p.origin)]
            : ["Despacho del almacén", join("Requerimiento de obra", p.origin)];
    }
    function lineStatus(l, received) {
        const r = Number(received || 0);
        if (Math.abs(r - l.sent) < 1e-6) return ["Completo", "ok"];
        if (r < l.sent) return [`Faltan ${qtyText(l.sent - r)} ${l.uom}`, "bad"];
        return ["Llegó de más", "bad"];
    }
    screens.reception = () => {
        const deliveries = state.data.deliveries || [];
        const picking = deliveries.find((p) => p.id === Number(state.params.id)) || deliveries[0];
        const head = header("Recepción en obra", join(projectParts().code, `${deliveries.length} ${deliveries.length === 1 ? "entrega" : "entregas"} por recibir`), "home");
        if (!picking) {
            return `${head}<main class="page"><p class="muted">No hay entregas por recibir.</p></main>`;
        }
        const d = (state.draft["reception" + picking.id] = state.draft["reception" + picking.id] || {
            received: Object.fromEntries(picking.lines.map((l) => [l.move_id, l.sent])), photos: [], note: "", edited: false,
        });
        const issues = picking.lines
            .map((l) => [l, lineStatus(l, d.received[l.move_id])])
            .filter(([, [, cls]]) => cls === "bad")
            .map(([l, [text]]) => `${l.name}: ${text.toLowerCase()}`)
            .join("; ");
        return `${head}
            <main class="page">
                ${deliveries
                    .map((p) => {
                        const [title, sub] = deliveryTitle(p);
                        return `<button class="card delivery ${p.id === picking.id ? "on" : ""}" data-go="reception" data-id="${p.id}" aria-pressed="${p.id === picking.id}"><b>${esc(title)}</b><small>${esc(join(sub, p.name))}</small></button>`;
                    })
                    .join("")}
                <div class="card"><div class="row lines-head"><span class="grow">Producto</span><span>Enviado</span><span class="rec">Recibido</span></div>
                ${picking.lines
                    .map((l) => {
                        const [text, cls] = lineStatus(l, d.received[l.move_id]);
                        return `<div class="row line"><span class="grow"><b>${esc(l.name)}</b><small class="strong ${cls}">${esc(text)}</small></span>
                        <span>${qtyText(l.sent)}</span>${stepper(`data-received="${picking.id}:${l.move_id}"`, d.received[l.move_id], "Recibido", true)}</div>`;
                    })
                    .join("")}</div>
                ${photosCard("reception" + picking.id, d, true, "Guía firmada y fotos de la carga")}
                <div class="card form"><label>Faltantes o daños<textarea rows="2" data-bind="reception${picking.id}.note" data-edited="reception${picking.id}" placeholder="Sin faltantes ni daños">${esc(d.edited ? d.note : issues)}</textarea></label></div>
                ${state.params.error ? `<p class="error">${esc(state.params.error)}</p>` : ""}
                <button class="primary" data-action="save-reception" data-id="${picking.id}">Confirmar recepción</button>
            </main>`;
    };

    // 12. Devolución al almacén.
    screens.return = () => {
        const items = state.data.returnables || [];
        const d = (state.draft.ret = state.draft.ret || { lines: {}, transport: "own", photos: [] });
        const where = state.data.project.location;
        return `${header("Devolución al almacén", where ? `De la ubicación ${where} al almacén central` : "Al almacén central", "home")}
            <main class="page">
                <p class="muted">Elija lo que regresa. Lo que está en buen estado vuelve al almacén y sale del costo de la partida; lo dañado pasa a «Dañados» de la obra hasta que Logística decida.</p>
                ${items
                    .map((it) => {
                        const row = d.lines[it.product_id];
                        return `<div class="card return ${row ? "on" : ""}"><label class="check"><input type="checkbox" data-return="${it.product_id}" ${row ? "checked" : ""}>
                        <span class="grow"><b>${esc(it.name)}</b><small>en obra ${qtyText(it.qty)} ${esc(it.uom)}</small></span></label>
                        ${
                            row
                                ? `<div class="row between"><small>Cantidad a devolver</small>${stepper(`data-ret="${it.product_id}"`, row.qty, "A devolver", true)}</div>
                                   <div class="pills"><button class="pill-btn ${row.state === "good" ? "ok" : ""}" data-set="ret.lines.${it.product_id}.state=good" aria-pressed="${row.state === "good"}">En buen estado</button>
                                   <button class="pill-btn ${row.state === "damaged" ? "bad" : ""}" data-set="ret.lines.${it.product_id}.state=damaged" aria-pressed="${row.state === "damaged"}">Dañado</button></div>`
                                : ""
                        }</div>`;
                    })
                    .join("") || '<p class="muted">No hay material en la obra.</p>'}
                <div class="card form"><label>Traslado<select data-bind="ret.transport">
                    <option value="own" ${d.transport === "own" ? "selected" : ""}>Unidad propia (guía de remisión)</option>
                    <option value="supplier" ${d.transport === "supplier" ? "selected" : ""}>Flete de proveedor</option></select></label></div>
                <div class="card form"><label>Motivo<textarea rows="2" data-bind="ret.note" placeholder="Qué pasó con lo dañado">${esc(d.note || "")}</textarea></label></div>
                ${photosCard("ret", d, true, "Foto de la carga")}
                ${state.params.error ? `<p class="error">${esc(state.params.error)}</p>` : ""}
                <button class="primary" data-action="save-return">Generar devolución</button>
            </main>`;
    };

    // 13. Contrata: mis valorizaciones.
    screens.valuations = () => {
        const data = state.data.valuations || [];
        const orders = state.data.orders || [];
        const stateKind = { draft: "warn", submitted: "warn", validated: "", approved: "ok", paid: "ok" };
        return `${header("Valorizaciones y pagos", state.data.contract_partner || projectName(), "home")}
            <main class="page">
                ${orders
                    .map(
                        (o) => `<div class="card"><div class="row between"><b>Orden ${esc(o.name)} · ${esc(projectParts().code)}</b>
                        <small>${esc(join(o.frequency_label.toLowerCase(), o.cutoff_label ? "corte " + o.cutoff_label.toLowerCase() : ""))}</small></div>
                        <div class="bar-bg"><div class="bar-fill" style="width:${Math.min(100, o.valued_pct)}%"></div></div>
                        <div class="kv"><span>Contratado sin IGV</span><b>${money(o.amount_untaxed)}</b></div>
                        <div class="kv"><span>Valorizado (${o.valued_pct} %)</span><b>${money(o.valued)}</b></div>
                        <div class="kv"><span>Fondo de garantía retenido</span><b>${money(o.guarantee)}</b></div>
                        <div class="kv"><span>Deductivos</span><b>${money(o.deductions)}</b></div></div>`
                    )
                    .join("")}
                <h2>Valorizaciones</h2>
                ${data
                    .map((v) => {
                        const sub =
                            v.state === "draft"
                                ? join(`Corte el ${longDay(v.period_end).replace(/-\d{4}$/, "")}`, v.pending_progress ? `${v.pending_progress} ${v.pending_progress === 1 ? "avance" : "avances"} por validar` : "")
                                : join(range(v.period_start, v.period_end).replace(/^del/, "Del"), v.invoice ? "factura " + v.invoice : "");
                        return `<button class="card valuation" data-go="valuation" data-id="${v.id}">
                            <div class="row between"><b>${esc(v.title || v.name)}</b>${pill(v.state === "draft" ? "En preparación" : v.state_label, stateKind[v.state])}</div>
                            <small>${esc(sub)}</small>
                            ${v.state === "draft" ? "" : `<div class="kv"><span>Total con IGV</span><b>${money(v.amount_total)}</b></div>`}</button>`;
                    })
                    .join("") || '<p class="muted">Aún no tiene valorizaciones.</p>'}
            <button class="primary" data-go="partidas">Registrar avance</button></main>${nav("home")}`;
    };

    // 14. Contrata: detalle y pago.
    screens.valuation = () => {
        const v = state.params.detail;
        if (!v) {
            return `${header("Valorización", "", "valuations")}<main class="page"><p class="muted">${state.params.error ? esc(state.params.error) : "Cargando…"}</p></main>`;
        }
        const row = (label, value, cls) => `<div class="kv ${cls || ""}"><span>${esc(label)}</span><b>${value}</b></div>`;
        const paid = v.lines.filter((l) => !l.rework || l.paid_rework).sort((a, b) => b.amount - a.amount);
        const top = paid.slice(0, 3);
        const rest = paid.slice(3);
        const rework = v.lines.filter((l) => l.rework && !l.paid_rework);
        let payment = "Aún sin factura.";
        if (v.invoice) {
            const last = v.payments[v.payments.length - 1];
            payment =
                v.payment_code === "paid" || v.payment_code === "in_payment"
                    ? `Factura ${v.invoice} pagada${last ? ` el ${dayMonth(last.date)}` : ""} por ${money(v.amount_paid)}.`
                    : v.payment_code === "partial"
                    ? `Factura ${v.invoice}: pagado ${money(v.amount_paid)} de ${money(v.total)}${last ? `, el último el ${dayMonth(last.date)}` : ""}.`
                    : `Factura ${v.invoice} registrada. Pago pendiente según el programa semanal de pagos.`;
        }
        return `${header(v.title || v.name, join(v.name, range(v.period_start, v.period_end) + "-" + asDate(v.period_end).getFullYear()), "valuations")}
            <main class="page">
                <div class="card"><small class="eyebrow">Partidas con más avance</small>
                ${top.map((l) => row(l.name, num(l.amount))).join("")}
                ${rest.length ? row(`Otras ${rest.length} ${rest.length === 1 ? "partida" : "partidas"}`, num(rest.reduce((s, l) => s + l.amount, 0))) : ""}
                ${rework.map((l) => row(`Re-trabajo ${l.name} (${join(qtyText(l.qty) + " " + l.uom, (l.rework_reason || "").toLowerCase())})`, "rechazado, no se paga", "bad")).join("")}</div>
                <div class="card">${row("Avance del periodo", num(v.progress_total))}
                ${v.deductions.map((dd) => row("Deductivo: " + dd.name, num(dd.amount))).join("")}
                ${row("Subtotal", num(v.subtotal))}${row(`IGV ${v.tax_pct} %`, num(v.tax))}${row("Total de la factura", num(v.total))}
                ${row(`Fondo de garantía ${num(v.guarantee_pct, v.guarantee_pct % 1 ? 1 : 0)} % (cuota retenida)`, "−" + num(v.guarantee))}
                ${v.advance ? row("Amortización del adelanto", "−" + num(v.advance)) : ""}
                ${v.detraction ? row(`Detracción ${num(v.detraction_pct, 0)} % (Banco de la Nación)`, "−" + num(v.detraction)) : ""}
                ${row("Neto a su cuenta", money(v.net), "big")}</div>
                <p class="hint">${esc(payment)}</p>
                ${state.params.error ? `<p class="error">${esc(state.params.error)}</p>` : ""}
                <div class="row two"><button class="secondary" data-pdf="valuation">PDF del valorizado</button>
                ${v.has_invoice_pdf ? '<button class="secondary" data-pdf="invoice">Ver factura</button>' : ""}</div>
            </main>`;
    };

    // ------------------------------------------------------------------
    // Pintado y eventos
    // ------------------------------------------------------------------
    function render() {
        const screen = screens[state.route] || screens.home;
        $app().innerHTML = screen();
        if (state.route === "daily" || state.route === "change") {
            setupSignature();
        }
        // El Gantt abre con «hoy» a la vista.
        const gantt = document.querySelector(".gantt-scroll[data-today-x]");
        if (gantt) {
            gantt.scrollLeft = Math.max(0, Number(gantt.dataset.todayX) - gantt.clientWidth / 3);
        }
        if (state.route === "qr" && state.params.scanning) {
            attachScanner();
        }
    }

    function setPath(path, value) {
        const parts = path.split(".");
        if (parts[0] === "cartText") {
            state.draft.cartText = value;
            return;
        }
        let target = state.draft;
        for (let i = 0; i < parts.length - 1; i++) {
            target[parts[i]] = target[parts[i]] || {};
            target = target[parts[i]];
        }
        target[parts[parts.length - 1]] = value;
    }

    // Lector del QR con la cámara (BarcodeDetector del navegador).
    let scanner = null;
    function stopScanner() {
        if (scanner) {
            scanner.stream.getTracks().forEach((t) => t.stop());
            clearInterval(scanner.timer);
            scanner = null;
        }
    }
    async function startScanner() {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" } });
            scanner = { stream, detector: new window.BarcodeDetector({ formats: ["qr_code"] }) };
            state.params.scanning = true;
            render();
        } catch {
            state.params.error = "No se pudo abrir la cámara: escriba el código de la obra.";
            render();
        }
    }
    function attachScanner() {
        const video = document.getElementById("qr-video");
        if (!scanner || !video) return;
        video.srcObject = scanner.stream;
        video.play().catch(() => {});
        clearInterval(scanner.timer);
        scanner.timer = setInterval(async () => {
            try {
                const codes = await scanner.detector.detect(video);
                if (codes.length) {
                    const raw = codes[0].rawValue || "";
                    const match = raw.match(/[#&?]qr=([^&#]+)/);
                    const code = decodeURIComponent(match ? match[1] : raw);
                    stopScanner();
                    readSite(code);
                }
            } catch {
                // El cuadro aún no tiene un QR legible.
            }
        }, 400);
    }
    async function readSite(code) {
        try {
            const site = await call("/site/" + encodeURIComponent(code));
            go("qr", { site, code });
        } catch (error) {
            go("qr", { code, error: state.online ? error.message : "Sin señal: el ingreso por QR necesita conexión." });
        }
    }

    document.addEventListener("input", (event) => {
        const el = event.target;
        if (el.dataset.input === "q" || el.dataset.input === "tq") {
            const name = el.dataset.input;
            state.params[name] = el.value;
            const pos = el.selectionStart;
            render();
            const again = document.querySelector(`[data-input="${name}"]`);
            if (again) {
                again.focus();
                again.setSelectionRange(pos, pos);
            }
        } else if (el.dataset.bind) {
            setPath(el.dataset.bind, el.type === "checkbox" ? el.checked : el.value);
            if (el.dataset.edited) {
                state.draft[el.dataset.edited].edited = true;
            }
        }
    });

    document.addEventListener("change", async (event) => {
        const el = event.target;
        if (el.dataset.change === "project") {
            state.projectId = Number(el.value);
            state.data = null;
            state.draft = {};
            saveSession();
            await loadCache();
            render();
            await refresh();
            render();
        } else if (el.dataset.settlepick) {
            const id = Number(el.dataset.settlepick);
            const picked = state.draft.expense.picked;
            if (el.checked && !picked.includes(id)) picked.push(id);
            if (!el.checked && picked.includes(id)) picked.splice(picked.indexOf(id), 1);
            render();
        } else if (el.dataset.taskpick && el.dataset.taskpick.startsWith("expense:")) {
            // El gasto va a una sola partida.
            const id = Number(el.dataset.taskpick.split(":")[1]);
            state.draft.expense.task_ids = el.checked ? [id] : [];
            render();
        } else if (el.dataset.taskpick) {
            const [key, id] = el.dataset.taskpick.split(":");
            const list = state.draft[key].task_ids;
            const index = list.indexOf(Number(id));
            if (el.checked && index < 0) list.push(Number(id));
            if (!el.checked && index >= 0) list.splice(index, 1);
        } else if (el.dataset.rerender && el.dataset.bind) {
            setPath(el.dataset.bind, el.type === "checkbox" ? el.checked : el.value);
            render();
        } else if (el.dataset.pick) {
            const id = Number(el.dataset.pick);
            const picked = (state.draft.picked = state.draft.picked || []);
            if (el.checked && !picked.includes(id)) picked.push(id);
            if (!el.checked) picked.splice(picked.indexOf(id), 1);
            render();
        } else if (el.dataset.bind && /^val\d+\.qty$/.test(el.dataset.bind)) {
            render();
        } else if (el.tagName === "SELECT" && el.dataset.bind && /^(val|apr)\d+\./.test(el.dataset.bind)) {
            setPath(el.dataset.bind, el.value);
        } else if (el.dataset.return) {
            const id = el.dataset.return;
            const item = (state.data.returnables || []).find((it) => String(it.product_id) === id);
            if (el.checked) state.draft.ret.lines[id] = { qty: Math.min(1, item.qty) || item.qty, state: "good" };
            else delete state.draft.ret.lines[id];
            render();
        } else if (el.dataset.bind && el.dataset.bind.startsWith("crew.hours")) {
            // Solo el total de la persona: sin pintar de nuevo, el foco sigue
            // en la celda siguiente.
            const id = el.dataset.bind.split(".")[2].split(":")[0];
            const cell = document.querySelector(`[data-total="${id}"]`);
            const t = Object.entries(state.draft.crew.hours)
                .filter(([key]) => key.startsWith(id + ":"))
                .reduce((sum, [, h]) => sum + Number(h || 0), 0);
            if (cell) {
                cell.textContent = qtyText(t);
                cell.className = "strong " + (t === 8 ? "ok" : "bad");
            }
        } else if (el.dataset.bind && el.type === "checkbox") {
            setPath(el.dataset.bind, el.checked);
            if (el.dataset.bind === "progress.rework") {
                render();
            }
        } else if (el.dataset.bind === "progress.qty" || el.dataset.bind === "progress.pct") {
            render();
        } else if (el.dataset.toggle) {
            const [path, value] = el.dataset.toggle.split("=");
            const list = path.split(".").reduce((o, k) => o[k], state.draft);
            const index = list.indexOf(value);
            if (index >= 0) list.splice(index, 1);
            else list.push(value);
        } else if (el.dataset.photos) {
            const key = el.dataset.photos;
            const draft = state.draft[key];
            const max = MAX_PHOTOS[key] || 5;
            for (const file of el.files) {
                if (draft.photos.length >= max) break;
                try {
                    draft.photos.push(await compress(file));
                } catch {
                    // La foto que no se puede leer se omite.
                }
            }
            locate().then((pos) => {
                if (!state.data) return;
                if (!pos) {
                    draft.gps = { denied: true };
                } else {
                    const site = state.data.project;
                    const dist = site.latitude || site.longitude ? distance(pos, site) : undefined;
                    draft.gps = Object.assign(pos, { distance: dist, out: dist !== undefined && site.radius_m && dist > site.radius_m });
                }
                render();
            });
            render();
        }
    });

    document.addEventListener("submit", async (event) => {
        event.preventDefault();
        const form = event.target;
        const values = Object.fromEntries(new FormData(form).entries());
        try {
            if (form.dataset.form === "login") {
                state.remember = values.remember === "on";
                state.session = await call("/login", { login: values.login, password: values.password, device: navigator.userAgent });
            } else if (form.dataset.form === "qr-code") {
                return readSite(values.code);
            } else if (form.dataset.form === "pin") {
                state.remember = true;
                state.session = await call("/pin", { code: state.params.code, member_id: Number(values.member_id), pin: values.pin, device: navigator.userAgent });
            }
            saveSession();
            await refresh();
            go("home");
        } catch (error) {
            state.params.error = state.online ? error.message : "Sin señal: el ingreso necesita conexión.";
            render();
        }
    });

    function bump(value, delta, min, max) {
        return Math.min(max === undefined ? Infinity : max, Math.max(min || 0, Number(value || 0) + delta));
    }

    document.addEventListener("click", async (event) => {
        const el = event.target.closest("button, [data-go]");
        if (!el) {
            return;
        }
        const data = el.dataset;
        if (data.go) {
            event.preventDefault();
            if (data.go === "progress") {
                state.draft.progress = null;
            }
            if (data.go === "valuation") {
                go("valuation", { id: data.id });
                try {
                    const detail = await call(`/valuation/${state.projectId}/${data.id}`);
                    await cachePut("valuation:" + data.id, detail);
                    state.params.detail = detail;
                } catch (error) {
                    state.params.detail = await cacheGet("valuation:" + data.id);
                    state.params.error = state.params.detail ? "" : "Sin señal: abra esta valorización con conexión.";
                }
                return render();
            }
            const params = data.id ? { id: data.id } : {};
            if (data.tabGo) {
                params.tab = data.tabGo;
                params.order = state.route === "inbox" ? state.params.order : undefined;
            }
            return go(data.go, params);
        }
        if (data.filter) {
            state.params.filter = data.filter;
            return render();
        }
        if (data.view) {
            state.params.view = data.view;
            return render();
        }
        if (data.tfilter) {
            state.params.tfilter = data.tfilter;
            return render();
        }
        if (data.zoom) {
            state.params.zoom = data.zoom;
            return render();
        }
        if (data.task) {
            // La partida del tablero abre el registro de su avance.
            const line = ((state.data && state.data.partidas) || []).find((p) => p.task_id === Number(data.task));
            state.draft.progress = null;
            return line ? go("progress", { id: line.id }) : go("partidas", { q: "" });
        }
        if (data.order) {
            state.params.order = data.order;
            return render();
        }
        if (data.photo) {
            state.params.photo = Number(data.photo);
            return render();
        }
        if (data.photoClose) {
            state.params.photo = null;
            return render();
        }
        if (data.person !== undefined) {
            const p = state.draft.crewreq.people[Number(data.person)];
            p.count = bump(p.count, Number(data.delta));
            return render();
        }
        if (data.clearSign) {
            state.draft[data.clearSign].signature = "";
            return render();
        }
        if (data.valqty) {
            const row = state.data.resident.progress.find((x) => x.id === Number(data.valqty));
            const d = state.draft["val" + data.valqty];
            const step = row.qty >= 10 ? 1 : 0.5;
            d.qty = Math.round(bump(d.qty, Number(data.delta) * step, 0, row.qty) * 100) / 100;
            return render();
        }
        if (data.aprset) {
            const [req, line, qty] = data.aprset.split(":");
            state.draft["apr" + req].qty[line] = Number(qty);
            return render();
        }
        if (data.aprqty) {
            const [req, line] = data.aprqty.split(":");
            const row = state.data.resident.requests.find((x) => x.id === Number(req));
            const l = row.lines.find((x) => x.id === Number(line));
            const d = state.draft["apr" + req];
            d.qty[line] = bump(d.qty[line], Number(data.delta), 0, l.qty);
            return render();
        }
        if (data.tab) {
            state.params.tab = data.tab;
            return render();
        }
        if (data.set) {
            const [path, value] = data.set.split("=");
            setPath(path, value);
            return render();
        }
        if (data.step) {
            const d = state.draft.progress;
            const key = d.mode;
            d[key] = bump(d[key], Number(data.step) * (key === "pct" ? 5 : 0.5), 0, key === "pct" ? 100 : undefined);
            return render();
        }
        if (data.staff !== undefined) {
            const r = state.draft.daily.staff[Number(data.staff)];
            r.count = bump(r.count, Number(data.delta));
            return render();
        }
        if (data.received) {
            const [picking, move] = data.received.split(":");
            const d = state.draft["reception" + picking];
            d.received[move] = bump(d.received[move], Number(data.delta));
            return render();
        }
        if (data.ret) {
            const item = state.data.returnables.find((it) => String(it.product_id) === data.ret);
            const row = state.draft.ret.lines[data.ret];
            row.qty = bump(row.qty, Number(data.delta), Math.min(1, item.qty), item.qty);
            return render();
        }
        if (data.presence) {
            const a = (state.draft.crew.attendance[data.presence] = state.draft.crew.attendance[data.presence] || { time: "07:30" });
            a.present = !a.present;
            return render();
        }
        if (data.pdf) {
            return openPdf(`/valuation/${state.projectId}/${state.params.detail.id}/${data.pdf}.pdf`);
        }
        if (data.removePhoto) {
            const [key, index] = data.removePhoto.split(":");
            state.draft[key].photos.splice(Number(index), 1);
            return render();
        }
        if (data.cart) {
            const existing = state.cart.find((c) => c.key === data.cart);
            const delta = Number(data.delta);
            if (existing) {
                existing.qty = Math.max(0, existing.qty + delta);
                if (!existing.qty) state.cart.splice(state.cart.indexOf(existing), 1);
            } else if (delta > 0 && data.item) {
                state.cart.push(Object.assign(JSON.parse(data.item), { qty: 1 }));
            }
            return render();
        }
        if (data.kit) {
            const [tab, id] = data.kit.split(":");
            const kit = state.data.catalog[tab].kits.find((k) => k.id === Number(id));
            for (const line of kit.lines) {
                const key = `${tab}:${line.product_id}`;
                const existing = state.cart.find((c) => c.key === key);
                if (existing) existing.qty += line.qty;
                else state.cart.push({ key, catalog: tab, product_id: line.product_id, name: line.name, uom: line.uom, dest: "Gastos generales de la obra", qty: line.qty });
            }
            return render();
        }
        if (data.discard) {
            await queueDelete(data.discard);
            state.queue = await queueAll();
            return render();
        }
        if (data.retry) {
            const item = state.queue.find((q) => q.uuid === data.retry);
            item.status = "pending";
            item.error = "";
            await queuePut(item);
            return flush();
        }
        if (data.action) {
            return actions[data.action] && actions[data.action](el);
        }
    });

    // ------------------------------------------------------------------
    // Acciones (cada registro va a la cola)
    // ------------------------------------------------------------------
    const actions = {
        logout: () => logout(),
        sync: async () => {
            await refresh();
            render();
        },
        flush: () => {
            if (!navigator.onLine) {
                state.params.error = "Sin señal: se reintenta solo cuando vuelva la conexión.";
                return render();
            }
            state.params.error = "";
            return flush();
        },
        // Sin pintar de nuevo: no se pierde lo escrito.
        "toggle-password": (el) => {
            const input = el.parentElement.querySelector("input");
            input.type = input.type === "password" ? "text" : "password";
        },
        "scan-qr": () => (scanner ? null : startScanner()),
        "show-other": () => {
            state.params.other = true;
            render();
        },
        "add-staff": () => {
            state.draft.daily.staff.push({ name: "", source: "contract", count: 0, custom: true });
            render();
        },
        "add-text": () => {
            const text = (state.draft.cartText || "").trim();
            if (text) {
                state.cart.push({ key: "text:" + uuid(), catalog: "text", name: text, qty: 1 });
                state.draft.cartText = "";
                state.params.other = false;
            }
            render();
        },
        "clear-signature": () => {
            state.draft.daily.signature = "";
            render();
        },
        "resident-progress": async (el) => {
            const id = Number(el.dataset.id);
            const kind = el.dataset.kind;
            const row = state.data.resident.progress.find((x) => x.id === id);
            const d = state.draft["val" + id];
            const payload = { uuid: uuid(), project_id: state.projectId, action: kind, items: [{ id, seen_qty: row.qty }], comment: d.comment || "" };
            let label;
            if (kind === "validate") {
                const qty = Number(d.qty);
                if (!(qty > 0) || qty > row.qty + 1e-6) {
                    return alertInline(`La cantidad validada va de más de 0 a ${qtyText(row.qty)} ${row.uom}.`);
                }
                if (qty < row.qty - 1e-6) {
                    if (!d.reason) return alertInline("Elija el motivo de la corrección.");
                    payload.qty = qty;
                    payload.reason_id = Number(d.reason);
                }
                label = `Validar ${row.name}: ${qtyText(qty)} ${row.uom}`;
            } else if (kind === "reject") {
                if (!d.reason) return alertInline("Elija el motivo del rechazo.");
                payload.reason_id = Number(d.reason);
                label = `Rechazar ${row.name}`;
            } else {
                if (!d.rework) return alertInline("Elija el motivo del re-trabajo.");
                payload.rework_reason = d.rework;
                label = `Re-trabajo ${row.name}`;
            }
            await enqueue("resident_progress", "/resident/progress", payload, `${label} · ${taskName(row)}`);
            state.draft["val" + id] = null;
            dropFromInbox("progress", [id]);
            go("inbox", { tab: "progress", order: state.params.order, flash: `${label}: ${state.online ? "enviado a Odoo." : "en «Por enviar»; Odoo lo confirma al volver la señal."}` });
        },
        "resident-batch": async () => {
            const picked = state.draft.picked || [];
            const rows = state.data.resident.progress.filter((x) => picked.includes(x.id) && !(x.warnings || []).length);
            if (!rows.length) return;
            const payload = { uuid: uuid(), project_id: state.projectId, action: "validate", items: rows.map((x) => ({ id: x.id, seen_qty: x.qty })) };
            await enqueue("resident_progress", "/resident/progress", payload, `Validar ${rows.length} ${rows.length === 1 ? "avance" : "avances"} sin aviso`);
            state.draft.picked = [];
            dropFromInbox("progress", rows.map((x) => x.id));
            go("inbox", { tab: "progress", flash: `${rows.length} ${rows.length === 1 ? "avance validado" : "avances validados"}${state.online ? "." : "; quedan en «Por enviar»."}` });
        },
        "resident-request": async (el) => {
            const id = Number(el.dataset.id);
            const kind = el.dataset.kind;
            const row = state.data.resident.requests.find((x) => x.id === id);
            const d = state.draft["apr" + id];
            const payload = { uuid: uuid(), project_id: state.projectId, request_id: id, action: kind, seen: row.seen, comment: d.comment || "" };
            if (kind === "approve") {
                if (row.lines.some((l) => !(Number(d.qty[l.id]) > 0))) {
                    return alertInline("Cada línea aprobada lleva una cantidad mayor que cero; si no va, rechace el requerimiento.");
                }
                payload.lines = row.lines.map((l) => ({ id: l.id, qty: Number(d.qty[l.id]) }));
            } else {
                if (!d.reason) return alertInline("Elija el motivo del rechazo.");
                payload.reason_id = Number(d.reason);
            }
            const label = `${kind === "approve" ? "Aprobar" : "Rechazar"} ${row.name}`;
            await enqueue("resident_request", "/resident/request", payload, label);
            state.draft["apr" + id] = null;
            dropFromInbox("requests", [id]);
            go("inbox", { tab: "requests", flash: `${label}: ${state.online ? "enviado a Odoo." : "en «Por enviar»; Odoo lo confirma al volver la señal."}` });
        },
        "push-enable": async () => {
            state.params.pushError = "";
            try {
                await enablePush();
                state.params.pushDone = true;
            } catch (error) {
                state.params.pushError = state.online ? error.message : "Sin señal: active los avisos con conexión.";
            }
            render();
        },
        "push-dismiss": () => {
            try {
                localStorage.setItem("obra-push-dismissed", "1");
            } catch {
                // Sin almacenamiento: se oculta solo en esta sesión.
            }
            state.params.pushDone = true;
            render();
        },
        "save-expense": async () => {
            const d = state.draft.expense;
            if (!d.photos.length) return alertInline("Tome la foto del comprobante.");
            if (!d.doc_type) return alertInline("Elija el tipo de comprobante.");
            if (!/^\d{11}$/.test(d.ruc)) return alertInline("El RUC del emisor tiene 11 dígitos.");
            if (!d.number.trim()) return alertInline("Indique la serie y el número del comprobante.");
            if (!(Number(d.amount) > 0)) return alertInline("Indique el monto del comprobante.");
            if (!d.general && !d.task_ids.length) return alertInline("Elija la partida o marque gastos generales de la obra.");
            const payload = {
                uuid: uuid(), project_id: state.projectId, fund_id: Number(d.fund), doc_type_id: Number(d.doc_type),
                ruc: d.ruc, number: d.number.trim().toUpperCase(), date: d.date, amount: Number(d.amount),
                task_id: d.general ? false : d.task_ids[0], description: d.description, photos: d.photos,
            };
            await enqueue("expense", "/resident/expense", payload, `Comprobante ${payload.number}: ${num(payload.amount)}`);
            state.draft.expense = Object.assign({}, d, { doc_type: "", ruc: "", number: "", amount: "", description: "", photos: [], task_ids: [] });
            go("queue", { saved: "expense" });
        },
        settle: async () => {
            const d = state.draft.expense;
            if (!d.picked.length) return alertInline("Marque los comprobantes que rinde.");
            await enqueue("settle", "/resident/settle", { uuid: uuid(), project_id: state.projectId, fund_id: Number(d.fund), receipt_ids: d.picked }, `Rendición de ${d.picked.length} ${d.picked.length === 1 ? "comprobante" : "comprobantes"}`);
            const fund = resident().cash.funds.find((f) => String(f.id) === String(d.fund));
            fund.receipts.forEach((r) => {
                if (d.picked.includes(r.id)) {
                    r.state = "sent";
                    r.state_label = "Rendido";
                }
            });
            d.picked = [];
            go("queue", { saved: "settle" });
        },
        "add-person": () => {
            state.draft.crewreq.people.push({ role: "", count: 1 });
            render();
        },
        "close-day": async () => {
            const p = resident().parts;
            const d = state.draft.closeDay;
            const payload = { uuid: uuid(), project_id: state.projectId, date: p.date, comment: d.comment || "", seen_report_ids: p.reports.map((r) => r.id) };
            await enqueue("close_day", "/resident/close-day", payload, `Cerrar el día ${dayMonth(p.date)}`);
            state.draft.closeDay = null;
            p.site = { id: 0, state: "closed", comment: d.comment };
            p.reports.forEach((r) => (r.state = "reviewed"));
            state.data.counters.daily_to_review = 0;
            go("queue", { saved: "close_day" });
        },
        "save-change": async () => {
            const d = state.draft.change;
            const canvas = document.getElementById("signature");
            const signature = d.signature || (canvas && canvas.dataset.signed ? canvas.toDataURL("image/png") : "");
            if (!d.description.trim()) return alertInline("Describa el cambio que pide el cliente.");
            if (!d.task_ids.length && !d.new_item.trim()) return alertInline("Elija las partidas afectadas o describa la partida nueva.");
            if (!d.photos.length) return alertInline("Tome al menos una foto.");
            if (!d.rep_name.trim()) return alertInline("Indique quién lo pidió por el cliente.");
            if (!signature) return alertInline("Falta la firma de quien lo pidió.");
            const payload = Object.assign({ uuid: uuid(), project_id: state.projectId, date: today() }, d, { signature });
            await enqueue("change_order", "/resident/change-order", payload, `Cambio del cliente: ${d.description.slice(0, 40)}`);
            state.draft.change = null;
            go("queue", { saved: "change_order" });
        },
        "save-deduction": async () => {
            const d = state.draft.deduction;
            if (!d.order) return alertInline("Elija la orden de la contrata.");
            if (!d.type) return alertInline("Elija el motivo del deductivo.");
            if (!d.description.trim()) return alertInline("Describa el deductivo.");
            const byQty = d.mode === "qty" && d.line;
            if (!(Number(byQty ? d.qty : d.amount) > 0)) return alertInline(byQty ? "Indique la cantidad." : "Indique el monto.");
            if (!d.photos.length) return alertInline("Tome al menos una foto.");
            const order = resident().orders.find((o) => String(o.id) === String(d.order));
            const payload = {
                uuid: uuid(), project_id: state.projectId, date: today(), purchase_order_id: Number(d.order),
                order_line_id: Number(d.line) || false, type_id: Number(d.type), description: d.description,
                amount: byQty ? 0 : Number(d.amount), qty: byQty ? Number(d.qty) : 0, photos: d.photos,
            };
            await enqueue("deduction", "/resident/deduction", payload, `Deductivo a ${order ? order.partner : "la contrata"}`);
            state.draft.deduction = null;
            go("queue", { saved: "deduction" });
        },
        "save-crewreq": async () => {
            const d = state.draft.crewreq;
            if (!d.task_ids.length) return alertInline("Elija las partidas.");
            if (!d.date_needed) return alertInline("Indique la fecha en que se necesita.");
            if (d.kind === "crew" && !d.people.some((p) => p.role && p.count > 0)) return alertInline("Indique cuántas personas y de qué rol.");
            if (d.kind === "contract" && !d.scope.trim()) return alertInline("Indique el metrado que hará la contrata.");
            const payload = Object.assign({ uuid: uuid(), project_id: state.projectId }, d, { people: d.people.filter((p) => p.role && p.count > 0) });
            await enqueue("crew_request", "/resident/crew-request", payload, `Pedir ${d.kind === "crew" ? "cuadrilla adicional" : "contrata"} para el ${dayMonth(d.date_needed)}`);
            state.draft.crewreq = null;
            go("queue", { saved: "crew_request" });
        },
        "save-progress": async () => {
            const d = state.draft.progress;
            const line = state.data.partidas.find((p) => p.id === Number(state.params.id));
            if (progressCheck(line, d).blocked) {
                return alertInline("El avance supera el saldo de la partida y la tolerancia del plan.");
            }
            if (!d.photos.length) {
                return alertInline("Tome al menos una foto del avance.");
            }
            if (d.rework && !d.reason) {
                return alertInline("Elija el motivo del re-trabajo.");
            }
            const pos = (d.gps && !d.gps.denied && d.gps) || (await locate()) || {};
            const payload = {
                uuid: uuid(), project_id: state.projectId, plan_line_id: line.id, date: d.date,
                mode: d.mode, qty: Number(d.qty || 0), pct: Number(d.pct || 0),
                is_rework: !!d.rework, rework_reason: d.reason || false, note: d.note,
                latitude: pos.latitude || 0, longitude: pos.longitude || 0, photos: d.photos,
            };
            const amount = d.mode === "pct" ? d.pct + " %" : qtyText(d.qty) + " " + line.uom;
            await enqueue("progress", "/progress", payload, `Avance ${line.item} ${line.name}: ${amount}`);
            state.draft.progress = null;
            go("queue", { saved: "progress" });
        },
        "save-daily": async () => {
            const d = state.draft.daily;
            const canvas = document.getElementById("signature");
            const payload = {
                uuid: uuid(), project_id: state.projectId, date: d.date, weather: d.weather,
                staff: d.staff.filter((r) => r.name).map((r) => ({ name: r.name, source: r.source, count: Number(r.count || 0) })),
                restrictions: d.restrictions, occurrences: d.occurrences, photos: d.photos,
                signature: d.signature || (canvas && canvas.dataset.signed ? canvas.toDataURL("image/png") : ""),
            };
            await enqueue("daily_report", "/daily-report", payload, `Parte diario del ${dayMonth(d.date)}`);
            state.draft.daily = null;
            go("queue", { saved: "daily_report" });
        },
        "save-crew": async () => {
            const d = state.draft.crew;
            const payload = {
                uuid: uuid(), project_id: state.projectId, date: d.date,
                attendance: Object.entries(d.attendance).map(([id, a]) => ({ employee_id: Number(id), present: !!a.present, time: a.time })),
                hours: Object.entries(d.hours)
                    .filter(([key, h]) => Number(h) > 0 && (d.attendance[key.split(":")[0]] || {}).present)
                    .map(([key, h]) => ({ employee_id: Number(key.split(":")[0]), plan_line_id: Number(key.split(":")[1]), hours: Number(h) })),
            };
            const present = payload.attendance.filter((a) => a.present).length;
            await enqueue("crew_day", "/crew-day", payload, `Asistencia de la cuadrilla y tareo del ${dayMonth(d.date)}: ${present} ${present === 1 ? "persona" : "personas"}`);
            state.draft.crew = null;
            go("queue", { saved: "crew_day" });
        },
        "save-request": async () => {
            const d = state.draft.request;
            const payload = {
                uuid: uuid(), project_id: state.projectId, date_required: d.date_required,
                priority: d.priority, note: d.note,
                lines: state.cart.map((c) =>
                    c.catalog === "text"
                        ? { catalog: "partida", text: c.name, qty: 1 }
                        : { catalog: c.catalog, product_id: c.product_id, task_id: c.task_id || false, qty: c.qty }
                ),
            };
            await enqueue("material_request", "/material-request", payload, `Requerimiento de ${state.cart.length} ${state.cart.length === 1 ? "ítem" : "ítems"}`);
            state.cart = [];
            state.draft.request = null;
            go("queue", { saved: "material_request" });
        },
        "save-reception": async (el) => {
            const id = Number(el.dataset.id);
            const d = state.draft["reception" + id];
            if (!d.photos.length) {
                return alertInline("Tome la foto de la guía firmada.");
            }
            const picking = state.data.deliveries.find((p) => p.id === id);
            const note = document.querySelector(`[data-bind="reception${id}.note"]`);
            const payload = {
                uuid: uuid(), project_id: state.projectId, picking_id: id, note: note ? note.value : d.note, photos: d.photos,
                lines: Object.entries(d.received).map(([move, qty]) => ({ move_id: Number(move), qty: Number(qty) })),
            };
            await enqueue("reception", "/reception", payload, `Recepción de ${picking.name}`);
            state.data.deliveries = state.data.deliveries.filter((p) => p.id !== id);
            state.draft["reception" + id] = null;
            go("queue", { saved: "reception" });
        },
        "save-return": async () => {
            const d = state.draft.ret;
            const lines = Object.entries(d.lines)
                .filter(([, row]) => Number(row.qty) > 0)
                .map(([product, row]) => ({ product_id: Number(product), qty: Number(row.qty), state: row.state || "good" }));
            if (!lines.length) {
                return alertInline("Elija lo que devuelve.");
            }
            if (!d.photos.length) {
                return alertInline("Tome la foto de la carga.");
            }
            if (lines.some((line) => line.state === "damaged") && !(d.note || "").trim()) {
                return alertInline("Indique el motivo de lo dañado.");
            }
            await enqueue("return", "/return", { uuid: uuid(), project_id: state.projectId, transport: d.transport, note: d.note || "", photos: d.photos, lines }, `Devolución de ${lines.length} ${lines.length === 1 ? "producto" : "productos"}`);
            state.draft.ret = null;
            go("queue", { saved: "return" });
        },
    };
    function alertInline(message) {
        state.params.error = message;
        render();
    }

    function setupSignature() {
        const canvas = document.getElementById("signature");
        if (!canvas) {
            return;
        }
        const ctx = canvas.getContext("2d");
        ctx.lineWidth = 2.5;
        ctx.lineCap = "round";
        let drawing = false;
        const point = (e) => {
            const rect = canvas.getBoundingClientRect();
            const t = e.touches ? e.touches[0] : e;
            return [((t.clientX - rect.left) * canvas.width) / rect.width, ((t.clientY - rect.top) * canvas.height) / rect.height];
        };
        const start = (e) => {
            drawing = true;
            const hint = canvas.parentElement.querySelector(".sign-hint");
            if (hint) hint.remove();
            ctx.beginPath();
            ctx.moveTo(...point(e));
            e.preventDefault();
        };
        const move = (e) => {
            if (!drawing) return;
            ctx.lineTo(...point(e));
            ctx.stroke();
            canvas.dataset.signed = "1";
            e.preventDefault();
        };
        // El borrador que guarda la firma: el parte diario o el cambio del cliente.
        const key = canvas.dataset.sign || "daily";
        const end = () => {
            if (drawing && canvas.dataset.signed && state.draft[key]) {
                state.draft[key].signature = canvas.toDataURL("image/png");
            }
            drawing = false;
        };
        canvas.addEventListener("pointerdown", start);
        canvas.addEventListener("pointermove", move);
        window.addEventListener("pointerup", end, { once: false });
        if (state.draft[key] && state.draft[key].signature) {
            const img = new Image();
            img.onload = () => ctx.drawImage(img, 0, 0);
            img.src = state.draft[key].signature;
            canvas.dataset.signed = "1";
        }
    }

    // ------------------------------------------------------------------
    // Arranque
    // ------------------------------------------------------------------
    window.addEventListener("online", () => {
        state.online = true;
        flush();
        refresh().then(render);
    });
    window.addEventListener("offline", () => {
        state.online = false;
        render();
    });
    if (navigator.serviceWorker) {
        navigator.serviceWorker.register("/obra/app/sw.js", { scope: "/obra/app/" }).catch(() => {});
        navigator.serviceWorker.addEventListener("message", (event) => {
            if (event.data && event.data.type === "flush") flush();
            if (event.data && event.data.type === "open") {
                refresh().then(() => openRecord(event.data.model, event.data.res_id));
            }
        });
    }

    async function start() {
        loadSession();
        state.queue = await queueAll().catch(() => []);
        const hash = new URLSearchParams(location.hash.slice(1));
        if (hash.get("qr") && !state.session) {
            history.replaceState(null, "", location.pathname);
            return readSite(hash.get("qr"));
        }
        if (!state.session) {
            return go("login");
        }
        await loadCache();
        // Desde un aviso: abre la pantalla de su registro con los datos al día.
        const open = hash.get("open");
        if (open) {
            history.replaceState(null, "", location.pathname);
        }
        go("home");
        await refresh();
        // Con el permiso ya dado, el celular queda registrado en este Odoo.
        if (pushSupported() && Notification.permission === "granted" && state.session) {
            enablePush().catch(() => {});
        }
        if (open) {
            const [model, resId] = open.split(":");
            return openRecord(model, resId);
        }
        render();
        flush();
    }
    start();
})();

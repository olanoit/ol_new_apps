/* Portal de obra (requerimiento CREVAL v1.0, 4.11).
 *
 * Aplicación web instalable para capataces, contratas y oficina técnica.
 * Trabaja sin señal: guarda en el equipo los datos de la obra (partidas,
 * catálogo, cuadrilla, entregas y valorizaciones) y deja cada registro en una
 * cola con sus fotos comprimidas, que se envía al volver la conexión. Cada
 * registro lleva un identificador único: Odoo no lo duplica si el envío se
 * repite y vuelve a validar sus reglas al recibirlo.
 *
 * Usa solo los servicios JSON /construction/api/v1 (los mismos que usará una
 * aplicación nativa). */
(function () {
    "use strict";

    const API = "/construction/api/v1";
    const state = {
        session: null, // {token, name}
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
    const money = (value) => "S/ " + num(value, 2);
    const today = () => new Date(Date.now() - new Date().getTimezoneOffset() * 60000)
        .toISOString().slice(0, 10);
    const uuid = () =>
        (crypto.randomUUID && crypto.randomUUID()) ||
        "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => {
            const r = (Math.random() * 16) | 0;
            return (c === "x" ? r : (r & 0x3) | 0x8).toString(16);
        });
    const role = (name) => state.data && state.data.roles.includes(name);

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

    function loadSession() {
        try {
            state.session = JSON.parse(localStorage.getItem("obra-session") || "null");
            state.projectId = Number(localStorage.getItem("obra-project")) || null;
        } catch {
            state.session = null;
        }
    }
    function saveSession() {
        try {
            if (state.session) {
                localStorage.setItem("obra-session", JSON.stringify(state.session));
            } else {
                localStorage.removeItem("obra-session");
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
        home: '<path d="M3 10.5L12 3l9 7.5V21h-6v-6H9v6H3z"/>',
        chart: '<path d="M3 3v18h18"/><path d="M7 15l4-4 3 3 6-6"/>',
        cart: '<path d="M3 4h2l2.4 11.2a2 2 0 0 0 2 1.6h7.7a2 2 0 0 0 2-1.5L21 8H6.2"/>',
        sync: '<path d="M21 12a9 9 0 1 1-3-6.7L21 8"/><path d="M21 3v5h-5"/>',
        camera:
            '<path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"/><circle cx="12" cy="13" r="4"/>',
        report: '<rect x="5" y="3" width="14" height="18" rx="2"/><path d="M9 11h6M9 15h4"/>',
        crew: '<circle cx="9" cy="8" r="3.5"/><path d="M2.5 20a6.5 6.5 0 0 1 13 0"/>',
        truck: '<rect x="1" y="6" width="14" height="10"/><path d="M15 9h4l3 3v4h-7"/>',
        undo: '<path d="M9 14L4 9l5-5"/><path d="M4 9h10.5a5.5 5.5 0 0 1 0 11H11"/>',
        doc: '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/>',
        offline: '<path d="M1 1l22 22M8.5 16.1a5 5 0 0 1 7 0M12 20h.01"/>',
    };
    const svg = (name, size = 24) =>
        `<svg width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${icon[name]}</svg>`;

    function header(title, sub, back) {
        return `<header class="bar">${
            back
                ? `<button class="icon-btn" data-go="${back}" aria-label="Volver">${svg("back")}</button>`
                : `<div class="logo">${esc(((state.me && state.me.company.name) || "Obra").slice(0, 2).toUpperCase())}</div>`
        }<div class="bar-title"><span>${esc(title)}</span>${sub ? `<small>${esc(sub)}</small>` : ""}</div></header>${
            state.online
                ? ""
                : `<div class="offline">${svg("offline", 20)}<span><b>Sin señal.</b> ${pendingText()}</span></div>`
        }`;
    }
    function pendingText() {
        const count = state.queue.filter((q) => q.status === "pending").length;
        if (!count) {
            return "Lo que registre se enviará al volver la conexión.";
        }
        return count === 1 ? "1 registro espera para enviarse." : `${count} registros esperan para enviarse.`;
    }

    function nav(active) {
        const items = [
            ["home", "home", "Inicio"],
            ["partidas", "chart", "Avance"],
            ["catalog", "cart", "Pedidos"],
            ["queue", "sync", "Por enviar"],
        ];
        const pending = state.queue.filter((q) => q.status !== "done").length;
        return `<nav class="nav" aria-label="Navegación principal">${items
            .map(
                ([route, ic, label]) =>
                    `<button data-go="${route}" class="${active === route ? "active" : ""}">${svg(ic)}<span>${label}${
                        route === "queue" && pending ? ` (${pending})` : ""
                    }</span></button>`
            )
            .join("")}</nav>`;
    }
    const projectName = () =>
        (state.data && state.data.project.name) ||
        (state.me && (state.me.projects.find((p) => p.id === state.projectId) || {}).name) ||
        "";

    // ------------------------------------------------------------------
    // Pantallas
    // ------------------------------------------------------------------
    const screens = {};

    screens.login = () => `
        <header class="bar"><div class="logo">OB</div><div class="bar-title"><span>Portal de obra</span></div></header>
        <main class="page">
            <h1>Portal de obra</h1>
            <p class="muted">Avance, parte diario, cuadrilla, requerimientos y recepción de la obra.</p>
            <form class="card form" data-form="login">
                <label>Usuario<input name="login" autocomplete="username" required></label>
                <label>Contraseña<input name="password" type="password" autocomplete="current-password" required></label>
                ${state.params.error ? `<p class="error">${esc(state.params.error)}</p>` : ""}
                <button class="primary" type="submit">Ingresar</button>
            </form>
            <div class="or"><span>o</span></div>
            <button class="secondary" data-go="qr">Ingresar con el QR de la obra</button>
            <p class="hint">Instálelo con «Agregar a la pantalla de inicio». Lo que registre sin señal se envía solo al volver la conexión.</p>
        </main>`;

    screens.qr = () => {
        const site = state.params.site;
        if (!site) {
            return `${header("Ingresar con el QR", "", "login")}
            <main class="page"><form class="card form" data-form="qr-code">
                <p class="muted">Escanee el QR del cartel de la obra con la cámara del celular o escriba su código.</p>
                <label>Código de la obra<input name="code" required value="${esc(state.params.code || "")}"></label>
                ${state.params.error ? `<p class="error">${esc(state.params.error)}</p>` : ""}
                <button class="primary" type="submit">Continuar</button></form></main>`;
        }
        return `${header("Ingresar con el QR", "", "login")}
            <main class="page">
                <div class="card ok-row"><b>${esc(site.project)}</b><small>Obra leída</small></div>
                <h2>¿Quién es usted?</h2>
                <form data-form="pin" class="form">
                    <div class="card list">${site.members
                        .map(
                            (m) => `<label class="pick"><input type="radio" name="member_id" value="${m.id}" ${m.locked ? "disabled" : ""} required>
                            <span><b>${esc(m.name)}</b><small>${esc(m.role)}${m.locked ? " · bloqueado" : ""}</small></span></label>`
                        )
                        .join("")}</div>
                    <label>PIN de 4 dígitos<input name="pin" type="password" inputmode="numeric" pattern="[0-9]{4}" maxlength="4" required></label>
                    ${state.params.error ? `<p class="error">${esc(state.params.error)}</p>` : ""}
                    <button class="primary" type="submit">Ingresar</button>
                </form>
            </main>`;
    };

    screens.home = () => {
        if (!state.me) {
            return `${header("Portal de obra")}<main class="page"><p class="muted">Cargando…</p></main>`;
        }
        const data = state.data;
        const projects = state.me.projects;
        const partidas = (data && data.partidas) || [];
        const toValidate = partidas.filter((p) => p.pending > 0).length;
        const deliveries = (data && data.deliveries) || [];
        const tiles = [];
        if (data) {
            tiles.push(["partidas", "chart", "Avance"]);
            if (role("foreman") || role("office")) {
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
        return `${header("Portal de obra")}
            <main class="page">
                <label class="card select">Obra
                    <select data-change="project">${projects
                        .map((p) => `<option value="${p.id}" ${p.id === state.projectId ? "selected" : ""}>${esc(p.name)}</option>`)
                        .join("")}</select>
                </label>
                ${
                    data
                        ? `<div class="stats"><div class="card"><b>${toValidate}</b><small>partidas por validar</small></div>
                           <div class="card"><b>${state.queue.filter((q) => q.status !== "done").length}</b><small>por enviar</small></div>
                           <div class="card"><b class="accent">${deliveries.length}</b><small>entregas por recibir</small></div></div>
                           <div class="tiles">${tiles
                               .map(([route, ic, label]) => `<button class="tile" data-go="${route}">${svg(ic, 28)}<span>${label}</span></button>`)
                               .join("")}</div>
                           ${
                               role("contractor")
                                   ? `<button class="card row-link" data-go="valuations">${svg("doc", 26)}<span><b>Valorizaciones y pagos</b><small>Su orden, fondo de garantía y deductivos</small></span></button>`
                                   : ""
                           }
                           <p class="hint">Datos de la obra del ${esc((data.synced_at || "").replace("T", " ").slice(0, 16))}.
                           <button class="link" data-action="sync">Actualizar</button></p>`
                        : `<p class="muted">${projects.length ? "Sin datos de la obra: conéctese para descargarlos." : "No está en el portal de ninguna obra."}</p>`
                }
                <button class="link" data-action="logout">Salir</button>
            </main>${nav("home")}`;
    };

    screens.partidas = () => {
        const data = state.data || { partidas: [] };
        const filter = state.params.filter || "all";
        const q = (state.params.q || "").toLowerCase();
        const rows = data.partidas.filter(
            (p) =>
                (filter === "all" || (filter === "pending" ? p.pending > 0 : p.balance > 0)) &&
                (!q || (p.item + " " + p.name + " " + p.activity).toLowerCase().includes(q))
        );
        const chip = (key, label) =>
            `<button class="chip ${filter === key ? "on" : ""}" data-filter="${key}">${label}</button>`;
        return `${header("Avance", projectName(), "home")}
            <main class="page">
                <input class="search" type="search" placeholder="Buscar partida o ítem" value="${esc(state.params.q || "")}" data-input="q" aria-label="Buscar partida">
                <div class="chips">${chip("all", "Todas")}${chip("pending", "Por validar")}${chip("balance", "Con saldo")}</div>
                ${rows
                    .map((p) => {
                        const pct = p.planned ? Math.min(100, (100 * p.validated) / p.planned) : 0;
                        return `<button class="card partida" data-go="progress" data-id="${p.id}">
                            <div class="row"><span class="tag">${esc(p.item)}</span><b>${esc(p.name)}</b></div>
                            <small>${esc(p.activity)}</small>
                            <div class="bar-bg"><div class="bar-fill" style="width:${pct}%"></div></div>
                            <div class="row between"><small>${num(p.validated)} de ${num(p.planned)} ${esc(p.uom)}</small>
                            <small class="${p.pending > 0 ? "warn" : ""}">${p.pending > 0 ? num(p.pending) + " por validar" : "Saldo " + num(p.balance)}</small></div>
                        </button>`;
                    })
                    .join("") || '<p class="muted">Sin partidas.</p>'}
            </main>${nav("partidas")}`;
    };

    screens.progress = () => {
        const line = ((state.data && state.data.partidas) || []).find((p) => p.id === Number(state.params.id));
        if (!line) {
            return screens.partidas();
        }
        const d = (state.draft.progress = state.draft.progress || {
            date: today(), mode: "qty", qty: 0, pct: 0, photos: [], rework: false, reason: "", note: "",
        });
        const value = d.mode === "pct" ? d.pct : d.qty;
        const over = d.mode === "pct" ? d.pct > 100 : d.qty > line.balance;
        return `${header("Registrar avance", "", "partidas")}
            <main class="page">
                <div class="card">
                    <div class="row"><span class="tag">${esc(line.item)}</span><small>${esc(line.path)}</small></div>
                    <b>${esc(line.name)}</b><small>${esc(line.activity)}</small>
                    <div class="grid4"><span>Plan<b>${num(line.planned)}</b></span><span>Validado<b>${num(line.validated)}</b></span>
                    <span>Por validar<b class="warn">${num(line.pending)}</b></span><span>Saldo ${esc(line.uom)}<b class="accent">${num(line.balance)}</b></span></div>
                </div>
                <div class="card form">
                    <label>Fecha de ejecución<input type="date" data-bind="progress.date" value="${esc(d.date)}" max="${today()}"></label>
                    <div class="toggle"><button class="${d.mode === "qty" ? "on" : ""}" data-set="progress.mode=qty">Metrado (${esc(line.uom)})</button>
                    <button class="${d.mode === "pct" ? "on" : ""}" data-set="progress.mode=pct">Porcentaje</button></div>
                    <div class="stepper"><button data-step="-1" aria-label="Restar">−</button>
                    <input type="number" step="0.01" inputmode="decimal" data-bind="progress.${d.mode}" value="${value}" aria-label="Cantidad">
                    <button data-step="1" aria-label="Sumar">+</button></div>
                    <small class="muted">${d.mode === "pct" ? "% acumulado de la partida" : esc(line.uom) + " de hoy"}</small>
                    ${over ? '<p class="alert">Supera el saldo de la partida: se envía como exceso y lo aprueba la jefatura.</p>' : ""}
                </div>
                ${photosCard("progress", d, true)}
                <div class="card form">
                    <label class="check"><input type="checkbox" data-bind="progress.rework" ${d.rework ? "checked" : ""}> Es re-trabajo (no se paga)</label>
                    ${
                        d.rework
                            ? `<label>Motivo<select data-bind="progress.reason"><option value=""></option>${(state.data.rework_reasons || [])
                                  .map(([code, label]) => `<option value="${code}" ${d.reason === code ? "selected" : ""}>${esc(label)}</option>`)
                                  .join("")}</select></label>`
                            : ""
                    }
                    <label>Observación<textarea rows="2" data-bind="progress.note" placeholder="Opcional">${esc(d.note)}</textarea></label>
                </div>
                ${state.params.error ? `<p class="error">${esc(state.params.error)}</p>` : ""}
                <button class="primary" data-action="save-progress">Guardar avance</button>
            </main>`;
    };

    function photosCard(key, draft, required) {
        return `<div class="card form"><div class="row between"><b>Fotos</b><small class="muted">${required ? "obligatoria al menos una" : "opcional"}</small></div>
            <div class="photos">${draft.photos
                .map((p, i) => `<div class="thumb" style="background-image:url(${p.data})"><button data-remove-photo="${key}:${i}" aria-label="Quitar foto">×</button></div>`)
                .join("")}
            <label class="add-photo">${svg("camera", 26)}<span>Tomar foto</span><input type="file" accept="image/*" capture="environment" multiple data-photos="${key}" hidden></label></div>
            ${draft.gps ? `<small class="${draft.gps.out ? "warn" : "ok"}">Ubicación tomada${draft.gps.distance !== undefined ? ": a " + Math.round(draft.gps.distance) + " m de la obra" : ""}</small>` : ""}</div>`;
    }

    screens.queue = () => `${header("Por enviar", "", "home")}
        <main class="page">
            <p class="muted">${state.online ? "Con señal: se envía solo." : "Sin señal: se envía solo cuando vuelva la conexión."}</p>
            ${state.queue
                .slice()
                .reverse()
                .map(
                    (item) => `<div class="card queue ${item.status}"><div class="row between"><b>${esc(item.label)}</b>
                    <small>${{ pending: "en cola", done: "enviado", rejected: "rechazado" }[item.status]}</small></div>
                    <small class="muted">${esc(item.created.replace("T", " ").slice(0, 16))}${item.result && item.result.name ? " · " + esc(item.result.name) : ""}</small>
                    ${item.error ? `<p class="error">${esc(item.error)}</p>` : ""}
                    ${item.status !== "pending" ? `<button class="link" data-discard="${item.uuid}">${item.status === "done" ? "Quitar de la lista" : "Descartar"}</button>` : ""}
                    ${item.status === "rejected" ? `<button class="link" data-retry="${item.uuid}">Reintentar</button>` : ""}</div>`
                )
                .join("") || '<p class="muted">No hay registros por enviar.</p>'}
            <button class="primary" data-action="flush">Reintentar el envío ahora</button>
        </main>${nav("queue")}`;

    screens.daily = () => {
        const d = (state.draft.daily = state.draft.daily || {
            date: today(), weather: "", staff: [{ name: "Personal propio", source: "own", count: 0 }],
            restrictions: [], occurrences: "", photos: [], signature: "",
        });
        const todayWork = state.queue
            .filter((q) => q.kind === "progress" && q.payload.date === d.date)
            .map((q) => q.label);
        return `${header("Parte diario", projectName() + " · " + d.date, "home")}
            <main class="page">
                <div class="card form"><b>Clima</b><div class="chips">${(state.data.weather || [])
                    .map(([code, label]) => `<button class="chip ${d.weather === code ? "on" : ""}" data-set="daily.weather=${code}">${esc(label)}</button>`)
                    .join("")}</div></div>
                <div class="card form"><div class="row between"><b>Personal en obra</b><small>total ${d.staff.reduce((s, r) => s + Number(r.count || 0), 0)}</small></div>
                    ${d.staff
                        .map(
                            (r, i) => `<div class="row staff"><input value="${esc(r.name)}" data-bind="daily.staff.${i}.name" aria-label="Cuadrilla o contrata">
                            <select data-bind="daily.staff.${i}.source"><option value="own" ${r.source === "own" ? "selected" : ""}>Propio</option><option value="contract" ${r.source === "contract" ? "selected" : ""}>Contrata</option></select>
                            <input type="number" min="0" value="${r.count}" data-bind="daily.staff.${i}.count" aria-label="Personas"></div>`
                        )
                        .join("")}
                    <button class="link" data-action="add-staff">+ Agregar cuadrilla o contrata</button></div>
                <div class="card"><b>Trabajos del día</b><small class="muted">Se llenan con los avances registrados hoy.</small>
                    ${todayWork.map((w) => `<div class="small">${esc(w)}</div>`).join("") || '<small class="muted">Sin avances registrados en este equipo.</small>'}</div>
                <div class="card form"><b>Restricciones del día</b>${[
                    ["material", "Falta de material"],
                    ["front", "Frente no liberado por el cliente"],
                    ["weather", "Lluvia o paralización"],
                ]
                    .map(([code, label]) => `<label class="check"><input type="checkbox" data-toggle="daily.restrictions=${code}" ${d.restrictions.includes(code) ? "checked" : ""}> ${label}</label>`)
                    .join("")}</div>
                <div class="card form"><label>Ocurrencias y visitas<textarea rows="3" data-bind="daily.occurrences">${esc(d.occurrences)}</textarea></label></div>
                ${photosCard("daily", d, false)}
                <div class="card form"><b>Firma del maestro de obra</b><canvas id="signature" class="signature" width="340" height="140"></canvas>
                <button class="link" data-action="clear-signature">Borrar la firma</button></div>
                ${state.params.error ? `<p class="error">${esc(state.params.error)}</p>` : ""}
                <button class="primary" data-action="save-daily">Enviar al residente</button>
            </main>`;
    };

    screens.crew = () => {
        const crew = state.data.crew || [];
        const lines = (state.data.partidas || []).filter((p) => p.kind === "labor");
        const d = (state.draft.crew = state.draft.crew || {
            date: today(),
            attendance: Object.fromEntries(crew.map((w) => [w.id, { present: true, time: "07:30" }])),
            hours: {},
        });
        const total = (id) =>
            Object.entries(d.hours)
                .filter(([key]) => key.startsWith(id + ":"))
                .reduce((sum, [, h]) => sum + Number(h || 0), 0);
        return `${header("Cuadrilla y tareo", projectName() + " · " + d.date, "home")}
            <main class="page wide">
                <div class="card"><div class="row between"><b>Asistencia</b><small>Presentes ${crew.filter((w) => d.attendance[w.id] && d.attendance[w.id].present).length} de ${crew.length}</small></div>
                ${crew
                    .map(
                        (w) => `<div class="row crew"><span><b>${esc(w.name)}</b><small>${esc(w.category)}</small></span>
                        <label class="check"><input type="checkbox" data-bind="crew.attendance.${w.id}.present" ${d.attendance[w.id] && d.attendance[w.id].present ? "checked" : ""}> Presente</label>
                        <input type="time" value="${esc((d.attendance[w.id] || {}).time || "07:30")}" data-bind="crew.attendance.${w.id}.time" aria-label="Hora de entrada"></div>`
                    )
                    .join("") || '<small class="muted">La cuadrilla no tiene personas con turno en la obra.</small>'}</div>
                <div class="card scroll"><b>Horas por partida</b><small class="muted">jornada de 8 horas; las horas extra van aparte</small>
                <table class="tareo"><thead><tr><th>Persona</th>${lines.map((l) => `<th>${esc(l.item)} ${esc(l.name.slice(0, 14))}</th>`).join("")}<th>Total</th></tr></thead>
                <tbody>${crew
                    .map(
                        (w) => `<tr><td>${esc(w.name)}</td>${lines
                            .map((l) => `<td><input type="number" min="0" max="12" step="0.5" value="${d.hours[w.id + ":" + l.id] || ""}" data-bind="crew.hours.${w.id}:${l.id}" aria-label="Horas"></td>`)
                            .join("")}<td class="${total(w.id) > 8 ? "warn" : ""}">${num(total(w.id), 1)}</td></tr>`
                    )
                    .join("")}</tbody></table></div>
                ${state.params.error ? `<p class="error">${esc(state.params.error)}</p>` : ""}
                <button class="primary" data-action="save-crew">Enviar tareo</button>
            </main>`;
    };

    screens.catalog = () => {
        if (!state.data || !state.data.catalog) {
            return `${header("Requerimientos", projectName(), "home")}<main class="page"><p class="muted">Los requerimientos los piden el capataz y la oficina técnica.</p></main>${nav("catalog")}`;
        }
        const tab = state.params.tab || "partida";
        const cat = state.data.catalog;
        const qty = (key) => (state.cart.find((c) => c.key === key) || {}).qty || 0;
        const tabs = [["partida", "Materiales de partida"], ["epp", "EPP"], ["office", "Útiles y aseo"]];
        let items;
        if (tab === "partida") {
            items = cat.partida.map((p) => ({ key: `partida:${p.product_id}:${p.task_id}`, catalog: "partida", product_id: p.product_id, task_id: p.task_id, name: p.name, sub: `${p.task} · saldo ${num(p.balance)} ${p.uom}` }));
        } else {
            items = cat[tab].products.map((p) => ({ key: `${tab}:${p.product_id}`, catalog: tab, product_id: p.product_id, name: p.name, sub: p.uom }));
        }
        const kits = tab === "partida" ? [] : cat[tab].kits;
        return `${header("Requerimientos", projectName(), "home")}
            <main class="page">
                <div class="tabs">${tabs.map(([key, label]) => `<button class="${tab === key ? "on" : ""}" data-tab="${key}">${label}</button>`).join("")}</div>
                ${kits.map((k) => `<button class="chip" data-kit="${tab}:${k.id}">+ ${esc(k.name)}</button>`).join("")}
                ${items
                    .map(
                        (it) => `<div class="card item"><span><b>${esc(it.name)}</b><small>${esc(it.sub)}</small></span>
                        <div class="stepper small"><button data-cart="${esc(it.key)}" data-delta="-1" aria-label="Restar">−</button><b>${num(qty(it.key), 0)}</b>
                        <button data-cart="${esc(it.key)}" data-delta="1" data-item='${esc(JSON.stringify(it))}' aria-label="Sumar">+</button></div></div>`
                    )
                    .join("") || '<p class="muted">Sin productos en este catálogo.</p>'}
                <div class="card form"><label>Pedir algo que no está en la lista<input data-bind="cartText" value="${esc(state.draft.cartText || "")}" placeholder="Descripción y cantidad"></label>
                <button class="link" data-action="add-text">Agregar</button></div>
                <button class="primary" data-go="cart">${state.cart.length} ítems en el pedido · Revisar ›</button>
            </main>${nav("catalog")}`;
    };

    screens.cart = () => {
        const d = (state.draft.request = state.draft.request || { date_required: today(), priority: "normal", note: "" });
        return `${header("Revisar el requerimiento", "", "catalog")}
            <main class="page">
                <div class="card form"><label>Fecha en que se necesita<input type="date" data-bind="request.date_required" value="${esc(d.date_required)}"></label>
                <div class="toggle"><button class="${d.priority === "normal" ? "on" : ""}" data-set="request.priority=normal">Normal</button>
                <button class="${d.priority === "urgent" ? "on" : ""}" data-set="request.priority=urgent">Urgente</button></div></div>
                ${["partida", "epp", "office"]
                    .map((kind) => {
                        const rows = state.cart.filter((c) => c.catalog === kind);
                        if (!rows.length) return "";
                        return `<div class="card"><b>${{ partida: "De la partida", epp: "EPP", office: "Útiles y aseo" }[kind]}</b>${rows
                            .map((c) => `<div class="row between"><span>${esc(c.name)}<small>${esc(c.sub || "")}</small></span><b>${num(c.qty, 0)}</b></div>`)
                            .join("")}</div>`;
                    })
                    .join("")}
                ${state.cart.filter((c) => c.catalog === "text").map((c) => `<div class="card"><small>Fuera de catálogo</small> ${esc(c.name)}</div>`).join("")}
                <div class="card steps"><b>Qué pasa al enviarlo</b><ol><li>Lo aprueba el coordinador de la obra</li><li>Logística despacha del almacén o compra</li><li>Usted confirma la recepción en obra</li></ol></div>
                <div class="card form"><label>Nota para logística<textarea rows="2" data-bind="request.note">${esc(d.note)}</textarea></label></div>
                <button class="primary" data-action="save-request" ${state.cart.length ? "" : "disabled"}>Enviar a aprobación</button>
            </main>`;
    };

    screens.reception = () => {
        const deliveries = state.data.deliveries || [];
        const picking = deliveries.find((p) => p.id === Number(state.params.id));
        if (!picking) {
            return `${header("Recepción en obra", deliveries.length + " entregas por recibir", "home")}
                <main class="page">${deliveries
                    .map((p) => `<button class="card row-link" data-go="reception" data-id="${p.id}"><span><b>${esc(p.name)}</b><small>${esc(p.origin)} · ${esc((p.date || "").slice(0, 10))}</small></span></button>`)
                    .join("") || '<p class="muted">No hay entregas por recibir.</p>'}</main>`;
        }
        const d = (state.draft["reception" + picking.id] = state.draft["reception" + picking.id] || {
            received: Object.fromEntries(picking.lines.map((l) => [l.move_id, l.sent])), photos: [], note: "",
        });
        const missing = picking.lines.filter((l) => Number(d.received[l.move_id]) < l.sent);
        return `${header("Recepción en obra", picking.name, "reception")}
            <main class="page">
                <div class="card"><table class="lines"><thead><tr><th>Producto</th><th>Enviado</th><th>Recibido</th></tr></thead><tbody>${picking.lines
                    .map((l) => `<tr><td>${esc(l.name)}</td><td>${num(l.sent)} ${esc(l.uom)}</td><td><input type="number" min="0" step="0.01" value="${d.received[l.move_id]}" data-bind="reception${picking.id}.received.${l.move_id}" aria-label="Recibido"></td></tr>`)
                    .join("")}</tbody></table></div>
                ${photosCard("reception" + picking.id, d, true)}
                <div class="card form"><b>Faltantes o daños</b><small class="${missing.length ? "warn" : "muted"}">${missing.length ? missing.length + " productos con faltante: quedan pendientes." : "Sin faltantes."}</small>
                <textarea rows="2" data-bind="reception${picking.id}.note">${esc(d.note)}</textarea></div>
                <button class="primary" data-action="save-reception" data-id="${picking.id}">Confirmar recepción</button>
            </main>`;
    };

    screens.return = () => {
        const items = state.data.returnables || [];
        const d = (state.draft.ret = state.draft.ret || { lines: {}, transport: "own", photos: [] });
        return `${header("Devolución al almacén", "Lo que vuelve sale del costo de la partida", "home")}
            <main class="page">
                ${items
                    .map((it) => {
                        const row = d.lines[it.product_id] || { qty: 0, state: "good" };
                        return `<div class="card form"><div class="row between"><b>${esc(it.name)}</b><small>en obra ${num(it.qty)} ${esc(it.uom)}</small></div>
                        <label>Cantidad a devolver<input type="number" min="0" max="${it.qty}" step="0.01" value="${row.qty}" data-bind="ret.lines.${it.product_id}.qty"></label>
                        <div class="toggle"><button class="${row.state === "good" ? "on" : ""}" data-set="ret.lines.${it.product_id}.state=good">En buen estado</button>
                        <button class="${row.state === "damaged" ? "on" : ""}" data-set="ret.lines.${it.product_id}.state=damaged">Dañado</button></div></div>`;
                    })
                    .join("") || '<p class="muted">No hay material en la obra.</p>'}
                <div class="card form"><b>Traslado</b><label class="check"><input type="radio" name="transport" data-set-radio="ret.transport=own" ${d.transport === "own" ? "checked" : ""}> Unidad propia (guía de remisión)</label>
                <label class="check"><input type="radio" name="transport" data-set-radio="ret.transport=supplier" ${d.transport === "supplier" ? "checked" : ""}> Flete de proveedor</label></div>
                ${photosCard("ret", d, true)}
                <button class="primary" data-action="save-return">Generar devolución</button>
            </main>`;
    };

    screens.valuations = () => {
        const data = state.data.valuations || [];
        return `${header("Valorizaciones y pagos", projectName(), "home")}
            <main class="page">${data
                .map(
                    (v) => `<button class="card row-link" data-go="valuation" data-id="${v.id}"><span><b>${esc(v.name)}</b>
                    <small>${esc(v.period_start)} al ${esc(v.period_end)} · ${esc(v.state_label)}${v.invoice ? " · factura " + esc(v.invoice) : ""}</small></span><b>${money(v.amount)}</b></button>`
                )
                .join("") || '<p class="muted">Aún no tiene valorizaciones.</p>'}
            <button class="secondary" data-go="partidas">Registrar avance</button></main>${nav("home")}`;
    };

    screens.valuation = () => {
        const v = state.params.detail;
        if (!v) {
            return `${header("Valorización", "", "valuations")}<main class="page"><p class="muted">${state.params.error ? esc(state.params.error) : "Cargando…"}</p></main>`;
        }
        const row = (label, value, cls) => `<div class="row between ${cls || ""}"><span>${esc(label)}</span><b>${value}</b></div>`;
        return `${header(v.name, v.period_start + " al " + v.period_end, "valuations")}
            <main class="page">
                <div class="card">${v.lines.map((l) => row(l.name + (l.rework ? " · re-trabajo" : ""), num(l.amount), l.rework && !l.paid_rework ? "muted" : "")).join("")}</div>
                <div class="card">${v.deductions.map((dd) => row("Deductivo: " + dd.name, num(dd.amount))).join("")}
                ${row("Subtotal", num(v.subtotal))}${row("IGV", num(v.tax))}${row("Total de la factura", num(v.total))}
                ${row("Fondo de garantía (retenido)", "−" + num(v.guarantee))}${v.detraction ? row("Detracción", "−" + num(v.detraction)) : ""}
                ${row("Neto a su cuenta", money(v.net), "big")}</div>
                <p class="hint">${v.invoice ? "Factura " + esc(v.invoice) + ". " + esc(v.payment_state) : "Aún sin factura."}</p>
            </main>`;
    };

    // ------------------------------------------------------------------
    // Pintado y eventos
    // ------------------------------------------------------------------
    function render() {
        const screen = screens[state.route] || screens.home;
        $app().innerHTML = screen();
        if (state.route === "daily") {
            setupSignature();
        }
    }

    function setPath(path, value) {
        const parts = path.split(".");
        let target = parts[0] === "cartText" ? state : state.draft;
        if (parts[0] === "cartText") {
            state.draft.cartText = value;
            return;
        }
        for (let i = 0; i < parts.length - 1; i++) {
            target[parts[i]] = target[parts[i]] || {};
            target = target[parts[i]];
        }
        target[parts[parts.length - 1]] = value;
    }

    document.addEventListener("input", (event) => {
        const el = event.target;
        if (el.dataset.input === "q") {
            state.params.q = el.value;
            const pos = el.selectionStart;
            render();
            const again = document.querySelector('[data-input="q"]');
            if (again) {
                again.focus();
                again.setSelectionRange(pos, pos);
            }
        } else if (el.dataset.bind) {
            setPath(el.dataset.bind, el.type === "checkbox" ? el.checked : el.value);
        }
    });

    document.addEventListener("change", async (event) => {
        const el = event.target;
        if (el.dataset.change === "project") {
            state.projectId = Number(el.value);
            state.data = null;
            saveSession();
            await loadCache();
            render();
            await refresh();
            render();
        } else if (el.dataset.bind && el.dataset.bind.startsWith("crew.hours")) {
            // El total de horas por persona se recalcula al salir de la celda.
            render();
        } else if (el.dataset.bind && el.type === "checkbox") {
            setPath(el.dataset.bind, el.checked);
            if (el.dataset.bind === "progress.rework" || el.dataset.bind.startsWith("crew.attendance")) {
                render();
            }
        } else if (el.dataset.toggle) {
            const [path, value] = el.dataset.toggle.split("=");
            const list = path.split(".").reduce((o, k) => o[k], state.draft);
            const index = list.indexOf(value);
            if (index >= 0) list.splice(index, 1);
            else list.push(value);
        } else if (el.dataset.setRadio) {
            const [path, value] = el.dataset.setRadio.split("=");
            setPath(path, value);
        } else if (el.dataset.photos) {
            const key = el.dataset.photos;
            const draft = state.draft[key];
            for (const file of el.files) {
                try {
                    draft.photos.push(await compress(file));
                } catch {
                    // La foto que no se puede leer se omite.
                }
            }
            locate().then((pos) => {
                if (pos && state.data) {
                    const site = state.data.project;
                    const dist = site.latitude || site.longitude ? distance(pos, site) : undefined;
                    draft.gps = Object.assign(pos, { distance: dist, out: dist !== undefined && site.radius_m && dist > site.radius_m });
                    render();
                }
            });
            render();
        } else if (el.dataset.bind && ["reception", "ret", "crew"].some((k) => el.dataset.bind.startsWith(k))) {
            render();
        }
    });

    document.addEventListener("submit", async (event) => {
        event.preventDefault();
        const form = event.target;
        const values = Object.fromEntries(new FormData(form).entries());
        try {
            if (form.dataset.form === "login") {
                state.session = await call("/login", { login: values.login, password: values.password, device: navigator.userAgent });
            } else if (form.dataset.form === "qr-code") {
                const site = await call("/site/" + encodeURIComponent(values.code));
                return go("qr", { site, code: values.code });
            } else if (form.dataset.form === "pin") {
                state.session = await call("/pin", { code: state.params.code, member_id: Number(values.member_id), pin: values.pin, device: navigator.userAgent });
            }
            saveSession();
            await refresh();
            go("home");
        } catch (error) {
            state.params.error = error.message;
            render();
        }
    });

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
            return go(data.go, data.id ? { id: data.id } : {});
        }
        if (data.filter) {
            state.params.filter = data.filter;
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
            d[key] = Math.max(0, Number(d[key] || 0) + Number(data.step) * (key === "pct" ? 5 : 0.5));
            return render();
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
                else state.cart.push({ key, catalog: tab, product_id: line.product_id, name: line.name, qty: line.qty });
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
        flush: () => flush(),
        "add-staff": () => {
            state.draft.daily.staff.push({ name: "", source: "contract", count: 0 });
            render();
        },
        "add-text": () => {
            const text = (state.draft.cartText || "").trim();
            if (text) {
                state.cart.push({ key: "text:" + uuid(), catalog: "text", name: text, qty: 1 });
                state.draft.cartText = "";
            }
            render();
        },
        "clear-signature": () => {
            state.draft.daily.signature = "";
            render();
        },
        "save-progress": async () => {
            const d = state.draft.progress;
            const line = state.data.partidas.find((p) => p.id === Number(state.params.id));
            if (!d.photos.length) {
                state.params.error = "Tome al menos una foto del avance.";
                return render();
            }
            if (d.rework && !d.reason) {
                state.params.error = "Elija el motivo del re-trabajo.";
                return render();
            }
            const pos = d.gps || (await locate()) || {};
            const payload = {
                uuid: uuid(), project_id: state.projectId, plan_line_id: line.id, date: d.date,
                mode: d.mode, qty: Number(d.qty || 0), pct: Number(d.pct || 0),
                is_rework: !!d.rework, rework_reason: d.reason || false, note: d.note,
                latitude: pos.latitude || 0, longitude: pos.longitude || 0, photos: d.photos,
            };
            const amount = d.mode === "pct" ? d.pct + " %" : num(d.qty) + " " + line.uom;
            await enqueue("progress", "/progress", payload, `Avance ${line.item} ${line.name}: ${amount}`);
            state.draft.progress = null;
            go("queue");
        },
        "save-daily": async () => {
            const d = state.draft.daily;
            const canvas = document.getElementById("signature");
            const payload = {
                uuid: uuid(), project_id: state.projectId, date: d.date, weather: d.weather,
                staff: d.staff.filter((r) => r.name), restrictions: d.restrictions,
                occurrences: d.occurrences, photos: d.photos,
                signature: d.signature || (canvas && canvas.dataset.signed ? canvas.toDataURL("image/png") : ""),
            };
            await enqueue("daily_report", "/daily-report", payload, `Parte diario del ${d.date}`);
            state.draft.daily = null;
            go("queue");
        },
        "save-crew": async () => {
            const d = state.draft.crew;
            const payload = {
                uuid: uuid(), project_id: state.projectId, date: d.date,
                attendance: Object.entries(d.attendance).map(([id, a]) => ({ employee_id: Number(id), present: !!a.present, time: a.time })),
                hours: Object.entries(d.hours)
                    .filter(([, h]) => Number(h) > 0)
                    .map(([key, h]) => ({ employee_id: Number(key.split(":")[0]), plan_line_id: Number(key.split(":")[1]), hours: Number(h) })),
            };
            const present = payload.attendance.filter((a) => a.present).length;
            await enqueue("crew_day", "/crew-day", payload, `Asistencia y tareo del ${d.date}: ${present} personas`);
            state.draft.crew = null;
            go("queue");
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
            await enqueue("material_request", "/material-request", payload, `Requerimiento de ${state.cart.length} ítems`);
            state.cart = [];
            state.draft.request = null;
            go("queue");
        },
        "save-reception": async (el) => {
            const id = Number(el.dataset.id);
            const d = state.draft["reception" + id];
            if (!d.photos.length) {
                return alertInline("Tome la foto de la guía firmada.");
            }
            const picking = state.data.deliveries.find((p) => p.id === id);
            const payload = {
                uuid: uuid(), project_id: state.projectId, picking_id: id, note: d.note, photos: d.photos,
                lines: Object.entries(d.received).map(([move, qty]) => ({ move_id: Number(move), qty: Number(qty) })),
            };
            await enqueue("reception", "/reception", payload, `Recepción de ${picking.name}`);
            state.data.deliveries = state.data.deliveries.filter((p) => p.id !== id);
            state.draft["reception" + id] = null;
            go("queue");
        },
        "save-return": async () => {
            const d = state.draft.ret;
            if (!d.photos.length) {
                return alertInline("Tome la foto de la carga.");
            }
            const lines = Object.entries(d.lines)
                .filter(([, row]) => Number(row.qty) > 0)
                .map(([product, row]) => ({ product_id: Number(product), qty: Number(row.qty), state: row.state || "good" }));
            if (!lines.length) {
                return alertInline("Indique lo que devuelve.");
            }
            await enqueue("return", "/return", { uuid: uuid(), project_id: state.projectId, transport: d.transport, photos: d.photos, lines }, `Devolución de ${lines.length} productos`);
            state.draft.ret = null;
            go("queue");
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
        const end = () => {
            if (drawing && canvas.dataset.signed) {
                state.draft.daily.signature = canvas.toDataURL("image/png");
            }
            drawing = false;
        };
        canvas.addEventListener("pointerdown", start);
        canvas.addEventListener("pointermove", move);
        window.addEventListener("pointerup", end, { once: false });
        if (state.draft.daily && state.draft.daily.signature) {
            const img = new Image();
            img.onload = () => ctx.drawImage(img, 0, 0);
            img.src = state.draft.daily.signature;
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
        });
    }

    async function start() {
        loadSession();
        state.queue = await queueAll().catch(() => []);
        const hash = new URLSearchParams(location.hash.slice(1));
        if (hash.get("qr") && !state.session) {
            history.replaceState(null, "", location.pathname);
            try {
                const site = await call("/site/" + encodeURIComponent(hash.get("qr")));
                return go("qr", { site, code: hash.get("qr") });
            } catch (error) {
                return go("qr", { code: hash.get("qr"), error: error.message });
            }
        }
        if (!state.session) {
            return go("login");
        }
        await loadCache();
        go("home");
        await refresh();
        render();
        flush();
    }
    start();
})();

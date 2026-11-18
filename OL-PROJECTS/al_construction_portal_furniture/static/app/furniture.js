/* Portal de obra · funciones de campo de mobiliario (paquete 1.22, etapa 2,
 * M122-05 a M122-09).
 *
 * Se suma a la aplicación del portal por «window.ObraPortal» (carga después
 * de app.js): la ficha del departamento, la recepción de módulos por
 * departamento, el pedido de reposición, la marca de ambiente medido, el
 * avance por sub etapa y el avance de la contrata con su driver. Cada una es
 * una función del perfil de la obra («feature») y trabaja sin señal con lo
 * que trae la sincronización en «data.furniture». */
(function () {
    "use strict";

    const P = window.ObraPortal;
    if (!P) {
        return;
    }
    const { state, screens, actions, h } = P;
    const { esc, qtyText, today, range, join, pill, header, nav, role, feature, go, render, enqueue, uuid, cachePut,
            photosCard, alertInline, projectParts, taskName, lineDone, byName, locate } = h;

    const EMPTY = { stages: [], apartments: {}, reasons: [], settled: {}, week: false };
    const fur = () => (state.data && state.data.furniture) || EMPTY;
    const fieldRole = () => role("foreman") || role("office");
    const contractor = () => role("contractor") && feature("contractor_units");
    // El departamento abierto y a dónde vuelve «Avance por sub etapa»: la
    // navegación de la aplicación solo lleva un identificador.
    const mem = { apt: null, back: "partidas" };
    const aptId = () => Number(state.params.id || mem.apt || 0);
    const apartment = (id) => fur().apartments[id];
    const plural = (n, one, many) => `${n} ${n === 1 ? one : many}`;
    const saveCache = () => cachePut("sync:" + state.projectId, state.data).catch(() => {});
    const errorBox = () => (state.params.error ? `<p class="error">${esc(state.params.error)}</p>` : "");

    P.MAX_PHOTOS.furstage = 3;
    P.MAX_PHOTOS.furmeasure = 8;
    P.MAX_PHOTOS.furrepl = 5;
    Object.assign(P.SAVED_TEXT, {
        stage_progress: ["Avance por sub etapa", "queda por validar por el residente"],
        replacement: ["Reposición", "queda en borrador en Odoo y sigue su flujo de aprobación y pedido a planta"],
        measure: ["Medición", "los ambientes quedan en «Medido»"],
    });
    Object.assign(P.routeFeature, { furstage: "stage_progress", furmeasure: "measure", furrepl: "replacement" });
    // Lo enviado cambia la ficha del departamento: se vuelve a sincronizar.
    P.afterFlush.push((item) => ["stage_progress", "replacement", "measure"].includes(item.kind));

    // Líneas del plan de un departamento (por su grupo de «Avance»).
    function inGroup(p, id) {
        const groups = (state.data && state.data.groups) || {};
        for (let g = p.group_id; g && groups[g]; g = groups[g].parent) {
            if (Number(g) === Number(id)) return true;
        }
        return false;
    }
    const aptLines = (id) => ((state.data && state.data.partidas) || []).filter((p) => inGroup(p, id));

    // ------------------------------------------------------------------
    // Matriz ambiente × sub etapa de instalación (M122-08)
    // ------------------------------------------------------------------
    function matrix(id) {
        const stages = fur().stages;
        const codes = stages.map((s) => s.code);
        const a = apartment(id) || { spaces: [] };
        const rows = new Map();
        const lines = aptLines(id).filter((p) => p.space_id && codes.includes(p.stage));
        lines.forEach((p) => {
            if (!rows.has(p.space_id)) {
                const space = a.spaces.find((s) => s.id === p.space_id);
                rows.set(p.space_id, { id: p.space_id, name: (space && space.name) || p.space || taskName(p), cells: {} });
            }
            const row = rows.get(p.space_id);
            const i = codes.indexOf(p.stage);
            (row.cells[i] = row.cells[i] || []).push(p);
        });
        const list = [...rows.values()].sort((x, y) => byName(x.name, y.name));
        const used = stages.map((s, i) => i).filter((i) => list.some((r) => r.cells[i]));
        return { stages, used, rows: list, lines };
    }
    const cellPct = (lines) =>
        lines && lines.length ? Math.round((100 * lines.reduce((sum, p) => sum + (p.planned ? Math.min(1, lineDone(p) / p.planned) : 1), 0)) / lines.length) : null;
    const cellKey = (spaceId, i) => `c${spaceId}_${i}`;
    const targetOf = (d, key) => Math.max(0, Math.min(100, Number(d.cells[key] || 0)));
    // Líneas a las que el envío les registra algo: las que no llegan al % pedido.
    const cellTodo = (lines, target) => (lines || []).filter((p) => (p.planned * target) / 100 - lineDone(p) > 1e-6);
    function stageDraft(id) {
        if (!state.draft.furstage || state.draft.furstage.apt !== id) {
            state.draft.furstage = { apt: id, date: today(), cells: {}, selected: "", photos: [], note: "" };
        }
        return state.draft.furstage;
    }
    function stageTodo(m, d) {
        const todo = [];
        m.rows.forEach((r) => m.used.forEach((i) => {
            const target = targetOf(d, cellKey(r.id, i));
            if (target > 0) cellTodo(r.cells[i], target).forEach((p) => todo.push([p, target]));
        }));
        return todo;
    }
    const stageShort = (s) => s.number || s.label;

    screens.furstage = () => {
        const id = aptId();
        const a = apartment(id);
        if (!a) return screens.partidas();
        mem.apt = id;
        const m = matrix(id);
        const d = stageDraft(id);
        const head = header("Avance por sub etapa", join(a.name, a.parent), mem.back);
        if (!m.rows.length) {
            return `${head}<main class="page"><p class="muted">${role("contractor") && !fieldRole() ? "No tiene actividades de instalación en este departamento." : "Este departamento no tiene líneas de instalación en el plan."}</p></main>`;
        }
        const todo = stageTodo(m, d);
        const cell = (r, i) => {
            const lines = r.cells[i];
            if (!lines) return '<td class="fur-none">—</td>';
            const key = cellKey(r.id, i);
            const pct = cellPct(lines);
            const target = targetOf(d, key);
            const cls = target ? "set" : pct >= 100 ? "ok" : pct > 0 ? "part" : "";
            return `<td><button class="fur-cell ${cls} ${d.selected === key ? "sel" : ""}" data-fur-cell="${key}" aria-pressed="${!!target}" aria-label="${esc(r.name)}, ${esc(m.stages[i].label)}: ${pct} %${target ? `, se reporta ${target} %` : ""}">${target ? target : pct}</button></td>`;
        };
        let editor = "";
        if (d.selected && d.cells[d.selected] !== undefined) {
            const [space, i] = d.selected.slice(1).split("_").map(Number);
            const r = m.rows.find((row) => row.id === space);
            if (r && m.stages[i]) {
                editor = `<div class="card form"><label>% acumulado de ${esc(r.name)} · ${esc(m.stages[i].label)}
                    <input type="number" min="0" max="100" step="5" inputmode="numeric" data-bind="furstage.cells.${d.selected}" data-rerender="1" value="${targetOf(d, d.selected)}"></label>
                    <small class="muted">100 es terminado. Toque otra vez la celda para quitarla.</small></div>`;
            }
        }
        return `${head}
            <main class="page">
                <div class="card"><table class="fur-matrix"><thead><tr><th>${esc(h.levelName("space", "Ambiente"))}</th>${m.used
                    .map((i) => `<th title="${esc(m.stages[i].label)}">${esc(stageShort(m.stages[i]))}</th>`)
                    .join("")}</tr></thead><tbody>${m.rows
                    .map((r) => `<tr><th class="clamp2">${esc(r.name)}</th>${m.used.map((i) => cell(r, i)).join("")}</tr>`)
                    .join("")}</tbody></table>
                    <small class="muted">${esc(m.used.map((i) => m.stages[i].label).join(" · "))}. Avance de hoy en %; toque una celda para darla por terminada.</small></div>
                ${m.used.map((i) => `<button class="secondary" data-fur-col="${i}">Todo el departamento terminado en ${esc(stageShort(m.stages[i]))}</button>`).join("")}
                ${editor}
                ${photosCard("furstage", d, true, "Foto")}
                <div class="card form"><label>Fecha de ejecución<input type="date" data-bind="furstage.date" value="${esc(d.date)}" max="${today()}"></label>
                    <label>Observación<textarea rows="2" data-bind="furstage.note" placeholder="Opcional">${esc(d.note)}</textarea></label></div>
                ${errorBox()}
                <button class="primary" data-action="save-fur-stage" ${todo.length ? "" : "disabled"}>Enviar · ${plural(todo.length, "línea", "líneas")}</button>
                <p class="hint">Se registra el saldo de cada línea del plan de ese ambiente y sub etapa; el residente lo valida en su bandeja. Una línea ya terminada no registra nada.</p>
            </main>`;
    };

    actions["save-fur-stage"] = async () => {
        const d = state.draft.furstage;
        const a = apartment(d.apt);
        const m = matrix(d.apt);
        const todo = stageTodo(m, d);
        if (!todo.length) return alertInline("Marque al menos un ambiente y una sub etapa con saldo.");
        if (!d.photos.length) return alertInline("Tome la foto del avance.");
        const cells = [];
        m.rows.forEach((r) => m.used.forEach((i) => {
            const target = targetOf(d, cellKey(r.id, i));
            if (target > 0) cells.push({ space_id: r.id, stage: m.stages[i].code, pct: target });
        }));
        const pos = (d.gps && !d.gps.denied && d.gps) || (await locate()) || {};
        const payload = {
            uuid: uuid(), project_id: state.projectId, apartment_id: d.apt, date: d.date, cells, note: d.note,
            latitude: pos.latitude || 0, longitude: pos.longitude || 0, photos: d.photos,
        };
        await enqueue("stage_progress", "/furniture/stage-progress", payload, `Avance por sub etapa de ${a.name}: ${plural(todo.length, "línea", "líneas")}`);
        // Los contadores de «Avance» y «Esta semana» se actualizan al guardar.
        const week = fur().week;
        todo.forEach(([p, target]) => {
            const added = Math.max(0, (p.planned * target) / 100 - lineDone(p));
            p.pending += added;
            p.balance -= added;
            if (week && p.kind === "contract") {
                let row = week.rows.find((w) => w.activity === p.activity && w.uom === p.uom);
                if (!row) {
                    row = { activity: p.activity, uom: p.uom, reported: 0, validated: 0 };
                    week.rows.push(row);
                }
                row.reported += added;
            }
        });
        saveCache();
        state.draft.furstage = null;
        go("queue", { saved: "stage_progress" });
    };

    // ------------------------------------------------------------------
    // Ficha del departamento (pantalla común)
    // ------------------------------------------------------------------
    const STAGE_PILL = { pending: "bad", measured: "", delivered: "ok", stage: "warn" };
    const aptDeliveries = (id) => ((state.data && state.data.deliveries) || []).filter((p) => (p.departments || []).some((dep) => dep.id === id));

    screens.furapt = () => {
        const id = aptId();
        const a = apartment(id);
        if (!a) return screens.partidas();
        mem.apt = id;
        const field = fieldRole();
        const deliveries = field && feature("module_reception") ? aptDeliveries(id) : [];
        const toMeasure = a.spaces.filter((s) => s.can_measure).length;
        const open = a.replacements || [];
        const hasStage = feature("progress") && feature("stage_progress") && matrix(id).rows.length;
        return `${header(a.name, join(projectParts().code, a.parent), "partidas")}
            <main class="page">
                <div class="card"><b>Etapa actual de cada ${esc(h.levelName("space", "ambiente").toLowerCase())}</b>
                    ${a.spaces.map((s) => `<div class="row between line"><span class="grow clamp2">${esc(s.name)}</span>${s.stage_label ? pill(s.stage_label, STAGE_PILL[s.kind] || "") : '<small class="muted">—</small>'}</div>`).join("") || '<small class="muted">Sin ambientes.</small>'}
                </div>
                ${hasStage ? `<button class="primary" data-fur-go="furstage" data-back="furapt" data-id="${id}">Avance por sub etapa</button>` : ""}
                ${field && feature("module_reception") ? `<button class="secondary" ${deliveries.length ? `data-go="reception" data-id="${deliveries[0].id}"` : "disabled"}>Recibir módulos · ${plural(deliveries.length, "despacho", "despachos")}</button>` : ""}
                ${field && feature("measure") ? `<button class="secondary" data-fur-go="furmeasure" data-id="${id}" ${toMeasure ? "" : "disabled"}>Marcar medido · ${plural(toMeasure, "pendiente", "pendientes")}</button>` : ""}
                ${field && feature("replacement") ? `<button class="secondary" data-fur-go="furrepl" data-id="${id}">Pedir reposición · ${plural(open.length, "abierta", "abiertas")}</button>` : ""}
                ${field && feature("replacement") ? open.map((r) => `<div class="card"><small class="eyebrow">Reposición abierta</small><b>${esc(join(r.name, r.module))}</b><small>${esc(join(r.state_label, r.reason, r.space))}</small></div>`).join("") : ""}
            </main>${nav("partidas")}`;
    };

    // Bajo la cabecera de un departamento abierto en «Avance».
    P.groupActions.push((n) => {
        if (!n.g || n.g.kind !== "apartment" || !apartment(n.id)) return "";
        const parts = [];
        if (contractor()) {
            parts.push(driverCard(n));
            if (feature("stage_progress")) parts.push(`<button class="secondary" data-fur-go="furstage" data-back="partidas" data-id="${n.id}">Avance por sub etapa</button>`);
        }
        if (fieldRole() || !contractor()) {
            parts.push(`<button class="secondary" data-fur-go="furapt" data-id="${n.id}">Ficha de ${esc(n.g.name)}</button>`);
        }
        return parts.join("");
    });

    // ------------------------------------------------------------------
    // M122-09 · Avance de la contrata: driver por departamento y «Esta semana»
    // ------------------------------------------------------------------
    function driverCard(n) {
        const settled = fur().settled || {};
        const rows = new Map();
        aptLines(n.id).filter((p) => p.kind === "contract").forEach((p) => {
            const key = p.activity + "|" + p.uom;
            if (!rows.has(key)) rows.set(key, { activity: p.activity, uom: p.uom, planned: 0, reported: 0, validated: 0, settled: 0 });
            const r = rows.get(key);
            r.planned += p.planned || 0;
            r.reported += lineDone(p);
            r.validated += p.validated || 0;
            r.settled += settled[p.id] || 0;
        });
        if (!rows.size) return "";
        const list = [...rows.values()];
        const q = (value, uom) => `${qtyText(value)} ${esc(uom || "")}`;
        return `<div class="card fur-driver"><small class="strong">${esc(list.map((r) => `${qtyText(r.planned)} ${r.uom || ""}`.trim()).join(" · "))}</small>
            <table class="fur-table"><thead><tr><th>Actividad</th><th>Reportado</th><th>Validado</th><th>Liquidado</th></tr></thead><tbody>${list
                .map((r) => `<tr><th>${esc(r.activity)}</th><td>${q(r.reported, r.uom)}</td><td>${q(r.validated, r.uom)}</td><td>${q(r.settled, r.uom)}</td></tr>`)
                .join("")}</tbody></table></div>`;
    }
    P.progressHead.push(() => {
        const week = fur().week;
        if (!contractor() || !week) return "";
        return `<div class="card"><small class="eyebrow">Esta semana · ${esc(range(week.start, week.end))}</small>
            ${week.rows.length
                ? `<table class="fur-table"><thead><tr><th>Actividad</th><th>Reportado</th><th>Validado</th></tr></thead><tbody>${week.rows
                      .map((r) => `<tr><th>${esc(r.activity)}</th><td>${qtyText(r.reported)} ${esc(r.uom)}</td><td>${qtyText(r.validated)} ${esc(r.uom)}</td></tr>`)
                      .join("")}</tbody></table>
                   <small class="muted">Lo validado es lo que pasa a la liquidación de la semana.</small>`
                : '<small class="muted">Aún no reporta avance esta semana.</small>'}</div>`;
    });

    // ------------------------------------------------------------------
    // M122-07 · Marcar medido
    // ------------------------------------------------------------------
    screens.furmeasure = () => {
        const id = aptId();
        const a = apartment(id);
        if (!a) return screens.partidas();
        mem.apt = id;
        if (!state.draft.furmeasure || state.draft.furmeasure.apt !== id) {
            state.draft.furmeasure = { apt: id, date: today(), picked: {}, photos: [], note: "" };
        }
        const d = state.draft.furmeasure;
        const spaces = a.spaces.filter((s) => s.can_measure);
        return `${header("Marcar medido", join(a.name, a.parent), "furapt")}
            <main class="page">
                <div class="card list">${spaces
                    .map((s) => `<label class="pick"><input type="checkbox" data-bind="furmeasure.picked.${s.id}" ${d.picked[s.id] ? "checked" : ""}><span class="grow"><b>${esc(s.name)}</b>${s.typology ? `<small> ${esc(s.typology)}</small>` : ""}</span></label>`)
                    .join("") || '<small class="muted">No hay ambientes pendientes de medir.</small>'}</div>
                ${photosCard("furmeasure", d, true, "Fotos o croquis de la medición")}
                <div class="card form"><label>Fecha de medición<input type="date" data-bind="furmeasure.date" value="${esc(d.date)}" max="${today()}"></label>
                    <label>Nota<textarea rows="2" data-bind="furmeasure.note" placeholder="Opcional">${esc(d.note)}</textarea></label></div>
                ${errorBox()}
                <button class="primary" data-action="save-fur-measure" ${spaces.length ? "" : "disabled"}>Guardar</button>
                <p class="hint">Desmarcar un ambiente se hace en Odoo.</p>
            </main>`;
    };
    actions["save-fur-measure"] = async () => {
        const d = state.draft.furmeasure;
        const a = apartment(d.apt);
        const ids = a.spaces.filter((s) => s.can_measure && d.picked[s.id]).map((s) => s.id);
        if (!ids.length) return alertInline("Elija al menos un ambiente.");
        if (!d.photos.length) return alertInline("Tome la foto o el croquis de la medición.");
        await enqueue("measure", "/furniture/measure", { uuid: uuid(), project_id: state.projectId, date: d.date, space_ids: ids, note: d.note, photos: d.photos },
            `Medición de ${a.name}: ${plural(ids.length, "ambiente", "ambientes")}`);
        a.spaces.forEach((s) => {
            if (ids.includes(s.id)) {
                s.can_measure = false;
                s.measured = true;
            }
        });
        saveCache();
        state.draft.furmeasure = null;
        go("queue", { saved: "measure" });
    };

    // ------------------------------------------------------------------
    // M122-06 · Pedir reposición
    // ------------------------------------------------------------------
    const moduleSub = (mod) => join(join(mod.space, mod.typology), mod.lot ? "lote " + mod.lot : "");
    screens.furrepl = () => {
        const id = aptId();
        const a = apartment(id);
        if (!a) return screens.partidas();
        mem.apt = id;
        if (!state.draft.furrepl || state.draft.furrepl.apt !== id) {
            state.draft.furrepl = { apt: id, space: "", task: "", qty: 1, reason: "", note: "", photos: [] };
        }
        const d = state.draft.furrepl;
        const spaces = a.spaces.filter((s) => a.modules.some((mod) => mod.space_id === s.id));
        const modules = a.modules.filter((mod) => String(mod.space_id) === String(d.space)).sort((x, y) => byName(x.label, y.label));
        const option = (value, label, current) => `<option value="${esc(value)}" ${String(current) === String(value) ? "selected" : ""}>${esc(label)}</option>`;
        return `${header("Pedir reposición", join(a.name, a.parent), "furapt")}
            <main class="page">
                <div class="card form">
                    <label>${esc(h.levelName("space", "Ambiente"))}<select data-bind="furrepl.space" data-rerender="1"><option value="">Elija</option>${spaces.map((s) => option(s.id, s.name, d.space)).join("")}</select></label>
                    <label>${esc(h.levelName("module", "Módulo"))}<select data-bind="furrepl.task" ${d.space ? "" : "disabled"}><option value="">Elija</option>${modules
                        .map((mod) => option(mod.id, join(mod.label, mod.name), d.task))
                        .join("")}</select></label>
                    <label>Cantidad<input type="number" min="1" step="1" inputmode="numeric" data-bind="furrepl.qty" value="${esc(d.qty)}"></label>
                    <label>Motivo<select data-bind="furrepl.reason"><option value="">Elija el motivo</option>${fur().reasons.map(([rid, name]) => option(rid, name, d.reason)).join("")}</select></label>
                    <label>Qué pasó<textarea rows="2" data-bind="furrepl.note">${esc(d.note)}</textarea></label>
                </div>
                ${photosCard("furrepl", d, true, "Fotos")}
                ${errorBox()}
                <button class="primary" data-action="save-fur-replacement">Enviar</button>
                <p class="hint">Queda en borrador en Odoo y sigue su flujo de aprobación y pedido a planta.</p>
            </main>`;
    };
    actions["save-fur-replacement"] = async () => {
        const d = state.draft.furrepl;
        const a = apartment(d.apt);
        const mod = a.modules.find((x) => String(x.id) === String(d.task) && String(x.space_id) === String(d.space));
        if (!mod) return alertInline("Elija el ambiente y el módulo.");
        if (!(Number(d.qty) > 0)) return alertInline("Indique la cantidad.");
        if (!d.reason) return alertInline("Elija el motivo.");
        if (!d.photos.length) return alertInline("Tome al menos una foto.");
        await enqueue("replacement", "/furniture/replacement",
            { uuid: uuid(), project_id: state.projectId, task_id: mod.id, qty: Number(d.qty), reason_id: Number(d.reason), note: d.note, photos: d.photos },
            `Reposición de ${mod.label} · ${a.name}`);
        const reason = fur().reasons.find(([rid]) => String(rid) === String(d.reason));
        a.replacements.push({ id: 0, name: "Por enviar", module: mod.label, space: mod.space, qty: Number(d.qty), state: "draft", state_label: "Borrador", reason: reason ? reason[1] : "" });
        saveCache();
        state.draft.furrepl = null;
        go("queue", { saved: "replacement" });
    };

    // ------------------------------------------------------------------
    // M122-05 · Recepción de módulos por departamento
    // ------------------------------------------------------------------
    const STATUS = [["ok", "Llegó"], ["missing", "No llegó"], ["damaged", "Llegó dañado"]];
    const modKey = (mod) => `${mod.move_id}:${mod.id}`;
    const damageKey = (pickingId, mod) => `furdmg${pickingId}_${mod.move_id}_${mod.id}`;
    function receptionDraft(picking) {
        const key = "reception" + picking.id;
        const d = (state.draft[key] = state.draft[key] || {
            received: Object.fromEntries(picking.lines.map((l) => [l.move_id, l.sent])), photos: [], note: "", edited: false,
        });
        d.status = d.status || {};
        return d;
    }
    function deliveryCard(p, on) {
        const title = p.departments ? "Despacho de módulos" : p.kind === "purchase" ? `Compra a ${p.partner || "proveedor"}` : "Despacho del almacén";
        const sub = p.departments ? join(p.name, plural(p.departments.length, "departamento", "departamentos")) : join(p.origin, p.name);
        return `<button class="card delivery ${on ? "on" : ""}" data-go="reception" data-id="${p.id}" aria-pressed="${on}"><b>${esc(title)}</b><small>${esc(sub)}</small></button>`;
    }
    const baseReception = screens.reception;
    screens.reception = () => {
        const deliveries = (state.data && state.data.deliveries) || [];
        const picking = deliveries.find((p) => p.id === Number(state.params.id)) || deliveries[0];
        // La recepción de materiales por producto no cambia.
        if (!picking || !picking.departments || !feature("module_reception")) {
            return baseReception();
        }
        const d = receptionDraft(picking);
        const moduleCard = (mod) => {
            const status = d.status[modKey(mod)] || "";
            let damage = "";
            if (status === "damaged") {
                const key = damageKey(picking.id, mod);
                const dd = (state.draft[key] = state.draft[key] || { photos: [], note: "", reason: "" });
                damage = `${photosCard(key, dd, true, "Foto del daño")}
                    <div class="form"><label>Qué pasó<input type="text" data-bind="${key}.note" value="${esc(dd.note)}"></label>
                    ${fur().reasons.length ? `<label>Motivo de la reposición<select data-bind="${key}.reason"><option value="">El primero del catálogo</option>${fur().reasons.map(([rid, name]) => `<option value="${rid}" ${String(dd.reason) === String(rid) ? "selected" : ""}>${esc(name)}</option>`).join("")}</select></label>` : ""}</div>`;
            }
            return `<div class="fur-mod line"><div><b>${esc(mod.label)}</b>${mod.name ? ` <small>${esc(mod.name)}</small>` : ""}<small class="fur-sub">${esc(moduleSub(mod))}</small></div>
                <div class="fur-marks" role="group" aria-label="Cómo llegó ${esc(mod.label)}">${STATUS.map(([code, label]) => `<button class="pill-btn ${status === code ? (code === "ok" ? "ok" : "bad") : ""}" data-set="reception${picking.id}.status.${modKey(mod)}=${code}" aria-pressed="${status === code}">${label}</button>`).join("")}</div>${damage}</div>`;
        };
        return `${header("Recepción", join(picking.name, plural(picking.departments.length, "departamento", "departamentos")), "home")}
            <main class="page">
                ${deliveries.length > 1 ? deliveries.map((p) => deliveryCard(p, p.id === picking.id)).join("") : ""}
                ${picking.departments
                    .map((dep) => {
                        const all = dep.modules.every((mod) => d.status[modKey(mod)] === "ok");
                        return `<div class="card"><div class="row between"><b>${esc(dep.name)}</b>${all ? pill("Llegó todo", "ok") : `<button class="chip outline" data-fur-all="${picking.id}:${dep.id}">Llegó todo</button>`}</div>
                            ${dep.modules.map(moduleCard).join("")}</div>`;
                    })
                    .join("")}
                ${picking.lines.length
                    ? `<div class="card"><div class="row lines-head"><span class="grow">Otros materiales</span><span>Enviado</span><span class="rec">Recibido</span></div>${picking.lines
                          .map((l) => `<div class="row line"><span class="grow"><b>${esc(l.name)}</b></span><span>${qtyText(l.sent)}</span>
                              <div class="stepper small"><button data-received="${picking.id}:${l.move_id}" data-delta="-1" aria-label="Restar">−</button><b aria-label="Recibido">${qtyText(d.received[l.move_id])}</b><button data-received="${picking.id}:${l.move_id}" data-delta="1" aria-label="Sumar">+</button></div></div>`)
                          .join("")}</div>`
                    : ""}
                ${photosCard("reception" + picking.id, d, true, "Foto de la guía firmada")}
                <div class="card form"><label>Observación<textarea rows="2" data-bind="reception${picking.id}.note" placeholder="Opcional">${esc(d.note)}</textarea></label></div>
                ${errorBox()}
                <button class="primary" data-action="save-fur-reception" data-id="${picking.id}">Confirmar recepción</button>
                <p class="hint">Lo que no llegó queda en la entrega parcial; lo que llegó dañado entra a la obra y abre su reposición en borrador.</p>
            </main>`;
    };
    actions["save-fur-reception"] = async (el) => {
        const id = Number(el.dataset.id);
        const picking = state.data.deliveries.find((p) => p.id === id);
        const d = receptionDraft(picking);
        const all = picking.departments.flatMap((dep) => dep.modules);
        if (all.some((mod) => !d.status[modKey(mod)])) {
            return alertInline("Marque cada módulo: llegó, no llegó o llegó dañado. «Llegó todo» marca un departamento completo.");
        }
        const modules = [];
        for (const mod of all) {
            const status = d.status[modKey(mod)];
            const row = { move_id: mod.move_id, task_id: mod.id, status };
            if (status === "damaged") {
                const dd = state.draft[damageKey(id, mod)] || { photos: [] };
                if (!dd.photos.length) return alertInline(`Tome la foto del daño de ${mod.label}.`);
                Object.assign(row, { photos: dd.photos, note: dd.note || "", reason_id: dd.reason ? Number(dd.reason) : false });
            }
            modules.push(row);
        }
        if (!modules.some((row) => row.status !== "missing") && !picking.lines.some((l) => Number(d.received[l.move_id]) > 0)) {
            return alertInline("No recibió nada de esta entrega.");
        }
        if (!d.photos.length) return alertInline("Tome la foto de la guía firmada.");
        const payload = {
            uuid: uuid(), project_id: state.projectId, picking_id: id, note: d.note, photos: d.photos, modules,
            lines: picking.lines.map((l) => ({ move_id: l.move_id, qty: Number(d.received[l.move_id] || 0) })),
        };
        await enqueue("reception", "/furniture/module-reception", payload, `Recepción de módulos de ${picking.name}`);
        state.data.deliveries = state.data.deliveries.filter((p) => p.id !== id);
        all.forEach((mod) => {
            state.draft[damageKey(id, mod)] = null;
        });
        state.draft["reception" + id] = null;
        go("queue", { saved: "reception" });
    };

    // ------------------------------------------------------------------
    // Toques propios (se atienden antes que la navegación de la aplicación)
    // ------------------------------------------------------------------
    P.clicks.push(async (data) => {
        if (data.furGo) {
            mem.apt = Number(data.id);
            if (data.furGo === "furstage") mem.back = data.back || "partidas";
            go(data.furGo, { id: data.id });
            return true;
        }
        if (data.furCell) {
            const d = state.draft.furstage;
            if (!d) return true;
            const key = data.furCell;
            if (d.cells[key] === undefined) {
                d.cells[key] = 100;
                d.selected = key;
            } else if (d.selected === key) {
                delete d.cells[key];
                d.selected = "";
            } else {
                d.selected = key;
            }
            state.params.error = "";
            render();
            return true;
        }
        if (data.furCol !== undefined) {
            const d = state.draft.furstage;
            if (!d) return true;
            const i = Number(data.furCol);
            matrix(d.apt).rows.forEach((r) => {
                if (r.cells[i]) d.cells[cellKey(r.id, i)] = 100;
            });
            d.selected = "";
            state.params.error = "";
            render();
            return true;
        }
        if (data.furAll) {
            const [pickingId, depId] = data.furAll.split(":").map(Number);
            const picking = ((state.data && state.data.deliveries) || []).find((p) => p.id === pickingId);
            const dep = picking && (picking.departments || []).find((x) => x.id === depId);
            if (dep) {
                const d = receptionDraft(picking);
                dep.modules.forEach((mod) => {
                    d.status[modKey(mod)] = "ok";
                });
                state.params.error = "";
                render();
            }
            return true;
        }
        return false;
    });
})();

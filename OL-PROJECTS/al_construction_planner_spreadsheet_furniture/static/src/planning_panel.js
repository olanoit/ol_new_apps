/**
 * Panel «Planificación» del maestro (paquete 1.13, M113-08).
 *
 * Muestra la pestaña activa (filas, errores y avisos de la última
 * validación), la ayuda de la columna seleccionada, los indicadores del piso
 * de la fila en ARBOL y los enlaces a Odoo. Sus acciones guardan una versión
 * de la hoja antes de escribir:
 *
 * - ARBOL: copiar un piso a otros pisos, asignar una tipología a la selección
 *   y numerar los ambientes repetidos de un departamento;
 * - TIPOLOGIAS y FICHA: crear una variante (03 → 03A);
 * - BOM y PIEZAS: reemplazar un material (M113-06, punto 7);
 * - todas: ver la ficha de la tipología.
 *
 * El clic derecho en una celda ofrece «Ver ficha de la tipología», «Copiar
 * este piso a…» e «Ir a la fila de origen (FUENTES)».
 */
import { Component, useState, xml } from "@odoo/owl";
import { components, registries } from "@odoo/o-spreadsheet";
import { _t } from "@web/core/l10n/translation";
import {
    activateSheet,
    collectSheets,
    dispatchBatch,
    ERRORS_SHEET,
    keyColumns,
    normText,
} from "@al_construction_planner_spreadsheet/send_to_planner";
import {
    columnValues,
    groupTreeByFloor,
    hasFloorGroups,
    headerIndex,
    headerRow,
    lastRowOf,
    TREE_SHEET,
} from "./floor_groups";
import { CARD_SHEET, originRows, selectedTypology, showCard } from "./planning";
import { ensureCapacity } from "./sheet_import";

const { sidePanelRegistry, cellMenuRegistry, topbarMenuRegistry } = registries;
const { Section } = components;

export const PANEL = "AlConstructionPlanning";
const VARIANT_SHEETS = ["TIPOLOGIAS", "MUEBLES", "MODULOS", "ACTIVIDADES", "PIEZAS", "BOM"];
const MATERIAL_SHEETS = ["BOM", "PIEZAS"];
const REFERENCE_SHEET = "REFERENCIAS";
const PICK_SEPARATOR = " · ";

const isFurniture = (env) =>
    env.constructionSheetKind && env.constructionSheetKind() === "furniture";

function activeName(env) {
    const getters = env.model.getters;
    return getters.getSheetName(getters.getActiveSheetId());
}

const isEmpty = (value) => value === null || value === undefined || value === "";

/** Texto de la celda como lo escribió el usuario (sin fórmulas); si no, su valor. */
function cellText(model, sheetId, col, row) {
    const cell = model.getters.getCell({ sheetId, col, row });
    if (cell && cell.content && !cell.isFormula) {
        return cell.content;
    }
    const value = model.getters.getEvaluatedCell({ sheetId, col, row }).value;
    return isEmpty(value) ? "" : String(value);
}

/** Código del producto de «nombre · unidad · código» o «[código] nombre». */
export function pickCode(text) {
    const value = String(text ?? "").trim();
    if (!value) {
        return "";
    }
    if (value.startsWith("[") && value.includes("]")) {
        return value.slice(1, value.indexOf("]"));
    }
    const parts = value.split(PICK_SEPARATOR);
    return parts[parts.length - 1].trim();
}

/** Guarda la versión de la hoja antes de escribir (M113-08). */
async function saveVersion(env, reason) {
    return env.constructionCall("construction_version_before", reason);
}

/** Pestaña, columnas por clave y última fila con datos en ``cols``. */
function sheetInfo(model, name, required = []) {
    const sheetId = model.getters.getSheetIdByName(name);
    if (!sheetId) {
        return null;
    }
    const keys = keyColumns(model)[name] || {};
    const header = headerRow(model, sheetId);
    const columns = { ...keys };
    for (const key of required) {
        if (columns[key] === undefined) {
            return null;
        }
    }
    const cols = Object.values(columns);
    const last = cols.length ? lastRowOf(model, sheetId, cols) : 0;
    return { sheetId, keys: columns, header, last };
}

/** Celdas de datos (sin fórmulas) de una fila: {columna: texto}. */
function dataCells(model, sheetId, row, ncols) {
    const cells = {};
    for (let col = 0; col < ncols; col++) {
        const cell = model.getters.getCell({ sheetId, col, row });
        if (cell && cell.content && !cell.isFormula) {
            cells[col] = cell.content;
        }
    }
    return cells;
}

/** «3-9», «3, 5, 7» o «3-5, 8» → [3, 4, 5, 8]. */
export function parseFloors(text) {
    const result = [];
    for (const part of String(text || "").split(/[,;]/)) {
        const match = /^\s*(-?\d+)\s*(?:-|a|al)\s*(-?\d+)\s*$/i.exec(part);
        if (match) {
            const [from, to] = [Number(match[1]), Number(match[2])];
            for (let n = Math.min(from, to); n <= Math.max(from, to); n++) {
                result.push(n);
            }
        } else if (/^\s*-?\d+\s*$/.test(part)) {
            result.push(Number(part));
        }
    }
    return [...new Set(result)];
}

/** El número del piso cambia en su nombre y al inicio del número del dpto. */
export function renumber(text, from, to) {
    const value = String(text ?? "");
    const fromText = String(from);
    return value.replace(/\d+/, (digits) =>
        digits.startsWith(fromText) && digits.length > fromText.length
            ? String(to) + digits.slice(fromText.length)
            : digits === fromText
            ? String(to)
            : digits
    );
}

// ---------------------------------------------------------------------------
// ARBOL
// ---------------------------------------------------------------------------
function treeInfo(model) {
    return sheetInfo(model, TREE_SHEET, ["floor", "apartment", "space"]);
}

/** «Torre A / Piso 2» o «Piso 2» de la fila ``row`` de ARBOL. */
function floorKeyAt(model, info, row) {
    const floor = cellText(model, info.sheetId, info.keys.floor, row);
    if (!floor) {
        return "";
    }
    const group =
        info.keys.group !== undefined ? cellText(model, info.sheetId, info.keys.group, row) : "";
    return group ? `${group} / ${floor}` : floor;
}

/** Filas de datos de ARBOL (sin las de resumen): [{row, floorKey, ...claves}]. */
function treeRows(model, info) {
    const rows = [];
    for (let row = 1; row <= info.last; row++) {
        const space = cellText(model, info.sheetId, info.keys.space, row);
        const floor = cellText(model, info.sheetId, info.keys.floor, row);
        if (!space && !floor) {
            continue;
        }
        const values = {};
        for (const [key, col] of Object.entries(info.keys)) {
            values[key] = cellText(model, info.sheetId, col, row);
        }
        rows.push({ row, floorKey: floorKeyAt(model, info, row), ...values });
    }
    return rows;
}

/** Escribe filas nuevas al final de la pestaña: [{columna: texto}]. */
async function appendRows(env, info, rows) {
    if (!rows.length) {
        return 0;
    }
    await ensureCapacity(env, info.last + rows.length);
    const commands = [];
    rows.forEach((cells, index) => {
        for (const [col, content] of Object.entries(cells)) {
            commands.push([
                "UPDATE_CELL",
                { sheetId: info.sheetId, col: Number(col), row: info.last + 1 + index, content },
            ]);
        }
    });
    dispatchBatch(env.model, commands);
    return rows.length;
}

export async function copyFloor(env, source, targetsText) {
    const model = env.model;
    const info = treeInfo(model);
    if (!info) {
        return _t("ARBOL no tiene las columnas Piso, Departamento y Ambiente.");
    }
    const rows = treeRows(model, info);
    const sourceRows = rows.filter((row) => normText(row.floorKey) === normText(source));
    if (!sourceRows.length) {
        return _t("El piso %s no tiene ambientes en ARBOL.", source);
    }
    const number = /\d+/.exec(sourceRows[0].floor);
    if (!number) {
        return _t("El nombre del piso %s no tiene número.", source);
    }
    const from = Number(number[0]);
    const targets = parseFloors(targetsText).filter((n) => n !== from);
    if (!targets.length) {
        return _t("Escriba los pisos de destino, por ejemplo «3-9» o «3, 5, 7».");
    }
    const existing = new Set(rows.map((row) => normText(row.floorKey)));
    const ncols = model.getters.getNumberCols(info.sheetId);
    const newRows = [];
    const skipped = [];
    for (const target of targets) {
        const floorName = renumber(sourceRows[0].floor, from, target);
        const group = sourceRows[0].group || "";
        const key = group ? `${group} / ${floorName}` : floorName;
        if (existing.has(normText(key))) {
            skipped.push(floorName);
            continue;
        }
        for (const sourceRow of sourceRows) {
            const cells = dataCells(model, info.sheetId, sourceRow.row, ncols);
            cells[info.keys.floor] = floorName;
            cells[info.keys.apartment] = renumber(sourceRow.apartment, from, target);
            newRows.push(cells);
        }
    }
    if (!newRows.length) {
        return _t("Los pisos de destino ya tienen ambientes: %s.", skipped.join(", "));
    }
    await saveVersion(env, _t("Antes de copiar el piso %s", source));
    const grouped = hasFloorGroups(model);
    await appendRows(env, info, newRows);
    if (grouped) {
        groupTreeByFloor(model);
    }
    env.constructionNotify(
        skipped.length
            ? _t("%(count)s ambientes nuevos. Ya tenían ambientes y no se copiaron: %(floors)s.", {
                  count: newRows.length,
                  floors: skipped.join(", "),
              })
            : _t("%s ambientes nuevos (versión anterior guardada).", newRows.length),
        skipped.length ? "warning" : "success"
    );
    return "";
}

/** Códigos de TIPOLOGIAS como texto. */
function typologyCodes(model) {
    const info = sheetInfo(model, "TIPOLOGIAS", ["code"]);
    if (!info) {
        return [];
    }
    const codes = [];
    for (let row = 1; row <= info.last; row++) {
        const code = cellText(model, info.sheetId, info.keys.code, row);
        if (code) {
            codes.push(code);
        }
    }
    return codes;
}

export async function assignTypology(env, code) {
    const model = env.model;
    const info = treeInfo(model);
    if (!info || info.keys.typology === undefined) {
        return _t("ARBOL no tiene la columna Tipología.");
    }
    const codes = typologyCodes(model);
    const typology = codes.find((value) => normText(value) === normText(code));
    if (!typology) {
        return _t("La tipología %s no está en TIPOLOGIAS.", code);
    }
    if (model.getters.getActiveSheetId() !== info.sheetId) {
        return _t("Seleccione las filas en ARBOL.");
    }
    const rows = new Set();
    for (const zone of model.getters.getSelectedZones()) {
        for (let row = Math.max(1, zone.top); row <= zone.bottom; row++) {
            if (cellText(model, info.sheetId, info.keys.space, row)) {
                rows.add(row);
            }
        }
    }
    if (!rows.size) {
        return _t("Seleccione filas de ARBOL con ambiente.");
    }
    await saveVersion(env, _t("Antes de asignar la tipología %s", typology));
    dispatchBatch(
        model,
        [...rows].map((row) => [
            "UPDATE_CELL",
            { sheetId: info.sheetId, col: info.keys.typology, row, content: typology },
        ])
    );
    env.constructionNotify(_t("Tipología %(code)s en %(count)s ambientes.", {
        code: typology,
        count: rows.size,
    }));
    return "";
}

export async function numberRepeated(env) {
    const model = env.model;
    const info = treeInfo(model);
    if (!info) {
        return _t("ARBOL no tiene las columnas Piso, Departamento y Ambiente.");
    }
    const byUnit = {};
    for (const row of treeRows(model, info)) {
        if (!row.space) {
            continue;
        }
        const unit = `${normText(row.floorKey)}|${normText(row.apartment)}|${normText(row.space)}`;
        (byUnit[unit] = byUnit[unit] || []).push(row);
    }
    const commands = [];
    for (const rows of Object.values(byUnit)) {
        if (rows.length < 2) {
            continue;
        }
        rows.forEach((row, index) => {
            commands.push([
                "UPDATE_CELL",
                {
                    sheetId: info.sheetId,
                    col: info.keys.space,
                    row: row.row,
                    content: `${row.space} ${index + 1}`,
                },
            ]);
        });
    }
    if (!commands.length) {
        env.constructionNotify(_t("No hay ambientes repetidos en un mismo departamento."));
        return "";
    }
    await saveVersion(env, _t("Antes de numerar los ambientes repetidos"));
    dispatchBatch(model, commands);
    env.constructionNotify(_t("%s ambientes numerados.", commands.length));
    return "";
}

// ---------------------------------------------------------------------------
// TIPOLOGIAS y FICHA: crear variante
// ---------------------------------------------------------------------------
/** Sufijo libre siguiente: 03A, 03B… */
export function nextSuffix(code, codes) {
    const taken = new Set(codes.map(normText));
    for (let index = 0; index < 26; index++) {
        const suffix = String.fromCharCode(65 + index);
        if (!taken.has(normText(`${code}${suffix}`))) {
            return suffix;
        }
    }
    return "";
}

export async function createVariant(env, code, suffix) {
    const model = env.model;
    const codes = typologyCodes(model);
    const base = codes.find((value) => normText(value) === normText(code));
    if (!base) {
        return _t("La tipología %s no está en TIPOLOGIAS.", code);
    }
    const variant = `${base}${String(suffix || "").trim()}`;
    if (!suffix || codes.some((value) => normText(value) === normText(variant))) {
        return _t("La variante %s ya existe o le falta el sufijo.", variant);
    }
    const plans = [];
    for (const name of VARIANT_SHEETS) {
        const typologyKey = name === "TIPOLOGIAS" ? "code" : "typology";
        const info = sheetInfo(model, name, [typologyKey]);
        if (!info) {
            continue;
        }
        const ncols = model.getters.getNumberCols(info.sheetId);
        const rows = [];
        for (let row = 1; row <= info.last; row++) {
            const value = cellText(model, info.sheetId, info.keys[typologyKey], row);
            if (normText(value) !== normText(base)) {
                continue;
            }
            const cells = dataCells(model, info.sheetId, row, ncols);
            cells[info.keys[typologyKey]] = variant;
            if (name === "TIPOLOGIAS") {
                if (info.keys.variant_of !== undefined) {
                    cells[info.keys.variant_of] = base;
                }
                if (info.keys.name !== undefined && cells[info.keys.name]) {
                    cells[info.keys.name] = `${cells[info.keys.name]} ${suffix}`;
                }
                // Los otros nombres son de la tipología base.
                if (info.keys.aliases !== undefined) {
                    delete cells[info.keys.aliases];
                }
            }
            rows.push(cells);
        }
        plans.push([info, rows]);
    }
    await saveVersion(env, _t("Antes de crear la variante %s", variant));
    const counts = [];
    for (const [info, rows] of plans) {
        // Cada pestaña se vuelve a leer: ensureCapacity puede haber ampliado.
        const fresh = { ...info, last: lastRowOf(model, info.sheetId, Object.values(info.keys)) };
        const count = await appendRows(env, fresh, rows);
        if (count) {
            counts.push(`${model.getters.getSheetName(info.sheetId)} ${count}`);
        }
    }
    env.constructionNotify(
        _t("Variante %(code)s creada: %(counts)s.", { code: variant, counts: counts.join(", ") })
    );
    return "";
}

// ---------------------------------------------------------------------------
// BOM y PIEZAS: reemplazar un material (M113-06, punto 7)
// ---------------------------------------------------------------------------
/** Productos de REFERENCIAS: [{pick, code, short, group}] (columnas P, K, O, Q). */
function referenceProducts(model) {
    const sheetId = model.getters.getSheetIdByName(REFERENCE_SHEET);
    if (!sheetId) {
        return [];
    }
    const products = [];
    const rows = model.getters.getNumberRows(sheetId);
    const value = (col, row) => {
        const result = model.getters.getEvaluatedCell({ sheetId, col, row }).value;
        return isEmpty(result) ? "" : String(result);
    };
    for (let row = 2; row < rows; row++) {
        const code = value(10, row); // K
        if (!code) {
            continue;
        }
        products.push({ code, pick: value(15, row), short: value(14, row), group: value(16, row) });
    }
    return products;
}

export async function replaceMaterial(env, oldText, newText, typology) {
    const model = env.model;
    const oldCode = pickCode(oldText);
    if (!oldCode) {
        return _t("Elija el material que se reemplaza.");
    }
    const products = referenceProducts(model);
    const wanted = normText(newText);
    const product =
        products.find((item) => normText(item.pick) === wanted) ||
        products.find((item) => normText(item.code) === normText(pickCode(newText)));
    if (!product) {
        return _t("El material nuevo no está en el maestro de productos (REFERENCIAS).");
    }
    const changes = [];
    for (const name of MATERIAL_SHEETS) {
        const info = sheetInfo(model, name, ["product_name"]);
        if (!info) {
            continue;
        }
        const codeCol = info.keys.product_code;
        for (let row = 1; row <= info.last; row++) {
            const current =
                codeCol !== undefined
                    ? cellText(model, info.sheetId, codeCol, row)
                    : pickCode(cellText(model, info.sheetId, info.keys.product_name, row));
            if (normText(current) !== normText(oldCode)) {
                continue;
            }
            if (
                typology &&
                info.keys.typology !== undefined &&
                normText(cellText(model, info.sheetId, info.keys.typology, row)) !==
                    normText(typology)
            ) {
                continue;
            }
            const cells = { [info.keys.product_name]: product.pick || product.code };
            if (info.keys.categ !== undefined && product.short) {
                cells[info.keys.categ] = product.short;
            }
            if (info.keys.categ_group !== undefined && product.group) {
                cells[info.keys.categ_group] = product.group;
            }
            changes.push([info.sheetId, row, cells]);
        }
    }
    if (!changes.length) {
        return typology
            ? _t("La tipología %(typology)s no usa el material %(code)s.", {
                  typology,
                  code: oldCode,
              })
            : _t("Ninguna fila de BOM ni de PIEZAS usa el material %s.", oldCode);
    }
    await saveVersion(env, _t("Antes de reemplazar el material %s", oldCode));
    const commands = [];
    for (const [sheetId, row, cells] of changes) {
        for (const [col, content] of Object.entries(cells)) {
            commands.push(["UPDATE_CELL", { sheetId, col: Number(col), row, content }]);
        }
    }
    dispatchBatch(model, commands);
    env.constructionNotify(
        _t("%(old)s reemplazado por %(new)s en %(count)s filas.", {
            old: oldCode,
            new: product.code,
            count: changes.length,
        })
    );
    return "";
}

// ---------------------------------------------------------------------------
// FUENTES: ir a la fila de origen
// ---------------------------------------------------------------------------
export function goToSource(env) {
    const model = env.model;
    const getters = model.getters;
    const sourceId = getters.getSheetIdByName("FUENTES");
    const info = treeInfo(model);
    if (!sourceId || !info || getters.getActiveSheetId() !== info.sheetId) {
        env.constructionNotify(_t("Seleccione una fila de ARBOL y tenga la pestaña FUENTES."), "warning");
        return;
    }
    const { row } = getters.getActivePosition();
    const wanted = {
        piso: [floorKeyAt(model, info, row), cellText(model, info.sheetId, info.keys.floor, row)],
        departamento: [cellText(model, info.sheetId, info.keys.apartment, row)],
        ambiente: [cellText(model, info.sheetId, info.keys.space, row)],
    };
    const rows = collectSheets(model, ["FUENTES"]).FUENTES || [];
    const header = (rows[0] || []).map(normText);
    const columns = Object.entries({
        piso: ["piso"],
        departamento: ["departamento", "dpto", "unidad"],
        ambiente: ["ambiente", "espacio"],
    })
        .map(([key, names]) => [key, header.findIndex((text) => names.includes(text))])
        .filter(([, col]) => col >= 0);
    if (!columns.length) {
        env.constructionNotify(_t("FUENTES no tiene las columnas Piso, Departamento o Ambiente."), "warning");
        return;
    }
    const match = (values, strict) =>
        columns.every(([key, col]) => {
            const options = wanted[key].filter(Boolean).map(normText);
            if (!options.length) {
                return !strict;
            }
            return options.includes(normText(values[col]));
        });
    let found = rows.findIndex((values, index) => index > 0 && match(values, true));
    if (found < 0) {
        found = rows.findIndex((values, index) => index > 0 && match(values, false));
    }
    if (found < 0) {
        env.constructionNotify(_t("No se encontró la fila de origen en FUENTES."), "warning");
        return;
    }
    activateSheet(model, sourceId);
    model.selection.selectCell(columns[0][1], found);
}

// ---------------------------------------------------------------------------
// Panel
// ---------------------------------------------------------------------------
export class PlanningPanel extends Component {
    static template = xml`
<div class="o-al-planning p-2">
  <Section title="sheetTitle">
    <div t-if="sheetSummary.rows !== null">Filas con datos: <b t-esc="sheetSummary.rows"/></div>
    <div>
      Última validación: <b t-esc="sheetSummary.errors"/> errores · <b t-esc="sheetSummary.warnings"/> avisos
    </div>
    <button class="o-button-link p-0" t-on-click="refresh">Actualizar</button>
  </Section>
  <Section t-if="columnHelp" title="columnHelp.title">
    <div t-esc="columnHelp.help"/>
    <div t-if="columnHelp.values" class="text-muted mt-1">Valores: <t t-esc="columnHelp.values"/></div>
  </Section>
  <Section t-if="floorStats" title="floorStats.title">
    <table class="table table-sm mb-0">
      <thead><tr><th/><th>Hoja</th><th t-if="floorStats.origin">Origen</th></tr></thead>
      <tbody>
        <tr t-foreach="floorStats.lines" t-as="line" t-key="line[0]"
            t-att-class="floorStats.origin and line[2] !== '' and line[1] != line[2] ? 'text-danger' : ''">
          <td t-esc="line[0]"/><td t-esc="line[1]"/><td t-if="floorStats.origin" t-esc="line[2]"/>
        </tr>
      </tbody>
    </table>
  </Section>
  <Section title="actionsTitle">
    <t t-if="sheetName === 'ARBOL'">
      <div class="fw-bold mt-1">Copiar piso a otros pisos</div>
      <input class="o-input mb-1" t-att-placeholder="floorStats ? floorStats.title : 'Piso de origen'" t-model="state.source"/>
      <input class="o-input mb-1" placeholder="Pisos de destino: 3-9 o 3, 5, 7" t-model="state.targets"/>
      <button class="o-button primary mb-2" t-att-disabled="state.busy" t-on-click="onCopyFloor">Copiar piso</button>
      <div class="fw-bold mt-1">Asignar tipología a la selección</div>
      <select class="o-input mb-1" t-model="state.typology">
        <option value="">Tipología…</option>
        <option t-foreach="typologies" t-as="code" t-key="code_index" t-att-value="code" t-esc="code"/>
      </select>
      <button class="o-button mb-2" t-att-disabled="state.busy" t-on-click="onAssignTypology">Asignar a las filas seleccionadas</button>
      <button class="o-button mb-2" t-att-disabled="state.busy" t-on-click="onNumberRepeated">Numerar ambientes repetidos</button>
      <button class="o-button mb-2" t-att-disabled="state.busy" t-on-click="onGroupFloors">Agrupar filas por piso</button>
    </t>
    <t t-if="sheetName === 'TIPOLOGIAS' or sheetName === 'FICHA'">
      <div class="fw-bold mt-1">Crear variante de <t t-esc="currentTypology or '…'"/></div>
      <input class="o-input mb-1" placeholder="Sufijo (A, B…)" t-model="state.suffix"/>
      <button class="o-button primary mb-2" t-att-disabled="state.busy or !currentTypology" t-on-click="onCreateVariant">Crear variante</button>
    </t>
    <t t-if="sheetName === 'BOM' or sheetName === 'PIEZAS'">
      <div class="fw-bold mt-1">Reemplazar un material</div>
      <input class="o-input mb-1" placeholder="Material actual" t-model="state.oldMaterial"/>
      <input class="o-input mb-1" placeholder="Material nuevo: escriba parte del nombre" list="o_al_planning_products"
             t-model="state.newMaterial" t-on-focus="loadProducts"/>
      <datalist id="o_al_planning_products">
        <option t-foreach="state.products" t-as="pick" t-key="pick_index" t-att-value="pick"/>
      </datalist>
      <select class="o-input mb-1" t-model="state.scope">
        <option value="typology">Solo la tipología <t t-esc="currentTypology"/></option>
        <option value="all">Toda la hoja</option>
      </select>
      <button class="o-button primary mb-2" t-att-disabled="state.busy" t-on-click="onReplaceMaterial">Reemplazar</button>
    </t>
    <button t-if="currentTypology" class="o-button mb-2" t-on-click="onViewCard">Ver ficha de <t t-esc="currentTypology"/></button>
    <div t-if="state.message" class="text-danger" t-esc="state.message"/>
  </Section>
  <Section title="linksTitle">
    <button class="o-button-link d-block p-0 mb-1" t-on-click="() => this.openLink('project')">Abrir la obra</button>
    <button class="o-button-link d-block p-0" t-on-click="() => this.openLink('tree')">Abrir el árbol en el planificador</button>
  </Section>
</div>`;
    static components = { Section };
    static props = {
        onCloseSidePanel: Function,
        copyFrom: { type: String, optional: true },
    };

    setup() {
        this.state = useState({
            source: this.props.copyFrom || "",
            targets: "",
            typology: "",
            suffix: "",
            oldMaterial: "",
            newMaterial: "",
            scope: "typology",
            busy: false,
            message: "",
            products: [],
            version: 0,
        });
        this.cache = {};
        this.actionsTitle = _t("Acciones (guardan una versión antes)");
        this.linksTitle = _t("Enlaces a Odoo");
    }

    get model() {
        return this.env.model;
    }

    get sheetName() {
        return activeName(this.env);
    }

    get sheetTitle() {
        return _t("Pestaña %s", this.sheetName);
    }

    /** Filas, errores y avisos de la pestaña activa (se recalcula al cambiar de pestaña). */
    get sheetSummary() {
        const key = `${this.sheetName}|${this.state.version}`;
        if (this.cache.summaryKey !== key) {
            const model = this.model;
            const sheetId = model.getters.getActiveSheetId();
            const keys = keyColumns(model)[this.sheetName];
            const rows = keys ? lastRowOf(model, sheetId, Object.values(keys)) : null;
            let errors = 0;
            let warnings = 0;
            for (const row of (collectSheets(model, [ERRORS_SHEET])[ERRORS_SHEET] || []).slice(2)) {
                if (normText(row[0]) === normText(this.sheetName)) {
                    if (normText(row[4]) === "error") {
                        errors++;
                    } else {
                        warnings++;
                    }
                }
            }
            this.cache.summaryKey = key;
            this.cache.summary = { rows, errors, warnings };
        }
        return this.cache.summary;
    }

    /** Ayuda de la columna seleccionada: SHEETS y la lista de la celda. */
    get columnHelp() {
        const getters = this.model.getters;
        const sheetId = getters.getActiveSheetId();
        const { col, row } = getters.getActivePosition();
        const help = this.env.constructionMetadata?.("construction_column_help") || {};
        const sheetHelp = help[this.sheetName];
        if (!sheetHelp) {
            return null;
        }
        const keys = keyColumns(this.model)[this.sheetName] || {};
        const key = Object.keys(keys).find((name) => keys[name] === col);
        const header = getters.getEvaluatedCell({ sheetId, col, row: 0 }).value;
        const entry = (key && sheetHelp[key]) || sheetHelp[header];
        if (!entry) {
            return null;
        }
        let values = (entry[3] || []).join(", ");
        const rule = getters.getValidationRuleForCell?.({ sheetId, col, row: Math.max(row, 1) });
        if (!values && rule?.criterion?.type === "isValueInList") {
            values = rule.criterion.values.join(", ");
        }
        return {
            title: entry[2] ? _t("%s (obligatoria)", entry[0]) : entry[0],
            help: entry[1],
            values,
        };
    }

    /** Indicadores del piso de la fila seleccionada en ARBOL, contra FUENTES. */
    get floorStats() {
        if (this.sheetName !== TREE_SHEET) {
            return null;
        }
        const model = this.model;
        const info = treeInfo(model);
        if (!info) {
            return null;
        }
        const { row } = model.getters.getActivePosition();
        const floorKey = row >= 1 ? floorKeyAt(model, info, row) : "";
        if (!floorKey) {
            return null;
        }
        const cacheKey = `${floorKey}|${this.state.version}`;
        if (this.cache.floorKey !== cacheKey) {
            const header = info.header;
            const floorCalc = headerIndex(header, "Piso (calc.)");
            const modulesCalc = headerIndex(header, "Módulos (calc.)");
            const mlCalc = headerIndex(header, "ML (calc.)");
            let spaces = 0;
            let modules = 0;
            let ml = 0;
            if (floorCalc >= 0) {
                const floors = columnValues(model, info.sheetId, floorCalc, info.last);
                const moduleValues =
                    modulesCalc >= 0 ? columnValues(model, info.sheetId, modulesCalc, info.last) : [];
                const mlValues = mlCalc >= 0 ? columnValues(model, info.sheetId, mlCalc, info.last) : [];
                floors.forEach((value, index) => {
                    if (normText(value) === normText(floorKey)) {
                        spaces++;
                        modules += Number(moduleValues[index]) || 0;
                        ml += Number(mlValues[index]) || 0;
                    }
                });
            } else {
                spaces = treeRows(model, info).filter(
                    (item) => normText(item.floorKey) === normText(floorKey)
                ).length;
            }
            const origin = originRows(model).find(
                (values) => normText(values[0]) === normText(floorKey)
            );
            this.cache.floorKey = cacheKey;
            this.cache.floor = {
                title: _t("Indicadores de %s", floorKey),
                origin: Boolean(origin),
                lines: [
                    [_t("Ambientes"), spaces, origin ? origin[1] : ""],
                    [_t("Módulos"), modules, origin ? origin[2] : ""],
                    [_t("ML"), Math.round(ml * 100) / 100, origin ? origin[3] : ""],
                ],
            };
            this.cache.floorName = floorKey;
        }
        return this.cache.floor;
    }

    get typologies() {
        return typologyCodes(this.model);
    }

    get currentTypology() {
        if (this.sheetName === CARD_SHEET) {
            const sheetId = this.model.getters.getActiveSheetId();
            return cellText(this.model, sheetId, 1, 2); // B3
        }
        const value = selectedTypology(this.env);
        return isEmpty(value) ? "" : String(value);
    }

    refresh() {
        this.state.version++;
    }

    loadProducts() {
        if (!this.state.products.length) {
            this.state.products = referenceProducts(this.model)
                .map((item) => item.pick)
                .filter(Boolean);
        }
        if (!this.state.oldMaterial && MATERIAL_SHEETS.includes(this.sheetName)) {
            const info = sheetInfo(this.model, this.sheetName, ["product_name"]);
            const { row } = this.model.getters.getActivePosition();
            if (info && row >= 1) {
                this.state.oldMaterial = cellText(this.model, info.sheetId, info.keys.product_name, row);
            }
        }
    }

    async run(action) {
        this.state.busy = true;
        this.state.message = "";
        try {
            this.state.message = (await action()) || "";
        } finally {
            this.state.busy = false;
            this.state.version++;
        }
    }

    onCopyFloor() {
        // Sin piso escrito: el de la fila seleccionada en ARBOL.
        const source = this.state.source || this.cache.floorName || "";
        return this.run(() => copyFloor(this.env, source, this.state.targets));
    }

    onAssignTypology() {
        return this.run(() => assignTypology(this.env, this.state.typology));
    }

    onNumberRepeated() {
        return this.run(() => numberRepeated(this.env));
    }

    onGroupFloors() {
        return this.run(async () => {
            await saveVersion(this.env, _t("Antes de agrupar ARBOL por piso"));
            const count = groupTreeByFloor(this.model);
            this.env.constructionNotify(_t("ARBOL agrupado en %s pisos.", count));
            return "";
        });
    }

    onCreateVariant() {
        const code = this.currentTypology;
        const suffix = this.state.suffix || nextSuffix(code, typologyCodes(this.model));
        return this.run(() => createVariant(this.env, code, suffix));
    }

    onReplaceMaterial() {
        const typology = this.state.scope === "typology" ? this.currentTypology : "";
        if (this.state.scope === "typology" && !typology) {
            this.state.message = _t("Seleccione una fila con tipología o elija «Toda la hoja».");
            return;
        }
        return this.run(() =>
            replaceMaterial(this.env, this.state.oldMaterial, this.state.newMaterial, typology)
        );
    }

    onViewCard() {
        showCard(this.env, this.currentTypology);
    }

    async openLink(kind) {
        const action = await this.env.constructionCall("construction_open_link", kind);
        await this.env.constructionDoAction(action);
    }
}

sidePanelRegistry.add(PANEL, {
    title: _t("Planificación"),
    Body: PlanningPanel,
    computeState(getters, initialProps) {
        return { isOpen: true, props: initialProps, key: initialProps.copyFrom || "planning" };
    },
});

// ---------------------------------------------------------------------------
// Menús
// ---------------------------------------------------------------------------
async function upgradeSheet(env) {
    const model = env.model;
    const getters = model.getters;
    const keys = keyColumns(model);
    const send = (env.constructionSendSheets && env.constructionSendSheets()) || [];
    const master = {};
    const other = {};
    for (const sheetId of getters.getSheetIds()) {
        const name = getters.getSheetName(sheetId);
        if (send.includes(name) && !name.startsWith("_")) {
            const rows = collectSheets(model, [name])[name] || [];
            const formulaCols = [];
            for (let col = 0; col < getters.getNumberCols(sheetId); col++) {
                if (getters.getCell({ sheetId, col, row: 1 })?.isFormula) {
                    formulaCols.push(col);
                }
            }
            master[name] = { rows, keys: keys[name] || {}, formula_cols: formulaCols };
        } else {
            const cells = {};
            for (const cellId of Object.keys(getters.getCells(sheetId))) {
                const position = getters.getCellPosition(cellId);
                const cell = getters.getCell(position);
                if (cell?.content) {
                    cells[`${columnName(position.col)}${position.row + 1}`] = cell.content;
                }
            }
            other[name] = { cells };
        }
    }
    const action = await env.constructionCall("construction_sheet_upgrade", { master, other });
    await env.constructionDoAction(action);
}

function columnName(index) {
    let letters = "";
    index += 1;
    while (index) {
        const rest = (index - 1) % 26;
        letters = String.fromCharCode(65 + rest) + letters;
        index = Math.floor((index - 1) / 26);
    }
    return letters;
}

topbarMenuRegistry.addChild("construction_furniture_panel", ["construction_planner"], {
    name: _t("Panel Planificación"),
    sequence: 105,
    isVisible: isFurniture,
    execute: (env) => env.openSidePanel(PANEL, {}),
});
topbarMenuRegistry.addChild("construction_furniture_upgrade", ["construction_planner"], {
    name: _t("Actualizar a la plantilla vigente…"),
    sequence: 195,
    isVisible: isFurniture,
    execute: (env) =>
        env.askConfirmation(
            _t(
                "La hoja se rehace con la plantilla de hoy (INICIO, FICHA, PROGRAMA, CONTROL, columnas calculadas y listas) y los datos de sus pestañas. Antes se guarda una versión. Se pierden los formatos propios de las pestañas del maestro. ¿Continuar?"
            ),
            () => upgradeSheet(env)
        ),
});

const sheetHasTypology = (env) => isFurniture(env) && !isEmpty(selectedTypology(env));
cellMenuRegistry.add("construction_view_card", {
    name: _t("Ver ficha de la tipología"),
    sequence: 300,
    separator: false,
    isVisible: sheetHasTypology,
    execute: (env) => showCard(env, selectedTypology(env)),
});
cellMenuRegistry.add("construction_copy_floor", {
    name: _t("Copiar este piso a…"),
    sequence: 301,
    isVisible: (env) => isFurniture(env) && activeName(env) === TREE_SHEET,
    execute: (env) => {
        const info = treeInfo(env.model);
        const { row } = env.model.getters.getActivePosition();
        const floorKey = info && row >= 1 ? floorKeyAt(env.model, info, row) : "";
        env.openSidePanel(PANEL, { copyFrom: floorKey });
    },
});
cellMenuRegistry.add("construction_go_to_source", {
    name: _t("Ir a la fila de origen (FUENTES)"),
    sequence: 302,
    isVisible: (env) =>
        isFurniture(env) &&
        activeName(env) === TREE_SHEET &&
        Boolean(env.model.getters.getSheetIdByName("FUENTES")),
    execute: (env) => goToSource(env),
});

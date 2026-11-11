/**
 * CREVAL, paquete 5, CR-43: el insumo de INSUMOS se elige escribiendo parte
 * del nombre de un producto del maestro («Producto (escriba el nombre)», con
 * la lista de LISTAS que llena «Traer de Odoo»). Al elegirlo, la hoja escribe
 * en la misma fila el nombre, el código, el tipo, la unidad, el precio
 * vigente, la moneda y la fecha y la fuente del precio. Son datos: el precio
 * se cambia si el presupuestador cotizó otro y un producto nuevo se escribe a
 * mano, como antes.
 */
import { registries, UIPlugin } from "@odoo/o-spreadsheet";
import { keyColumns, normText } from "@al_construction_planner_spreadsheet/send_to_planner";

const { featurePluginRegistry } = registries;

export const PICK_HEADER = "Producto (escriba el nombre)";
export const LIST_HEADER = "Producto (nombre · código)";
// Columnas de LISTAS después de «Producto (nombre · código)», con su clave
// en INSUMOS (PRODUCT_LIST de project_project.py).
export const LIST_KEYS = ["name", "code", "kind", "uom", "price", "currency", "date", "source"];

export class ConstructionProductPickPlugin extends UIPlugin {
    /** {texto normalizado de la lista: [valores de LISTAS]} */
    productList() {
        if (this.products) {
            return this.products;
        }
        const getters = this.getters;
        const sheetId = getters.getSheetIdByName("LISTAS");
        this.products = {};
        if (!sheetId) {
            return this.products;
        }
        let start = -1;
        for (let col = 0; col < getters.getNumberCols(sheetId); col++) {
            if (getters.getCell({ sheetId, col, row: 0 })?.content === LIST_HEADER) {
                start = col;
                break;
            }
        }
        if (start < 0) {
            return this.products;
        }
        for (let row = 1; row < getters.getNumberRows(sheetId); row++) {
            const pick = getters.getCell({ sheetId, col: start, row })?.content;
            if (!pick) {
                continue;
            }
            this.products[normText(pick)] = LIST_KEYS.map(
                (_key, offset) => getters.getCell({ sheetId, col: start + offset + 1, row })?.content ?? ""
            );
        }
        return this.products;
    }

    handle(cmd) {
        if (cmd.type !== "UPDATE_CELL" || this.filling) {
            return;
        }
        const getters = this.getters;
        const name = getters.getSheetName(cmd.sheetId);
        if (name === "LISTAS") {
            this.products = null;
            return;
        }
        if (name !== "INSUMOS" || !cmd.row || !cmd.content) {
            return;
        }
        const header = getters.getCell({ sheetId: cmd.sheetId, col: cmd.col, row: 0 })?.content;
        if (header !== PICK_HEADER) {
            return;
        }
        const values = this.productList()[normText(cmd.content)];
        if (!values) {
            return;
        }
        const columns = keyColumns({ getters }).INSUMOS || {};
        this.filling = true;
        try {
            LIST_KEYS.forEach((key, index) => {
                const col = columns[key];
                if (col === undefined || col === cmd.col) {
                    return;
                }
                this.dispatch("UPDATE_CELL", {
                    sheetId: cmd.sheetId,
                    col,
                    row: cmd.row,
                    content: String(values[index] ?? ""),
                });
            });
        } finally {
            this.filling = false;
        }
    }
}
featurePluginRegistry.add("al_construction_product_pick", ConstructionProductPickPlugin);

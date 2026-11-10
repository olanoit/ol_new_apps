/**
 * Paquete 7 de CREVAL (CR-59 y CR-60): bloques «presupuestado contra
 * ejecutado» de la cartera de obras y de la ficha de la obra.
 *
 * Los datos los calcula el puente de ventas
 * (`project.project._construction_indicators`); aquí solo se dibujan, con el
 * mismo formato en las dos pantallas: montos en miles con un decimal,
 * porcentajes con un decimal. Sin el grupo «Ve montos» los montos llegan en
 * `false` y se muestra «—».
 */
import { Component } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { formatFloat } from "@web/core/utils/numbers";

/** Bloques e indicadores; `pct` = porcentaje, el resto montos. */
export const INDICATOR_BLOCKS = [
    {
        key: "today",
        label: _t("A hoy"),
        items: [
            { key: "sale", label: _t("Venta"), help: _t("Presup.: valorización prevista acumulada a hoy. Ejec.: ingreso contable de la obra.") },
            { key: "cost", label: _t("Costo"), help: _t("Presup.: costo programado a hoy. Ejec.: costo contable (apuntes analíticos en cuentas de gasto).") },
            { key: "margin", label: _t("Margen"), help: _t("Venta − costo, a hoy.") },
            { key: "margin_pct", label: _t("Margen %"), pct: true, light: "margin", help: _t("Margen ÷ venta.") },
        ],
    },
    {
        key: "progress",
        label: _t("Avance y valorización"),
        items: [
            { key: "physical", label: _t("Avance físico"), pct: true, help: _t("Presup.: avance programado a hoy. Ejec.: Σ avance de cada partida × su precio ÷ Σ precio, con la regla de «Avance de la partida» de la obra.") },
            { key: "valued", label: _t("Valorizado"), pct: true, help: _t("Valorizaciones (previstas o confirmadas) ÷ venta vigente.") },
            { key: "to_value", label: _t("Por valorizar"), help: _t("(Avance físico − valorizado) × venta: obra hecha que aún no se cobra.") },
        ],
    },
    {
        key: "month",
        label: _t("Mes"),
        items: [
            { key: "month_valuation", label: _t("Valorización"), help: _t("Presup.: meta aprobada del mes (o calculada, sin aprobar). Ejec.: valorizado con corte en el mes.") },
            { key: "month_cost", label: _t("Costo"), help: _t("Presup.: costo programado del mes. Ejec.: costo contable del mes.") },
            { key: "month_margin", label: _t("Margen"), help: _t("Valorización − costo del mes.") },
        ],
    },
    {
        key: "close",
        label: _t("Al cierre"),
        items: [
            { key: "close_sale", label: _t("Venta"), help: _t("Venta vigente: orden de venta del contrato con los cambios cobrables.") },
            { key: "close_margin_pct", label: _t("Margen %"), pct: true, light: "margin", help: _t("Presup.: (venta − costo meta) ÷ venta. Ejec.: (venta − costo final estimado) ÷ venta.") },
        ],
    },
];

export function formatThousands(value) {
    if (value === false || value === null || value === undefined) {
        return "—";
    }
    return formatFloat(value / 1000, { digits: [16, 1] });
}

export function formatPct(value) {
    if (value === false || value === null || value === undefined) {
        return "—";
    }
    return `${formatFloat(value * 100, { digits: [16, 1] })} %`;
}

export function formatIndex(value) {
    if (value === false || value === null || value === undefined) {
        return "—";
    }
    return formatFloat(value, { digits: [16, 2] });
}

export function formatIndicator(item, value) {
    return item.pct ? formatPct(value) : formatThousands(value);
}

/** Color del ejecutado contra lo presupuestado: semáforo del margen o
 *  comparación simple (más es mejor salvo en el costo). */
export function indicatorClass(item, budget, executed, lights = {}) {
    if (item.light && lights[item.light]) {
        return `o_cp_light_${lights[item.light]}`;
    }
    if (typeof budget !== "number" || typeof executed !== "number" || !budget) {
        return "";
    }
    const worse = item.key.endsWith("cost") ? executed > budget : executed < budget;
    return worse ? "o_cp_light_amber" : "o_cp_light_green";
}

export class ConstructionIndicatorBlocks extends Component {
    static template = "al_construction_planner.IndicatorBlocks";
    static props = {
        budget: Object,
        executed: Object,
        lights: { type: Object, optional: true },
        monthLabel: { type: String, optional: true },
        monthTitle: { type: String, optional: true },
        extraClose: { type: Array, optional: true },
    };

    get blocks() {
        return INDICATOR_BLOCKS;
    }

    blockLabel(block) {
        if (block.key === "month" && this.props.monthTitle) {
            return `${block.label} · ${this.props.monthTitle}`;
        }
        return block.label;
    }

    format(item, value) {
        return formatIndicator(item, value);
    }

    cssClass(item) {
        return indicatorClass(
            item,
            this.props.budget[item.key],
            this.props.executed[item.key],
            this.props.lights || {}
        );
    }
}

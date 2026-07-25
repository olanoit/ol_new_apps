import { Component, useState } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";

/**
 * Modal único del comprobante en caja: las 3 opciones (Recibo, Boleta,
 * Factura) y, para boleta/factura, la selección de serie en el mismo
 * modal — con estrella de "serie fija" por caja y tipo (patrón del
 * vendedor predeterminado por sesión).
 *
 * Awaitable vía makeAwaitable: getPayload({type, serieId}) al confirmar;
 * undefined = canceló.
 */
export class DocTypePopup extends Component {
    static template = "al_l10n_pe_edi_pos.DocTypePopup";
    static components = { Dialog };
    static props = {
        title: { type: String, optional: true },
        currentType: { type: String, optional: true },
        currentSerieId: { type: [Number, { value: false }], optional: true },
        currentSend: { type: Boolean, optional: true },
        // {boleta: [{id, name}], factura: [{id, name}]}
        series: { type: Object },
        // {boleta: id|null, factura: id|null} — series fijas actuales
        fixedIds: { type: Object },
        onSetFixed: { type: Function },
        getPayload: Function,
        close: Function,
    };
    static defaultProps = {
        title: "Comprobante",
        currentType: "boleta",
        currentSerieId: false,
        currentSend: true,
    };

    static TYPES = [
        {
            code: "recibo",
            label: "Recibo",
            icon: "fa-print",
            hint: "Ticket simple, sin comprobante electrónico",
        },
        {
            code: "boleta",
            label: "Boleta electrónica",
            icon: "fa-file-text-o",
            hint: "Consumidor final (DNI opcional)",
        },
        {
            code: "factura",
            label: "Factura electrónica",
            icon: "fa-building-o",
            hint: "Requiere cliente con RUC",
        },
    ];

    setup() {
        this.types = this.constructor.TYPES;
        this.state = useState({
            type: this.props.currentType,
            serieId: this.props.currentSerieId || false,
            send: this.props.currentSend,
            fixedIds: { ...this.props.fixedIds },
        });
    }

    get seriesForType() {
        return this.props.series[this.state.type] || [];
    }

    selectType(code) {
        if (this.state.type === code) {
            return;
        }
        this.state.type = code;
        // Serie del tipo nuevo: fija > única > sin selección.
        const series = this.props.series[code] || [];
        const fixed = this.state.fixedIds[code];
        this.state.serieId =
            (fixed && series.some((s) => s.id === fixed) && fixed) ||
            (series.length === 1 ? series[0].id : false);
    }

    selectSerie(serie) {
        this.state.serieId = serie.id;
    }

    toggleFixed(serie, ev) {
        ev.stopPropagation();
        const type = this.state.type;
        const isCurrent = this.state.fixedIds[type] === serie.id;
        this.state.fixedIds[type] = isCurrent ? null : serie.id;
        this.props.onSetFixed(type, isCurrent ? null : serie);
        if (!isCurrent) {
            this.state.serieId = serie.id;
        }
    }

    get canConfirm() {
        if (this.state.type === "recibo") {
            return true;
        }
        // Sin series configuradas se permite confirmar (numera el diario);
        // con series, hay que elegir una.
        return !this.seriesForType.length || Boolean(this.state.serieId);
    }

    confirm() {
        this.props.getPayload({
            type: this.state.type,
            serieId: this.state.type === "recibo" ? false : this.state.serieId,
            send: this.state.type === "recibo" ? true : this.state.send,
        });
        this.props.close();
    }

    cancel() {
        this.props.close();
    }
}

import { Component } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

/**
 * Año como lista desplegable para un campo entero (CTS, gratificación,
 * vacaciones, utilidades, UIT…).
 *
 * Los años se calculan con la fecha de hoy: del próximo año hacia atrás
 * (`years_back`, 6 por defecto), así que la lista avanza sola cada enero sin
 * catálogo ni cron. Un valor guardado fuera del rango se conserva y se
 * muestra. El campo sigue siendo entero: no cambian los datos ni el código
 * que hace `date(record.year, …)`.
 *
 * Uso: <field name="year" widget="year_selection"/>
 *      options="{'years_back': 10, 'years_ahead': 1}"
 */
export class YearSelectionField extends Component {
    static template = "al_hr_pe.YearSelectionField";
    static props = {
        ...standardFieldProps,
        yearsBack: { type: Number, optional: true },
        yearsAhead: { type: Number, optional: true },
        placeholder: { type: String, optional: true },
    };
    static defaultProps = { yearsBack: 6, yearsAhead: 1 };

    get value() {
        return this.props.record.data[this.props.name] || false;
    }

    get isRequired() {
        return this.props.record.fields[this.props.name].required || this.props.required;
    }

    get years() {
        const current = luxon.DateTime.local().year;
        const years = [];
        for (let year = current + this.props.yearsAhead; year >= current - this.props.yearsBack; year--) {
            years.push(year);
        }
        if (this.value && !years.includes(this.value)) {
            years.push(this.value);
            years.sort((a, b) => b - a);
        }
        return years;
    }

    onChange(ev) {
        const raw = ev.target.value;
        this.props.record.update({ [this.props.name]: raw ? parseInt(raw, 10) : false });
    }
}

export const yearSelectionField = {
    component: YearSelectionField,
    displayName: _t("Año (lista)"),
    supportedTypes: ["integer"],
    extractProps: ({ options, placeholder }) => ({
        yearsBack: options.years_back,
        yearsAhead: options.years_ahead,
        placeholder,
    }),
};

registry.category("fields").add("year_selection", yearSelectionField);

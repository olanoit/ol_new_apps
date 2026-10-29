import { _t } from '@web/core/l10n/translation';
import { rpc } from '@web/core/network/rpc';
import { patch } from '@web/core/utils/patch';
import { patchDynamicContent } from '@web/public/utils';
import { CustomerAddress } from '@portal/interactions/address';

// Odoo 20: el RUC va en «vat» y el DNI en el identificador adicional PE_DNI.
const DNI_KEY = 'PE_DNI';
const RUC_REGEX = /^\d{11}$/;
const DNI_REGEX = /^\d{8}$/;

patch(CustomerAddress.prototype, {
    setup() {
        super.setup();
        this.l10nPeEnabled = !!this.el.querySelector('#div_l10n_pe_receipt');
        if (!this.l10nPeEnabled) {
            return;
        }
        patchDynamicContent(this.dynamicContent, {
            'input[name="l10n_pe_receipt"]': { 't-on-change': this.onChangeL10nPeReceipt.bind(this) },
            '.o_l10n_pe_document_lookup': {
                't-on-click.prevent': this.locked(this.l10nPeLookupDocument.bind(this), true),
            },
            'input[name="vat"]': { 't-on-change': this.onChangeL10nPeDocument.bind(this) },
            [`input[name="${DNI_KEY}"]`]: { 't-on-change': this.onChangeL10nPeDocument.bind(this) },
        });
    },

    _l10nPeIsInvoice() {
        return this.el.querySelector('#l10n_pe_receipt_factura')?.checked;
    },

    /**
     * Boleta o factura: la factura se emite al RUC (campo «vat»); la boleta,
     * al DNI, cuyo campo se muestra si aún no está.
     */
    onChangeL10nPeReceipt() {
        if (this._l10nPeIsInvoice()) {
            this.addressForm.vat?.focus();
            return;
        }
        const field = this.el.querySelector(`.o_additional_identifier_field[data-identifier-key="${DNI_KEY}"]`);
        if (field && field.style.display === 'none') {
            this.el.querySelector(`.o_add_identifier_item[data-identifier-key="${DNI_KEY}"]`)?.click();
        }
        this.el.querySelector(`input[name="${DNI_KEY}"]`)?.focus();
    },

    /**
     * Al terminar de escribir un RUC (11 dígitos) o un DNI (8), se consulta
     * solo.
     */
    async onChangeL10nPeDocument() {
        const [, number, regex] = this._l10nPeDocument();
        if (regex.test(number)) {
            await this.l10nPeLookupDocument();
        }
    },

    /**
     * @returns {[string, string, RegExp]} código SUNAT, número y su formato
     */
    _l10nPeDocument() {
        const clean = (value) => (value || '').replace(/[\s.-]/g, '');
        if (this._l10nPeIsInvoice()) {
            return ['6', clean(this.addressForm.vat?.value), RUC_REGEX];
        }
        return ['1', clean(this.el.querySelector(`input[name="${DNI_KEY}"]`)?.value), DNI_REGEX];
    },

    _l10nPeSetMessage(message) {
        const messageEl = this.el.querySelector('.o_l10n_pe_document_lookup_message');
        if (messageEl) {
            messageEl.textContent = message || '';
        }
    },

    /**
     * Consulta el RUC o DNI y llena el nombre y la dirección.
     */
    async l10nPeLookupDocument() {
        const [sunatCode, number, regex] = this._l10nPeDocument();
        if (!regex.test(number)) {
            this._l10nPeSetMessage(sunatCode === '6'
                ? _t('Escriba un RUC de 11 dígitos.')
                : _t('Escriba un DNI de 8 dígitos.'));
            return;
        }
        this._l10nPeSetMessage(_t('Consultando…'));
        const result = await this.waitFor(rpc('/shop/l10n_pe/document_lookup', {
            number,
            sunat_code: sunatCode,
        }));
        if (!result.found) {
            this._l10nPeSetMessage(result.message);
            return;
        }
        await this._l10nPeFillAddress(result.values);
        this._l10nPeSetMessage(_t('Datos completados con la consulta.'));
    },

    /**
     * Escribe los valores de la consulta en el formulario. Departamento,
     * provincia y distrito se cargan en cascada (como al elegirlos a mano).
     *
     * @param {Object} values
     */
    async _l10nPeFillAddress(values) {
        const form = this.addressForm;
        for (const fieldName of ['name', 'street', 'zip']) {
            if (values[fieldName] && form[fieldName]) {
                form[fieldName].value = values[fieldName];
            }
        }
        if (values.country_id && form.country_id && form.country_id.value !== String(values.country_id)) {
            form.country_id.value = values.country_id;
            await this.waitFor(this.onChangeCountry());
        }
        if (values.state_id && form.state_id) {
            form.state_id.value = values.state_id;
            await this.waitFor(this.onChangeState());
        }
        if (values.city_id && form.city_id) {
            form.city_id.value = values.city_id;
            await this.waitFor(this.onChangeCity());
        }
        if (values.l10n_pe_district && form.l10n_pe_district) {
            form.l10n_pe_district.value = values.l10n_pe_district;
        }
    },
});

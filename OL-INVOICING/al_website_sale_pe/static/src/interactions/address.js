import { _t } from '@web/core/l10n/translation';
import { rpc } from '@web/core/network/rpc';
import { patch } from '@web/core/utils/patch';
import { patchDynamicContent } from '@web/public/utils';
import { CustomerAddress } from '@portal/interactions/address';

const DOCUMENT_REGEX = /^(\d{8}|\d{11})$/;

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
            'input[name="vat"]': { 't-on-change': this.onChangeL10nPeVat.bind(this) },
        });
    },

    /**
     * Boleta o factura: el tipo de documento sigue al comprobante (factura →
     * RUC; boleta → DNI, salvo que ya haya elegido otro documento).
     */
    onChangeL10nPeReceipt(ev) {
        const select = this.addressForm.l10n_latam_identification_type_id;
        if (!select || select.tagName !== 'SELECT') {
            return;
        }
        const typeId = ev.currentTarget.dataset.identificationTypeId;
        const rucId = this.el.querySelector('#l10n_pe_receipt_factura').dataset.identificationTypeId;
        if (ev.currentTarget.value === 'factura' || select.value === rucId) {
            select.value = typeId;
        }
    },

    /**
     * Al terminar de escribir un RUC (11 dígitos) o un DNI (8), se consulta
     * solo.
     */
    async onChangeL10nPeVat() {
        if (DOCUMENT_REGEX.test(this._l10nPeDocumentNumber())) {
            await this.l10nPeLookupDocument();
        }
    },

    _l10nPeDocumentNumber() {
        return (this.addressForm.vat?.value || '').replace(/[\s.-]/g, '');
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
        const number = this._l10nPeDocumentNumber();
        const typeSelect = this.addressForm.l10n_latam_identification_type_id;
        if (!DOCUMENT_REGEX.test(number) || !typeSelect?.value) {
            this._l10nPeSetMessage(_t('Escriba un RUC (11 dígitos) o un DNI (8 dígitos).'));
            return;
        }
        this._l10nPeSetMessage(_t('Consultando…'));
        const result = await this.waitFor(rpc('/shop/l10n_pe/document_lookup', {
            number,
            identification_type_id: parseInt(typeSelect.value),
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
            await this.waitFor(this._onChangeCountry());
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

/* global KR */

import { loadCSS, loadJS } from '@web/core/assets';
import { _t } from '@web/core/l10n/translation';
import { rpc, RPCError } from '@web/core/network/rpc';
import { patch } from '@web/core/utils/patch';

import { PaymentForm } from '@payment/interactions/payment_form';

// Cliente JavaScript de Izipay (krypton-client V4.0) y su tema «neon».
const KRYPTON_PATH = '/static/js/krypton-client/V4.0';
const KR_CONTAINER_ID = 'o_izipay_container';

/**
 * Carga el cliente de Izipay en «modo SPA» (sin formulario hasta que se le
 * pasa un formToken), como hace su librería oficial embedded-form-glue: el
 * script necesita atributos propios, por eso no se usa loadJS.
 *
 * @param {string} staticUrl
 * @param {string} publicKey
 * @return {Promise<void>}
 */
async function loadIzipayClient(staticUrl, publicKey) {
    if (!window.KR && !document.querySelector('script[data-izipay-client]')) {
        await loadCSS(`${staticUrl}${KRYPTON_PATH}/ext/neon-reset.min.css`);
        const script = document.createElement('script');
        script.src = `${staticUrl}${KRYPTON_PATH}/stable/kr-payment-form.min.js`;
        script.setAttribute('kr-public-key', publicKey);
        script.setAttribute('kr-spa-mode', 'true');
        script.setAttribute('kr-language', 'es-PE');
        script.dataset.izipayClient = '1';
        document.body.appendChild(script);
        await loadJS(`${staticUrl}${KRYPTON_PATH}/ext/neon.js`);
    }
    await new Promise((resolve, reject) => {
        const start = Date.now();
        const check = () => {
            if (window.KR && window.KR.ready) {
                resolve();
            } else if (Date.now() - start > 30000) {
                reject(new Error(_t("No se pudo cargar el formulario de Izipay.")));
            } else {
                setTimeout(check, 100);
            }
        };
        check();
    });
}

patch(PaymentForm.prototype, {

    // #=== FLUJO ===#

    /**
     * Izipay usa el flujo «direct»: el formulario se abre en la misma página.
     *
     * @override
     */
    async _prepareInlineForm(providerId, providerCode, paymentOptionId, paymentMethodCode, flow) {
        if (providerCode !== 'izipay') {
            await super._prepareInlineForm(...arguments);
            return;
        }
        if (flow === 'token') {
            return;
        }
        this._setPaymentFlow('direct');
    },

    /**
     * Abre el formulario emergente de Izipay con el formToken creado en el
     * servidor. Al terminar, el servidor consulta el resultado a Izipay.
     *
     * @override
     */
    async _processDirectFlow(providerCode, paymentOptionId, paymentMethodCode, processingValues) {
        if (providerCode !== 'izipay') {
            await super._processDirectFlow(...arguments);
            return;
        }
        try {
            await this.waitFor(loadIzipayClient(
                processingValues.izipay_static_url, processingValues.izipay_public_key
            ));
            await this.waitFor(this._izipayOpenPopin(processingValues));
        } catch (error) {
            this._displayErrorDialog(
                _t("No se pudo procesar el pago"), error.message || error.errorMessage || ''
            );
            this._enableButton();
        }
    },

    /**
     * Prepara el formulario del formToken y lo abre en una ventana emergente.
     *
     * @private
     * @param {object} processingValues
     */
    async _izipayOpenPopin(processingValues) {
        await KR.removeForms();
        if (KR.removeEventCallbacks) {
            KR.removeEventCallbacks('onSubmit');
            KR.removeEventCallbacks('onPopinClosed');
        }
        await KR.setFormConfig({
            formToken: processingValues.izipay_form_token,
            'kr-public-key': processingValues.izipay_public_key,
            'kr-language': 'es-PE',
        });
        let finished = false;
        // Pago aceptado o intentos agotados: Izipay no redirige (return
        // false) y Odoo confirma el resultado en el servidor.
        await KR.onSubmit(() => {
            finished = true;
            KR.closePopin();
            this._izipayFinish(processingValues);
            return false;
        });
        // Si el cliente cierra la ventana sin pagar, puede volver a intentarlo.
        await KR.onPopinClosed(() => {
            if (!finished) {
                this._enableButton();
            }
        });

        let container = document.getElementById(KR_CONTAINER_ID);
        if (!container) {
            container = document.createElement('div');
            container.id = KR_CONTAINER_ID;
            document.body.appendChild(container);
        }
        container.replaceChildren();
        const form = document.createElement('div');
        form.className = 'kr-embedded';
        form.setAttribute('kr-popin', '');
        container.appendChild(form);

        const { result } = await KR.renderElements(form);
        await KR.openPopin(result && result.formId);
    },

    /**
     * El servidor consulta el pedido a Izipay y la página de estado muestra
     * el resultado.
     *
     * @private
     * @param {object} processingValues
     */
    async _izipayFinish(processingValues) {
        try {
            await this.waitFor(rpc('/payment/izipay/return', {
                reference: processingValues.reference,
                partner_id: processingValues.partner_id,
                access_token: processingValues.access_token,
            }));
        } catch (error) {
            if (error instanceof RPCError) {
                this._displayErrorDialog(_t("No se pudo procesar el pago"), error.data.message);
                this._enableButton();
                return;
            }
            return Promise.reject(error);
        }
        window.location = '/payment/status';
    },

});

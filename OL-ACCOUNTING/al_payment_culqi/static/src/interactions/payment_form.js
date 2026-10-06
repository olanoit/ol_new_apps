/* global CulqiCheckout, Culqi3DS */

import { loadJS } from '@web/core/assets';
import { _t } from '@web/core/l10n/translation';
import { rpc, RPCError } from '@web/core/network/rpc';
import { patch } from '@web/core/utils/patch';

import { PaymentForm } from '@payment/interactions/payment_form';

// Culqi Checkout Custom (Checkout v4 está en desuso) y Culqi 3DS v1.
const CULQI_CHECKOUT_URL = 'https://js.culqi.com/checkout-js';
const CULQI_3DS_URL = 'https://3ds.culqi.com';
const CULQI_PAYMENT_METHODS = ['tarjeta', 'yape', 'billetera', 'bancaMovil', 'agente', 'cuotealo'];

patch(PaymentForm.prototype, {

    // #=== FLUJO ===#

    /**
     * Culqi usa el flujo «direct»: el checkout se abre en la misma página.
     *
     * @override
     */
    async _prepareInlineForm(providerId, providerCode, paymentOptionId, paymentMethodCode, flow) {
        if (providerCode !== 'culqi') {
            await super._prepareInlineForm(...arguments);
            return;
        }
        if (flow === 'token') {
            return;
        }
        this._setPaymentFlow('direct');
    },

    /**
     * Abre Culqi Checkout Custom; el token (tarjeta o Yape) se cobra en el
     * servidor.
     *
     * @override
     */
    async _processDirectFlow(providerCode, paymentOptionId, paymentMethodCode, processingValues) {
        if (providerCode !== 'culqi') {
            await super._processDirectFlow(...arguments);
            return;
        }
        await this.waitFor(Promise.all([loadJS(CULQI_CHECKOUT_URL), loadJS(CULQI_3DS_URL)]));

        // Huella del dispositivo para el antifraude de Culqi (opcional: si
        // falla, el cargo sigue sin ella).
        Culqi3DS.publicKey = processingValues.culqi_public_key;
        let deviceId = null;
        try {
            deviceId = await this.waitFor(Culqi3DS.generateDevice());
        } catch {
            deviceId = null;
        }

        const checkout = new CulqiCheckout(
            processingValues.culqi_public_key, this._culqiCheckoutConfig(processingValues)
        );
        checkout.culqi = async () => {
            if (checkout.token) {
                checkout.close();
                await this._culqiCharge(processingValues, checkout.token.id, deviceId);
            } else if (checkout.error) {
                this._displayErrorDialog(
                    _t("No se pudo procesar el pago"),
                    checkout.error.user_message || checkout.error.merchant_message || ''
                );
                this._enableButton();
            }
        };
        checkout.open();
        // Si el cliente cierra el checkout sin pagar, puede volver a intentarlo.
        this._enableButton();
    },

    /**
     * Configuración de Checkout Custom: solo el método elegido en Odoo.
     *
     * @private
     * @param {object} processingValues
     * @return {object}
     */
    _culqiCheckoutConfig(processingValues) {
        const paymentMethods = Object.fromEntries(
            CULQI_PAYMENT_METHODS.map(code => [code, code === processingValues.culqi_payment_method])
        );
        const settings = {
            title: processingValues.culqi_title,
            currency: processingValues.culqi_currency,
            amount: processingValues.culqi_amount,
        };
        if (processingValues.culqi_rsa_id && processingValues.culqi_rsa_public_key) {
            settings.xculqirsaid = processingValues.culqi_rsa_id;
            settings.rsapublickey = processingValues.culqi_rsa_public_key;
        }
        return {
            settings,
            client: { email: processingValues.culqi_email },
            options: {
                lang: 'auto',
                installments: false,
                modal: true,
                paymentMethods,
                paymentMethodsSort: Object.keys(paymentMethods),
            },
            appearance: {},
        };
    },

    // #=== CARGO Y 3DS ===#

    /**
     * Pide al servidor el cargo. Si Culqi exige 3DS, autentica al cliente y
     * repite el cargo con los parámetros obtenidos.
     *
     * @private
     */
    async _culqiCharge(processingValues, tokenId, deviceId, authentication3ds = null) {
        let result;
        try {
            result = await this.waitFor(rpc('/payment/culqi/charge', {
                reference: processingValues.reference,
                partner_id: processingValues.partner_id,
                access_token: processingValues.access_token,
                source_id: tokenId,
                device_id: deviceId,
                authentication_3ds: authentication3ds,
            }));
        } catch (error) {
            if (error instanceof RPCError) {
                this._displayErrorDialog(_t("No se pudo procesar el pago"), error.data.message);
                this._enableButton();
                return;
            }
            return Promise.reject(error);
        }
        if (result.action === 'review' && !authentication3ds) {
            this._culqiAuthenticate3ds(processingValues, tokenId, deviceId);
            return;
        }
        // Estado final (hecho o rechazado): la página de estado lo muestra.
        window.location = '/payment/status';
    },

    /**
     * Autenticación 3DS con Culqi3DS: el resultado llega por postMessage.
     *
     * @private
     */
    _culqiAuthenticate3ds(processingValues, tokenId, deviceId) {
        if (!processingValues.culqi_3ds_allowed) {
            this._displayErrorDialog(
                _t("No se pudo procesar el pago"),
                _t("El banco exige la autenticación 3D Secure, que Culqi no admite para este monto.")
            );
            this._enableButton();
            return;
        }
        Culqi3DS.settings = {
            charge: {
                totalAmount: processingValues.culqi_amount,
                returnUrl: window.location.href,
                currency: processingValues.culqi_currency,
            },
            card: { email: processingValues.culqi_email },
        };
        Culqi3DS.options = {
            showModal: true,
            showLoading: true,
            showIcon: true,
            closeModalAction: () => this._enableButton(),
        };
        const listener = async event => {
            if (event.origin !== window.location.origin || !event.data) {
                return;
            }
            const response = event.data;
            if (response.parameters3DS) {
                window.removeEventListener('message', listener);
                Culqi3DS.reset();
                await this._culqiCharge(processingValues, tokenId, deviceId, response.parameters3DS);
            } else if (response.error) {
                window.removeEventListener('message', listener);
                Culqi3DS.reset();
                this._displayErrorDialog(_t("No se pudo procesar el pago"), response.error);
                this._enableButton();
            }
        };
        window.addEventListener('message', listener, false);
        Culqi3DS.initAuthentication(tokenId);
    },

});

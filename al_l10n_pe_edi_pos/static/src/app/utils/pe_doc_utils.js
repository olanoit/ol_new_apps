/**
 * Utilidades compartidas del flujo CPE en el TPV. La misma regla de RUC
 * se usa al elegir el tipo de comprobante y al validar el pago, para que
 * el error nunca llegue al backend (_prepare_invoice_vals queda como
 * red de seguridad).
 */
export function isValidPeRuc(vat) {
    const clean = (vat || "").trim();
    return clean.length === 11 && /^\d+$/.test(clean);
}

/** El cliente sirve para emitir factura: existe y tiene RUC válido. */
export function partnerCanInvoice(partner) {
    return Boolean(partner) && isValidPeRuc(partner.vat);
}

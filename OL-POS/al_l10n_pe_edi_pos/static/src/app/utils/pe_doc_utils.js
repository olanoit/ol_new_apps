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

/**
 * El cliente sirve para emitir factura: existe, su documento es RUC (código
 * SUNAT 6) y el número es válido. Un número de 11 dígitos con otro tipo
 * (p. ej. «VAT», código 0) daba una factura que SUNAT rechaza (2800).
 */
export function partnerCanInvoice(partner) {
    return (
        Boolean(partner) &&
        partner.l10n_latam_identification_type_id?.l10n_pe_vat_code === "6" &&
        isValidPeRuc(partner.vat)
    );
}

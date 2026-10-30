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
        // Odoo 20: el RUC va en vat y su código SUNAT en l10n_pe_sunat_id_code.
        partner.l10n_pe_sunat_id_code === "6" &&
        isValidPeRuc(partner.vat)
    );
}

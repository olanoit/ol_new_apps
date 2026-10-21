from odoo import fields, models, tools
from odoo.tools import SQL

# Tributos que forman el débito y el crédito fiscal (catálogo 5 de SUNAT).
IGV_CODES = ('1000', '1016')


class L10nPeDashboardTax(models.Model):
    """Ventas y compras con su IGV, en soles y con signo de negocio.

    Una fila por comprobante publicado: las ventas y las compras suman en
    positivo y las notas de crédito restan, para que el tablero y la tabla
    dinámica no tengan que invertir signos. El IGV sale de los apuntes de
    impuesto con código 1000 (IGV) o 1016 (IVAP).
    """
    _name = 'l10n_pe.dashboard.tax'
    _description = 'Ventas, compras e IGV'
    _auto = False
    _order = 'date desc, id desc'

    move_id = fields.Many2one('account.move', string='Comprobante', readonly=True)
    company_id = fields.Many2one('res.company', string='Compañía', readonly=True)
    currency_id = fields.Many2one('res.currency', string='Moneda', readonly=True)
    date = fields.Date(string='Fecha contable', readonly=True)
    invoice_date = fields.Date(string='Fecha de emisión', readonly=True)
    partner_id = fields.Many2one('res.partner', string='Cliente o proveedor', readonly=True)
    journal_id = fields.Many2one('account.journal', string='Diario', readonly=True)
    document_type_id = fields.Many2one('l10n_latam.document.type', string='Tipo de comprobante', readonly=True)
    kind = fields.Selection([('sale', 'Ventas'), ('purchase', 'Compras')], string='Operación', readonly=True)
    move_type = fields.Selection(related='move_id.move_type', string='Tipo')
    base = fields.Monetary(string='Base imponible', readonly=True)
    igv = fields.Monetary(string='IGV', readonly=True)
    total = fields.Monetary(string='Total', readonly=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute(SQL("""
            CREATE OR REPLACE VIEW %(table)s AS (
                SELECT m.id, m.id AS move_id, m.company_id, c.currency_id, m.date, m.invoice_date,
                       m.commercial_partner_id AS partner_id, m.journal_id,
                       m.l10n_latam_document_type_id AS document_type_id,
                       CASE WHEN m.move_type IN ('out_invoice', 'out_refund') THEN 'sale' ELSE 'purchase' END
                           AS kind,
                       sign.value * m.amount_untaxed_signed AS base,
                       sign.value * m.amount_total_signed AS total,
                       COALESCE(igv.amount, 0.0) AS igv
                  FROM account_move m
                  JOIN res_company c ON c.id = m.company_id
                 CROSS JOIN LATERAL (
                       SELECT CASE WHEN m.move_type IN ('out_invoice', 'out_refund') THEN 1 ELSE -1 END AS value
                 ) sign
                  LEFT JOIN LATERAL (
                       SELECT SUM(-sign.value * aml.balance) AS amount
                         FROM account_move_line aml
                         JOIN account_tax t ON t.id = aml.tax_line_id
                        WHERE aml.move_id = m.id
                          AND t.l10n_pe_edi_tax_code IN %(codes)s
                 ) igv ON TRUE
                 WHERE m.state = 'posted'
                   AND m.move_type IN ('out_invoice', 'out_refund', 'in_invoice', 'in_refund')
            )
        """, table=SQL.identifier(self._table), codes=IGV_CODES))

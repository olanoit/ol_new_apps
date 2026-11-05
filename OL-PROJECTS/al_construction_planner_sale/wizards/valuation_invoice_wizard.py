# -*- coding: utf-8 -*-
"""Vista previa de la factura de la valorización (paquete 1.17, M117-25)."""
from markupsafe import Markup

from odoo import fields, models
from odoo.exceptions import UserError
from odoo.tools.misc import formatLang


class ConstructionValuationInvoiceWizard(models.TransientModel):
    _name = 'construction.valuation.invoice.wizard'
    _description = 'Vista previa de la factura de la valorización'

    valuation_id = fields.Many2one('construction.valuation', required=True, ondelete='cascade')
    preview_html = fields.Html(string='Factura', compute='_compute_preview', sanitize=False)
    missing = fields.Char(string='Lo que falta', compute='_compute_preview')

    def _compute_preview(self):
        for wizard in self:
            valuation = wizard.valuation_id
            wizard.missing = False
            try:
                lines, _delivered = valuation._prepare_invoice_lines(
                    fields.Date.context_today(self))
            except UserError as error:
                wizard.missing = error.args[0]
                wizard.preview_html = False
                continue
            rows = Markup('').join(
                Markup('<tr><td>%s</td><td class="text-end">%s</td><td class="text-end">%s</td></tr>')
                % (line.get('name'), formatLang(self.env, line.get('quantity') or 0.0),
                   formatLang(self.env, line.get('price_unit') or 0.0)) for line in lines)
            wizard.preview_html = Markup(
                '<table class="table table-sm o_main_table"><thead><tr><th>%s</th>'
                '<th class="text-end">%s</th><th class="text-end">%s</th></tr></thead>'
                '<tbody>%s</tbody></table><p class="text-muted">%s</p>') % (
                self.env._('Línea'), self.env._('Cantidad'), self.env._('Precio'), rows,
                self.env._('La factura lleva adjunto el anexo de la valorización.'))

    def action_create(self):
        self.ensure_one()
        return self.valuation_id.action_create_invoice()

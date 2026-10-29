from odoo import _, api, fields, models


class ProductValue(models.Model):
    _inherit = 'product.value'

    @api.model_create_multi
    def create(self, vals_list):
        # Un ajuste de valor (Inventario ▸ Ajustar valorización) cambia el
        # costo del periodo del movimiento o de su fecha: el cierre mensual lo
        # bloquea.
        for vals in vals_list:
            move = self.env['stock.move'].browse(vals.get('move_id'))
            company = move.company_id or self.env['res.company'].browse(vals.get('company_id')) or self.env.company
            moment = move.date if move else fields.Datetime.to_datetime(vals.get('date')) or fields.Datetime.now()
            company._l10n_pe_check_stock_lock(moment, _('Ajuste de valorización'))
        return super().create(vals_list)

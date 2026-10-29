from datetime import datetime, time

import pytz

from odoo import _, fields, models
from odoo.exceptions import UserError

PE_TZ = pytz.timezone('America/Lima')


class L10nPeWhCostRecomputeWizard(models.TransientModel):
    """Revalorizar el kardex desde una fecha.

    Para cuando cambia el valor de movimientos ya hechos (factura de compra
    tardía, costo en destino, costo de producción corregido): rehace el costo
    por almacén desde esa fecha. Solo dentro del periodo abierto.
    """
    _name = 'l10n_pe.wh.cost.recompute.wizard'
    _description = 'Revalorizar costo por almacén'

    company_id = fields.Many2one(
        'res.company', string='Compañía', required=True, default=lambda self: self.env.company)
    date_from = fields.Date(string='Desde', required=True)
    lock_date = fields.Date(related='company_id.l10n_pe_stock_lock_date')

    def action_recompute(self):
        self.ensure_one()
        company = self.company_id
        if not company.l10n_pe_wh_cost:
            raise UserError(_('Active «Costo promedio por almacén» en los ajustes de Inventario.'))
        start = PE_TZ.localize(datetime.combine(self.date_from, time.min)).astimezone(pytz.utc).replace(tzinfo=None)
        company._l10n_pe_check_stock_lock(start, _('Revalorizar'))
        # Lo que ya estaba pendiente desde antes también se rehace.
        if company.l10n_pe_wh_cost_dirty_date and company.l10n_pe_wh_cost_dirty_date < start:
            start = company.l10n_pe_wh_cost_dirty_date
        company._l10n_pe_wh_cost_mark_dirty(start)
        company._l10n_pe_wh_cost_refresh()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'success',
                'message': _('Costo por almacén recalculado desde el %s.', fields.Date.to_string(self.date_from)),
                'next': {'type': 'ir.actions.act_window_close'},
            },
        }

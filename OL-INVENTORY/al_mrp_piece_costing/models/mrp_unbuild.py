# -*- coding: utf-8 -*-
from odoo import models
from odoo.exceptions import UserError


class MrpUnbuild(models.Model):
    _inherit = 'mrp.unbuild'

    def action_validate(self):
        # El desarme estándar no reconstruye el costo por pieza.
        costed = self.filtered(lambda u: u.mo_id.piece_costing)
        if costed:
            raise UserError(self.env._(
                'La orden %s se costeó por medida y no se puede desarmar: el desarme no '
                'reconstruye el costo de cada pieza. Corrija con un ajuste de inventario y su '
                'asiento, como se acordó con Contabilidad.', costed[0].mo_id.display_name))
        return super().action_validate()

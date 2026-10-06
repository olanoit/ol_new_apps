# -*- coding: utf-8 -*-
from odoo import models


class AccountMove(models.Model):
    _inherit = 'account.move'

    def _check_document_type_discount(self):
        # Odoo impide publicar notas de crédito y débito con descuento de
        # línea y obliga a rehacer las líneas. Con este módulo el XML de la
        # nota informa el precio neto de cada ítem (valor ÷ cantidad), como
        # exige SUNAT (regla 3271), así que el descuento ya no es un problema.
        return

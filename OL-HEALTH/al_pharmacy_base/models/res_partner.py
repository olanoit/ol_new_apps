# -*- coding: utf-8 -*-
from odoo import models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    def _pharmacy_identification_number(self):
        """Documento de identidad del contacto (DNI, RUC, CE…). Odoo 20 guarda
        el RUC en ``vat`` y los demás documentos en ``additional_identifiers``:
        se toma el identificador preferido del contacto."""
        self.ensure_one()
        return self._get_preferred_legal_entity_identifier_vals().get('value') or self.vat or ''

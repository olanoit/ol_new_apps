# -*- coding: utf-8 -*-
import unicodedata

from odoo import models

# Catálogo 03 de SUNAT (UN/ECE Rec. 20) para los nombres de presentación más
# comunes. Lo que no está aquí (blíster, tira…) toma el código de la unidad
# del producto: «1 Blíster x 7» sale como 1 NIU con su descripción.
PRESENTATION_UNIT_CODES = {
    'caja': 'BX',
    'frasco': 'BO',
    'botella': 'BO',
    'bolsa': 'BG',
    'paquete': 'PK',
    'kit': 'KT',
}


def _normalize(text):
    text = unicodedata.normalize('NFKD', text or '').encode('ascii', 'ignore').decode()
    return text.strip().lower()


class PharmacyPresentation(models.Model):
    _inherit = 'pharmacy.presentation'

    def _prepare_uom_values(self, base_uom):
        values = super()._prepare_uom_values(base_uom)
        code = PRESENTATION_UNIT_CODES.get(_normalize(self.name))
        values['l10n_pe_edi_measure_unit_code'] = code or base_uom.l10n_pe_edi_measure_unit_code
        return values

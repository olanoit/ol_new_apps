# -*- coding: utf-8 -*-
from odoo import fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    l10n_pe_perception_excluded = fields.Boolean(
        string='Exceptuado de la percepción',
        help='Figura en el «Listado de entidades que podrán ser exceptuadas de la percepción '
             'del IGV» (sector público, fundaciones, entidades de auxilio mutuo, comunidades, '
             'ENIEX, ONGD…): con un comprobante que da crédito fiscal no se le percibe '
             '(art. 6 de la R.S. 058-2006/SUNAT). Para combustibles: consumidor directo con '
             'registro habilitado en la Dirección General de Hidrocarburos.')

    def _apply_api_result(self, doc_type, vals, extra):
        """La ficha RUC de SUNAT lista los padrones del contribuyente: si figura
        en el de agentes de percepción, se marca (no hay un padrón descargable
        como el de agentes de retención)."""
        result = super()._apply_api_result(doc_type, vals, extra)
        padrones = (self.l10n_pe_padrones or '') if 'l10n_pe_padrones' in self._fields else ''
        if doc_type == 'ruc' and 'AGENTES DE PERCEPCI' in padrones.upper() \
                and not self.l10n_pe_is_perception_agent:
            self.l10n_pe_is_perception_agent = True
        return result

    def _l10n_pe_perception_is_natural_person(self):
        """Persona natural: sin RUC (DNI u otro documento) o con RUC de persona
        natural (10, 15 o 17)."""
        self.ensure_one()
        partner = self.commercial_partner_id
        doc_code = partner.l10n_latam_identification_type_id.l10n_pe_vat_code
        vat = (partner.vat or '').strip()
        if doc_code == '6' or (not doc_code and len(vat) == 11):
            return vat[:2] in ('10', '15', '17')
        return True

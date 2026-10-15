# -*- coding: utf-8 -*-
import re

from odoo import _, api, models
from odoo.exceptions import UserError

REGEX_DNI = re.compile(r'^\d{8}$')
REGEX_RUC = re.compile(r'^\d{11}$')


class ResPartner(models.Model):
    _inherit = 'res.partner'

    @api.model
    def l10n_pe_pos_create_from_document(self, number):
        """Cliente del TPV desde su RUC o DNI: si ya existe lo devuelve; si
        no, lo consulta en SUNAT/RENIEC y lo crea.

        :param str number: RUC (11 dígitos) o DNI (8 dígitos).
        :return: id del cliente.
        :raise UserError: si el número no tiene formato de RUC ni de DNI, o
            ninguna conexión devolvió datos.
        """
        self.check_access('create')
        number = re.sub(r'\D', '', number or '')
        if REGEX_RUC.match(number):
            identification_type = self.env.ref('l10n_pe.it_RUC')
        elif REGEX_DNI.match(number):
            identification_type = self.env.ref('l10n_pe.it_DNI')
        else:
            raise UserError(_('Escriba un RUC (11 dígitos) o un DNI (8 dígitos).'))

        existing = self.search([('vat', '=', number)], limit=1)
        if existing:
            return existing.id

        # Sin token no hay consulta: se dice qué falta en vez de «no se
        # encontraron datos».
        company = self.env.company
        doc_type = 'ruc' if len(number) == 11 else 'dni'
        if not company._l10n_pe_lookup_ready(doc_type):
            raise UserError(company._l10n_pe_lookup_not_ready_message(doc_type))
        values = self._l10n_pe_lookup_document(number, identification_type)
        if not values:
            raise UserError(_(
                'No se encontraron datos del %(type)s %(number)s. Revise el número o cree el '
                'cliente a mano.', type=identification_type.name, number=number))
        partner = self.create({
            **values,
            'vat': number,
            'l10n_latam_identification_type_id': identification_type.id,
        })
        return partner.id

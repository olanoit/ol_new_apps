# -*- coding: utf-8 -*-
import re

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class AccountJournal(models.Model):
    _inherit = 'account.journal'

    l10n_pe_lce_journal = fields.Boolean(
        string='Liquidaciones de compra electrónicas',
        help='Diario de compras en el que la compañía emite liquidaciones de compra (tipo 04) '
             'a personas naturales sin RUC, con numeración propia y envío a SUNAT.')
    l10n_pe_lce_serie = fields.Char(
        string='Serie de la liquidación de compra', size=4, default='L001',
        help='Cuatro caracteres que empiezan con «L» (anexo 27 de la R.S. 097-2012/SUNAT), '
             'p. ej. L001. El correlativo empieza en 1.')

    @api.constrains('l10n_pe_lce_journal', 'l10n_pe_lce_serie', 'type', 'l10n_latam_use_documents')
    def _check_l10n_pe_lce_journal(self):
        for journal in self.filtered('l10n_pe_lce_journal'):
            if journal.type != 'purchase' or not journal.l10n_latam_use_documents:
                raise ValidationError(self.env._(
                    'El diario de liquidaciones de compra debe ser de compras y usar documentos.'))
            if not re.fullmatch(r'L[A-Z0-9]{3}', journal.l10n_pe_lce_serie or ''):
                raise ValidationError(self.env._(
                    'La serie de la liquidación de compra debe tener cuatro caracteres y empezar '
                    'con «L» (p. ej. L001).'))

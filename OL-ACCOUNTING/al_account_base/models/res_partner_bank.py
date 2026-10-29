# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ResPartnerBank(models.Model):
    _inherit = 'res.partner.bank'

    # Sin ``size``: truncar convertiría un código erróneo en uno válido —
    # «123» pasaría a «12», que es otro banco— y el libro saldría mal sin que
    # nadie lo advierta. Mejor rechazarlo.
    # Odoo 20 retiró res.bank (bank_id): el banco de la cuenta, del catálogo.
    l10n_pe_bank_id = fields.Many2one(
        'l10n_pe.bank', string='Banco (catálogo)', index='btree_not_null',
        help='Banco de la cuenta, para lo que depende de él: formato de pago '
             'masivo, plantillas de cobranza y de cheques, tesorería.')
    l10n_pe_bank_code = fields.Char(
        string='Código SUNAT del banco',
        help='Código de la entidad financiera donde está la cuenta, según la '
             'tabla 3 del Anexo 2 del PLE. Es obligatorio en el Libro Caja y '
             'Bancos, formato 1.2.')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            self._l10n_pe_bank_fill(vals)
        return super().create(vals_list)

    def write(self, vals):
        self._l10n_pe_bank_fill(vals)
        return super().write(vals)

    def _l10n_pe_bank_fill(self, vals):
        """El nombre y el BIC del banco de la cuenta salen del catálogo si no
        vienen escritos."""
        if vals.get('l10n_pe_bank_id'):
            bank = self.env['l10n_pe.bank'].browse(vals['l10n_pe_bank_id'])
            vals.setdefault('bank_name', bank.name)
            if bank.bic:
                vals.setdefault('bank_bic', bank.bic)

    @api.model
    def _l10n_pe_national_bank_vals(self):
        """Valores de una cuenta del Banco de la Nación (detracciones), tal
        como la reconoce l10n_pe_edi: BIC BANCPEPL y código de entidad 18."""
        bank = self.env.ref('al_account_base.bank_nacion', raise_if_not_found=False)
        return {
            'l10n_pe_bank_id': bank.id if bank else False,
            'bank_name': 'Banco de la Nación',
            'bank_bic': 'BANCPEPL',
            'country_id': self.env.ref('base.pe').id,
            'clearing_number': '18',
        }

    def _l10n_pe_is_national_bank(self):
        self.ensure_one()
        return self.bank_bic == 'BANCPEPL'

    @api.onchange('l10n_pe_bank_id')
    def _onchange_l10n_pe_bank_id(self):
        for account in self.filtered('l10n_pe_bank_id'):
            account.bank_name = account.l10n_pe_bank_id.name
            account.bank_bic = account.bank_bic or account.l10n_pe_bank_id.bic

    @api.constrains('l10n_pe_bank_code')
    def _check_l10n_pe_bank_code(self):
        for account in self:
            code = (account.l10n_pe_bank_code or '').strip()
            if code and not (code.isdigit() and len(code) == 2):
                raise ValidationError(_(
                    'El código SUNAT del banco debe tener dos dígitos '
                    '(tabla 3 del PLE); se recibió «%s».', code))

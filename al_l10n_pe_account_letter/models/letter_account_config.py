# -*- coding: utf-8 -*-

from odoo import models, fields


class L10nPeLetterAccountConfig(models.Model):
    _name = 'l10n_pe.letter.account.config'
    _description = 'Configuración de cuentas de letras'

    account_type = fields.Selection(
        [('asset_receivable', 'Por cobrar'),
         ('liability_payable', 'Por pagar')],
        string='Tipo de cuenta',
        required=True
    )
    document_type = fields.Selection(
        [('letter', 'Letra')],
        default='letter',
        string='Tipo de documento',
        required=True
    )
    letter_type = fields.Selection(
        selection=[
            ('portfolio', 'En cartera'),
            ('billing', 'Cobranza libre'),
            ('discount', 'Descuento'),
            ('protested', 'Protestada'),
        ],
        string='Tipo de letra',
        default='portfolio',
    )
    group_id = fields.Many2one(
        'account.group',
        string='Grupo')
    account_id = fields.Many2one(
        'account.account',
        string='Cuenta',
        domain="[('account_type', '=', account_type), ('company_ids', 'in', company_id)]"
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Moneda',
    )
    company_id = fields.Many2one(
        'res.company',
        string='Compañía',
        required=True,
        default=lambda self: self.env.company,
    )

    # Traducciones (diccionarios a nivel de clase, no son campos Odoo)
    account_type_t = {
        'asset_receivable': 'Por cobrar',
        'liability_payable': 'Por pagar',
    }
    letter_type_t = {
        'portfolio': 'En cartera',
        'billing': 'Cobranza libre',
        'discount': 'Descuento',
        'protested': 'Protestada',
    }

    _unique_combination = models.Constraint(
        'unique(account_type, letter_type, currency_id, company_id)',
        'Ya existe una configuración de cuenta para esta combinación de '
        'tipo de cuenta, tipo de letra, moneda y compañía.',
    )

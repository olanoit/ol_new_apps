# -*- coding: utf-8 -*-

from odoo import api, models, fields


class L10nPeLetterAccountConfig(models.Model):
    _name = 'l10n_pe.letter.account.config'
    _description = 'Configuración de cuentas de letras'
    _check_company_auto = True

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
        check_company=True,
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

    #: Cuentas del PCGE que trae el plan contable peruano de Odoo (l10n_pe):
    #: 1232 Letras por cobrar - En cartera, 1233 - En cobranza, 1234 - En
    #: descuento y 423 Letras por pagar.
    PCGE_DEFAULTS = [
        ('asset_receivable', 'portfolio', 'chart1232'),
        ('asset_receivable', 'billing', 'chart1233'),
        ('asset_receivable', 'discount', 'chart1234'),
        ('liability_payable', 'portfolio', 'chart423'),
    ]

    @api.model
    def _l10n_pe_create_default_configs(self, companies=None):
        """Configuración de cuentas con el PCGE para las compañías peruanas.

        Solo crea las combinaciones que faltan (por moneda de la compañía y
        dólares): nunca toca una configuración existente.
        """
        companies = companies or self.env['res.company'].search([])
        usd = self.env.ref('base.USD', raise_if_not_found=False)
        created = self.browse()
        for company in companies.filtered(lambda c: c.country_code == 'PE'):
            currencies = company.currency_id | (usd if usd and usd.active else usd.browse())
            for account_type, letter_type, xmlid in self.PCGE_DEFAULTS:
                account = self.env.ref('account.%s_%s' % (company.id, xmlid), raise_if_not_found=False)
                if not account:
                    continue
                for currency in currencies:
                    exists = self.search_count([
                        ('account_type', '=', account_type), ('letter_type', '=', letter_type),
                        ('currency_id', '=', currency.id), ('company_id', '=', company.id)], limit=1)
                    if not exists:
                        created |= self.create({
                            'account_type': account_type, 'letter_type': letter_type,
                            'currency_id': currency.id, 'account_id': account.id,
                            'company_id': company.id,
                        })
        return created


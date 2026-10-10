# -*- coding: utf-8 -*-
from odoo import api, fields, models

#: Modalidades del factoring (NIIF 9): sin recurso el factor asume el riesgo y
#: la cuenta por cobrar se da de baja; con recurso el riesgo sigue en la
#: empresa y el adelanto es una obligación financiera.
MODALITIES = [
    ('without_recourse', 'Sin recurso'),
    ('with_recourse', 'Con recurso'),
]


class L10nPeFactoringAccountConfig(models.Model):
    _name = 'l10n_pe.factoring.account.config'
    _description = 'Cuentas del factoring'
    _check_company_auto = True
    _order = 'company_id, modality, currency_id'

    modality = fields.Selection(MODALITIES, string='Modalidad', required=True)
    currency_id = fields.Many2one(
        'res.currency', string='Moneda',
        help='Vacía: se usa para cualquier moneda sin configuración propia.')
    company_id = fields.Many2one(
        'res.company', string='Compañía', required=True, readonly=True,
        default=lambda self: self.env.company)
    assigned_account_id = fields.Many2one(
        'account.account', string='Facturas cedidas', required=True, check_company=True,
        domain="[('account_type', '=', 'asset_receivable'), ('reconcile', '=', True)]",
        help='Recibe las facturas cedidas (PCGE 1214). Sin recurso, la deuda pasa al '
             'factor; con recurso sigue a nombre del cliente.')
    obligation_account_id = fields.Many2one(
        'account.account', string='Obligación con el factor', check_company=True,
        help='Con recurso: el adelanto recibido es una obligación financiera (PCGE 45).')
    interest_account_id = fields.Many2one(
        'account.account', string='Intereses', required=True, check_company=True,
        help='Gasto financiero del descuento (PCGE 6734).')
    deferred_interest_account_id = fields.Many2one(
        'account.account', string='Intereses diferidos', check_company=True,
        help='Con recurso: los intereses cobrados por adelantado se devengan desde esta '
             'cuenta (PCGE 3731). Vacía: van directo a gasto en el desembolso.')
    fee_account_id = fields.Many2one(
        'account.account', string='Comisiones y gastos', required=True, check_company=True,
        help='Comisión del factor y gastos de la operación (PCGE 6391).')
    loss_account_id = fields.Many2one(
        'account.account', string='Pérdida del retenido', check_company=True,
        help='Sin recurso: retenido que el factor no libera porque el cliente no pagó '
             '(PCGE 6741, Gastos en operaciones de factoring – Gastos por menor valor).')

    _unique_combination = models.Constraint(
        'unique(modality, currency_id, company_id)',
        'Ya hay cuentas de factoring para esa modalidad, moneda y compañía.')

    #: Cuentas del PCGE que trae el plan contable peruano de Odoo (l10n_pe).
    PCGE_DEFAULTS = {
        'assigned_account_id': 'chart1214',
        'interest_account_id': 'chart6734',
        'fee_account_id': 'chart6391',
    }
    PCGE_WITHOUT_RECOURSE = {
        'loss_account_id': 'chart6741',
    }
    PCGE_WITH_RECOURSE = {
        'obligation_account_id': 'chart4512',
        'deferred_interest_account_id': 'chart3731',
    }

    @api.model
    def _l10n_pe_create_default_configs(self, companies=None):
        """Cuentas por defecto (PCGE) para las compañías peruanas que no las
        tienen; nunca toca una configuración existente."""
        companies = companies or self.env['res.company'].search([])
        created = self.browse()
        for company in companies.filtered(lambda c: c.country_code == 'PE'):
            for modality, _label in MODALITIES:
                if self.search_count([('modality', '=', modality), ('currency_id', '=', False),
                                      ('company_id', '=', company.id)], limit=1):
                    continue
                xmlids = dict(self.PCGE_DEFAULTS)
                xmlids.update(self.PCGE_WITH_RECOURSE if modality == 'with_recourse'
                              else self.PCGE_WITHOUT_RECOURSE)
                vals = {'modality': modality, 'company_id': company.id}
                for field, xmlid in xmlids.items():
                    account = self.env.ref('account.%s_%s' % (company.id, xmlid), raise_if_not_found=False)
                    if account:
                        vals[field] = account.id
                if all(vals.get(f) for f in ('assigned_account_id', 'interest_account_id', 'fee_account_id')):
                    created |= self.create(vals)
        return created

    @api.model
    def _l10n_pe_fill_loss_account(self):
        """Versión 4: la cuenta de pérdida del retenido en las configuraciones
        sin recurso que no la tienen."""
        for config in self.search([('modality', '=', 'without_recourse'), ('loss_account_id', '=', False)]):
            account = self.env.ref('account.%s_chart6741' % config.company_id.id, raise_if_not_found=False)
            if account:
                config.loss_account_id = account

    @api.model
    def _l10n_pe_get(self, company, modality, currency):
        """Configuración de la moneda o, si no hay, la general de la modalidad."""
        domain = [('company_id', '=', company.id), ('modality', '=', modality)]
        config = self.search(domain + [('currency_id', '=', currency.id)], limit=1) or \
            self.search(domain + [('currency_id', '=', False)], limit=1)
        if not config:
            config = self._l10n_pe_create_default_configs(company).filtered(
                lambda c: c.modality == modality)[:1]
        return config

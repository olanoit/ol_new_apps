# -*- coding: utf-8 -*-
import re

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.fields import Domain

PREFIXES_RE = re.compile(r'^\s*\d+(\s*,\s*\d+)*\s*$')


class L10nPeMrpCostPool(models.Model):
    """Bolsa de gastos indirectos de fabricación (CIF).

    Su importe del mes es el saldo publicado de las cuentas que empiezan por
    sus prefijos (por ejemplo la 92 del destino de producción, o 63 y 65 con
    el centro de costo de planta); el cierre de costos lo reparte entre las
    órdenes terminadas según su base.
    """
    _name = 'l10n_pe.mrp.cost.pool'
    _description = 'Bolsa de CIF'
    _order = 'sequence, id'
    _check_company_auto = True

    sequence = fields.Integer(default=10)
    name = fields.Char(string='Bolsa', required=True)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        'res.company', string='Compañía', required=True, default=lambda self: self.env.company)
    account_prefixes = fields.Char(
        string='Cuentas', required=True,
        help='Prefijos de código separados por comas, por ejemplo «92» o «63,65».')
    analytic_account_ids = fields.Many2many(
        'account.analytic.account', string='Centros de costo',
        help='Si se indican, solo cuentan los apuntes con alguno de estos centros de costo.')
    split_basis = fields.Selection(
        [('hours', 'Horas de las operaciones'),
         ('quantity', 'Cantidad producida'),
         ('weight', 'Peso producido'),
         ('volume', 'Volumen producido'),
         ('direct_cost', 'Costo directo')],
        string='Base de reparto', required=True, default='hours')
    workcenter_ids = fields.Many2many(
        'mrp.workcenter', string='Centros de producción', check_company=True,
        help='Si se indican, la bolsa solo se reparte entre las órdenes que pasaron '
             'por ellos y, con base en horas, solo cuentan sus horas.')
    counterpart_account_id = fields.Many2one(
        'account.account', string='Contrapartida', required=True, check_company=True,
        help='Cuenta que se abona al cargar la bolsa a las órdenes (PCGE: 71 '
             'Variación de la producción almacenada).')

    @api.constrains('account_prefixes')
    def _check_account_prefixes(self):
        for pool in self:
            if not PREFIXES_RE.match(pool.account_prefixes or ''):
                raise ValidationError(_(
                    'La bolsa «%s»: las cuentas deben ser prefijos numéricos separados por comas.',
                    pool.name))

    def _get_prefixes(self):
        self.ensure_one()
        return [prefix.strip() for prefix in self.account_prefixes.split(',') if prefix.strip()]

    def _l10n_pe_amount(self, date_from, date_to):
        """Saldo deudor publicado de la bolsa en el rango."""
        self.ensure_one()
        domain = Domain.AND([
            [('company_id', '=', self.company_id.id),
             ('parent_state', '=', 'posted'),
             ('date', '>=', date_from), ('date', '<=', date_to)],
            Domain.OR([[('account_id.code', '=like', f'{prefix}%')] for prefix in self._get_prefixes()]),
        ])
        if not self.analytic_account_ids:
            groups = self.env['account.move.line']._read_group(domain, [], ['balance:sum'])
            return groups[0][0] or 0.0
        # Con centros de costo, solo el porcentaje del apunte que va a ellos.
        domain &= Domain('distribution_analytic_account_ids', 'in', self.analytic_account_ids.ids)
        wanted = {str(account_id) for account_id in self.analytic_account_ids.ids}
        amount = 0.0
        for line in self.env['account.move.line'].search_fetch(domain, ['balance', 'analytic_distribution']):
            share = sum(
                percentage for key, percentage in (line.analytic_distribution or {}).items()
                if wanted & set(key.split(',')))
            amount += line.balance * share / 100.0
        return amount

# -*- coding: utf-8 -*-
"""Bolsa de herramientas manuales (requerimiento CREVAL v1.0, 6.1): las
herramientas en % de la mano de obra no se piden; las compras de la
categoría de herramientas manuales cargadas a la obra consumen la bolsa (las
líneas del plan por % de la mano de obra), en proporción a lo planificado."""
from collections import defaultdict

from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    construction_hand_tools_categ_id = fields.Many2one(
        'product.category', string='Categoría de herramientas manuales',
        help='Las compras de esta categoría (y sus hijas) con la analítica de una obra consumen '
             'su bolsa de herramientas.')


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    construction_hand_tools_categ_id = fields.Many2one(
        related='company_id.construction_hand_tools_categ_id', readonly=False)


class ConstructionResourcePlanLine(models.Model):
    _inherit = 'construction.resource.plan.line'

    def _get_line_execution(self):
        result = super()._get_line_execution()
        bags = self.filtered(lambda l: l.calc_method == 'pct_labor')
        for plan, lines in bags.grouped('plan_id').items():
            committed, actual = plan._construction_tool_bag_amounts()
            if not committed and not actual:
                continue
            # La bolsa de la obra se reparte entre sus líneas por lo
            # planificado.
            plan_bags = plan.line_ids.filtered(lambda l: l.calc_method == 'pct_labor')
            total = sum(plan_bags.mapped('amount_planned'))
            for line in lines:
                share = line.amount_planned / total if total else 1.0 / len(plan_bags)
                currency = line.currency_id
                result[line] = (currency.round(committed * share), currency.round(actual * share))
        return result


class ConstructionResourcePlan(models.Model):
    _inherit = 'construction.resource.plan'

    def _construction_tool_bag_amounts(self):
        """(comprometido, real) de las herramientas manuales de la obra:
        real = facturas de proveedor publicadas; comprometido = órdenes
        confirmadas aún no facturadas. Con la parte de la analítica de la
        obra de cada línea."""
        self.ensure_one()
        category = self.company_id.construction_hand_tools_categ_id
        account = self.project_id.account_id
        if not category or not account:
            return 0.0, 0.0
        key = str(account.id)
        # sudo: el control lee compras y contabilidad aunque quien mira el
        # plan no las vea; solo se suman importes de la obra.
        move_lines_sudo = self.env['account.move.line'].sudo().search([
            ('product_id.categ_id', 'child_of', category.id),
            ('parent_state', '=', 'posted'), ('display_type', '=', 'product'),
            ('move_id.move_type', 'in', ('in_invoice', 'in_refund')),
            ('analytic_distribution', 'in', [account.id]),
            ('company_id', '=', self.company_id.id)])
        actual = sum(line.balance * float(_share(line.analytic_distribution, key)) / 100.0
                     for line in move_lines_sudo)
        po_lines_sudo = self.env['purchase.order.line'].sudo().search([
            ('product_id.categ_id', 'child_of', category.id),
            ('order_id.state', '=', 'purchase'),
            ('analytic_distribution', 'in', [account.id]),
            ('company_id', '=', self.company_id.id)])
        committed = sum(max(line.product_qty - line.qty_invoiced, 0.0) * line.price_unit
                        * float(_share(line.analytic_distribution, key)) / 100.0
                        for line in po_lines_sudo)
        return committed, actual


def _share(distribution, key):
    """Porcentaje de la cuenta ``key`` en una distribución analítica (las
    claves pueden combinar cuentas: «12,30»)."""
    totals = defaultdict(float)
    for accounts, pct in (distribution or {}).items():
        if key in str(accounts).split(','):
            totals[key] += pct
    return totals[key]

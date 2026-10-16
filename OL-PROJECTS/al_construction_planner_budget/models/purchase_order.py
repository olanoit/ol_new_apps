# -*- coding: utf-8 -*-
"""Control del saldo de la OC con analítica de la obra (fase 7, «Control de
saldo», en su puente desde la v1.7): al confirmar se contrasta con el
presupuesto analítico de la combinación según la política del plan vigente
(W-10)."""
from collections import defaultdict

from odoo import fields, models
from odoo.exceptions import UserError
from odoo.tools.misc import formatLang

from odoo.addons.al_construction_planner.models.common import EXCEED_STATES
from odoo.addons.al_construction_planner.models.construction_resource_plan import OPEN_STATES

# De la política más estricta a la más laxa: si una OC toca varias obras se
# aplica la más estricta.
POLICY_RANK = {'block': 3, 'approval': 2, 'warn': 1}


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    construction_exceed_state = fields.Selection(
        EXCEED_STATES, string='Control de presupuesto', default='ok', copy=False, readonly=True,
        tracking=True, help='Resultado del control contra el presupuesto analítico del plan '
                            'vigente de la obra al confirmar la OC.')
    construction_exceed_reason = fields.Text(
        string='Justificación del exceso', copy=False, tracking=True)

    # ------------------------------------------------------------------
    # Control del saldo (presupuesto analítico de la combinación)
    # ------------------------------------------------------------------
    def _construction_budget_amounts(self):
        """{(plan, línea de presupuesto o False): monto de esta OC} en la
        moneda de la compañía, por cada combinación analítica de sus líneas
        que incluye la cuenta de una obra con plan vigente. Sin línea de
        presupuesto que la cubra, la combinación queda fuera del presupuesto
        (False)."""
        self.ensure_one()
        Account = self.env['account.analytic.account']
        Plan = self.env['construction.resource.plan']
        company = self.company_id
        date = fields.Date.to_date(self.date_order) or fields.Date.context_today(self)
        amounts = defaultdict(float)
        plan_cache = {}
        for line in self.order_line.filtered(
                lambda l: not l.display_type and l.analytic_distribution):
            subtotal = self.currency_id._convert(
                line.price_subtotal, company.currency_id, company, date)
            for key, percentage in line.analytic_distribution.items():
                accounts = Account.browse(int(a) for a in key.split(',') if a).exists()
                for account in accounts:
                    if account not in plan_cache:
                        plan_cache[account] = Plan.search([
                            ('project_id.account_id', '=', account.id),
                            ('state', 'in', OPEN_STATES), ('budget_analytic_id', '!=', False),
                            ('company_id', '=', company.id)], limit=1)
                    plan = plan_cache[account]
                    if not plan:
                        continue
                    combo = {acc.root_plan_id._column_name(): acc.id for acc in accounts}
                    budget_line = plan._construction_match_budget_line(combo)
                    amounts[(plan, budget_line)] += subtotal * float(percentage) / 100.0
        return amounts

    def _construction_budget_excess(self):
        """[(plan, línea de presupuesto, presupuesto, usado, esta OC, exceso)]
        de las combinaciones que pasan el presupuesto más la tolerancia del
        plan. «Usado» es el comprometido de la línea de presupuesto (OC
        confirmadas sin facturar más lo ya imputado)."""
        self.ensure_one()
        rows = []
        currency = self.company_id.currency_id
        # El comprometido del presupuesto no tiene dependencias: se descarta
        # de la caché para ver las OC confirmadas en esta transacción.
        self.env['budget.line'].invalidate_model(['committed_amount', 'achieved_amount'])
        for (plan, budget_line), amount in self._construction_budget_amounts().items():
            budget = budget_line.budget_amount if budget_line else 0.0
            used = budget_line.committed_amount if budget_line else 0.0
            limit = budget * (1 + (plan.exceed_tolerance or 0.0) / 100.0)
            excess = used + amount - limit
            if currency.compare_amounts(excess, 0.0) > 0:
                rows.append((plan, budget_line, budget, used, amount, min(excess, amount)))
        return rows

    def _construction_budget_text(self, rows):
        return '\n'.join('   · %s: %s' % (
            budget_line.display_name if budget_line else self.env._(
                '%s (combinación fuera del presupuesto)', plan.display_name),
            formatLang(self.env, excess, currency_obj=self.company_id.currency_id))
            for plan, budget_line, _budget, _used, _amount, excess in rows)

    def button_confirm(self):
        checked = self.env.context.get('construction_exceed_checked')
        # Las OC de servicio (puente de contratas) se controlan al asignar la
        # contrata y al liquidar.
        for order in self.filtered(lambda o: o.state in ('draft', 'sent') and not getattr(
                o, 'construction_is_service_order', False)):
            # Quien compra no suele ver el plan ni el presupuesto analítico:
            # el control se calcula sin sus permisos, solo para esta OC.
            order_sudo = order.sudo()
            rows = order_sudo._construction_budget_excess()
            if not rows:
                if order.construction_exceed_state != 'ok':
                    order.construction_exceed_state = 'ok'
                continue
            policy = max((row[0]._exceed_policy_for('material') for row in rows),
                         key=POLICY_RANK.get)
            if policy == 'block':
                raise UserError(self.env._(
                    'La OC %(order)s pasa el presupuesto analítico del plan de la obra y su '
                    'política es bloquear:\n\n%(lines)s',
                    order=order.name, lines=order_sudo._construction_budget_text(rows)))
            if not checked:
                wizard = self.env['construction.plan.exceed.wizard'].create({
                    'purchase_order_id': order.id,
                    'reason': order.construction_exceed_reason,
                })
                return wizard._get_action()
        return super().button_confirm()

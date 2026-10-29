# -*- coding: utf-8 -*-
"""Liquidación y cierre de la orden de contrata y ampliación por adicionales
(requerimiento CREVAL v1.0, 3.9 y 3.11).

La liquidación es la valorización que cierra la orden: sus cantidades finales
son el acumulado validado (se reducen con motivo), amortiza el saldo del
adelanto y consolida deductivos y fondo de garantía. «Cerrar orden», con la
factura publicada y los documentos requeridos adjuntos, baja cada línea de la
orden a lo recibido (libera el saldo del plan y el comprometido del
presupuesto analítico) y la bloquea, salvo la devolución del fondo."""
from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import UserError

from odoo.addons.al_construction_planner.models.common import (
    EXEC_APPROVER_GROUPS, EXEC_USER_GROUP,
)

from .construction_contract_valuation import OPEN_SETTLEMENT_STATES, VALUED_STATES


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    construction_needs_reapproval = fields.Boolean(
        string='Ampliación por aprobar', copy=False, readonly=True, tracking=True,
        help='Un adicional llevó la orden sobre su monto aprobado: la diferencia espera la '
             'aprobación de Ejecución: aprueba.')
    construction_liquidation_id = fields.Many2one(
        'construction.contract.settlement', string='Liquidación',
        compute='_compute_construction_liquidation_id')

    def _compute_construction_liquidation_id(self):
        for order in self:
            order.construction_liquidation_id = order.construction_settlement_ids.filtered(
                lambda s: s.settlement_type == 'settlement' and s.state != 'cancel')[:1]

    def _construction_check_amount_approved(self):
        """Si la orden confirmada supera su monto aprobado, la diferencia
        vuelve a aprobación (3.9)."""
        for order in self.filtered(lambda o: o.state == 'purchase'
                                   and o.construction_amount_approved):
            if order.currency_id.compare_amounts(order.amount_total,
                                                 order.construction_amount_approved) > 0:
                order.construction_needs_reapproval = True
                order.message_post(body=self.env._(
                    'La orden pasa su monto aprobado (%(approved)s → %(total)s): la ampliación '
                    'espera aprobación.',
                    approved=order.currency_id.format(order.construction_amount_approved),
                    total=order.currency_id.format(order.amount_total)))

    def action_construction_approve_extension(self):
        if not self.env.user.has_groups(EXEC_APPROVER_GROUPS):
            raise UserError(self.env._('Aprueba la ampliación quien aprueba la ejecución.'))
        for order in self.filtered('construction_needs_reapproval'):
            difference = order.amount_total - order.construction_amount_approved
            order.write({'construction_needs_reapproval': False,
                         'construction_amount_approved': order.amount_total})
            order.order_line.filtered('construction_additional_pending').write(
                {'construction_additional_pending': False})
            order.message_post(body=self.env._(
                'Ampliación aprobada por %(user)s: %(amount)s.', user=self.env.user.name,
                amount=order.currency_id.format(difference)))
        return True

    def action_construction_liquidate(self):
        """Crea la liquidación de la orden (la valorización que la cierra)."""
        self.ensure_one()
        if not self.env.user.has_group(EXEC_USER_GROUP):
            raise UserError(self.env._('Liquida la orden quien ejecuta la obra.'))
        if not self.construction_uses_terms or self.state != 'purchase':
            raise UserError(self.env._(
                'Se liquida una orden de contrata confirmada y con condiciones.'))
        if self.construction_liquidation_id:
            liquidation = self.construction_liquidation_id
        else:
            if self.construction_settlement_ids.filtered(
                    lambda s: s.state in OPEN_SETTLEMENT_STATES):
                raise UserError(self.env._(
                    'Apruebe o anule la valorización abierta de %s antes de liquidar.', self.name))
            Settlement = self.env['construction.contract.settlement']
            today = fields.Date.context_today(self)
            start = Settlement._terms_next_start(self) or today
            last = self.env['construction.task.progress'].sudo().search(
                self._construction_progress_domain(), order='date desc', limit=1).date
            liquidation = Settlement.create({
                'purchase_order_id': self.id, 'settlement_type': 'settlement',
                'period_start': start, 'date_cutoff': max(today, start, last or start)})
            liquidation._refresh_lines()
        return {'type': 'ir.actions.act_window', 'res_model': liquidation._name,
                'res_id': liquidation.id, 'view_mode': 'form'}


class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    construction_additional_pending = fields.Boolean(
        string='Adicional por aprobar', copy=False, readonly=True,
        help='No entra a las valorizaciones hasta que se apruebe la ampliación de la orden.')

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        additional = lines.filtered('construction_is_additional')
        additional.order_id._construction_check_amount_approved()
        additional.filtered(lambda l: l.order_id.construction_needs_reapproval).write(
            {'construction_additional_pending': True})
        return lines


class ConstructionContractSettlement(models.Model):
    _inherit = 'construction.contract.settlement'

    order_document_ids = fields.One2many(
        related='purchase_order_id.construction_document_ids', readonly=False,
        string='Documentos requeridos')
    documents_complete = fields.Boolean(
        string='Documentos completos', compute='_compute_documents_complete')
    order_closed = fields.Boolean(related='purchase_order_id.construction_closed',
                                  string='Orden cerrada')
    can_close_order = fields.Boolean(compute='_compute_documents_complete')

    @api.depends('order_document_ids.is_attached', 'invoice_id.state', 'state',
                 'settlement_type')
    def _compute_documents_complete(self):
        for settlement in self:
            settlement.documents_complete = all(settlement.order_document_ids.mapped(
                'is_attached'))
            settlement.can_close_order = (
                settlement.settlement_type == 'settlement' and settlement.state in VALUED_STATES
                and settlement.invoice_id.state == 'posted' and settlement.documents_complete
                and not settlement.order_closed)

    def _action_approve(self):
        res = super()._action_approve()
        for settlement in self.filtered(lambda s: s.uses_terms
                                        and s.settlement_type == 'settlement'):
            settlement._update_guarantee_dates()
        return res

    def _update_guarantee_dates(self):
        """Fondo «desde la liquidación»: con la liquidación aprobada, el
        vencimiento de cada cuota de la orden es su fecha más el plazo."""
        self.ensure_one()
        terms = self.terms_id
        if terms.guarantee_from != 'settlement' or not self.settlement_date:
            return
        due = self.settlement_date + timedelta(days=terms.guarantee_days or 0)
        # sudo: la cuota es de la factura de cada valorizado; la liquidación
        # solo corre su vencimiento.
        for fund in self.purchase_order_id.sudo().construction_guarantee_fund_ids.filtered(
                lambda f: not f.is_opening and f.amount_residual):
            if fund.move_line_id and not fund.move_line_id.reconciled:
                fund.move_line_id.date_maturity = due
            fund.date_maturity = due
        moves = self.purchase_order_id.construction_settlement_ids.invoice_id.filtered(
            lambda m: m.state == 'draft' and m.construction_guarantee_amount)
        moves.sudo().construction_guarantee_date = due

    def action_close_order(self):
        """Cierra la orden: cada línea baja a lo recibido, se libera el saldo
        del plan y la orden queda bloqueada (el fondo se devuelve después)."""
        self.ensure_one()
        if not self.can_close_order:
            raise UserError(self.env._(
                'Para cerrar la orden, la liquidación debe estar aprobada, con su factura '
                'publicada y los documentos requeridos adjuntos.'))
        # sudo: quien liquida no administra compras; el cierre es la
        # consecuencia de la liquidación aprobada.
        order_sudo = self.purchase_order_id.sudo()
        released = []
        for line in order_sudo.order_line.filtered(lambda l: not l.display_type):
            if line.uom_id.compare(line.qty_received, line.product_qty) < 0:
                released.append('%s: %s → %s' % (line.name, round(line.product_qty, 2),
                                                round(line.qty_received, 2)))
                line.product_qty = line.qty_received
            for allocation in line.construction_allocation_ids.filtered(
                    lambda a: a.state != 'cancel'):
                if allocation.plan_line_id.product_uom_id.compare(
                        allocation.qty_done, allocation.qty_allocated) < 0:
                    allocation.qty_allocated = allocation.qty_done
        order_sudo.write({'construction_closed': True})
        if 'locked' in order_sudo._fields and not order_sudo.locked:
            order_sudo.button_lock()
        order_sudo.order_line.construction_allocation_ids.plan_line_id._refresh_control()
        body = self.env._('Orden cerrada con la liquidación %s.', self.display_name)
        if released:
            body += ' ' + self.env._('Alcance no ejecutado liberado: %s.', '; '.join(released))
        order_sudo.message_post(body=body)
        self.message_post(body=body)
        return True


class ConstructionContractSettlementLine(models.Model):
    _inherit = 'construction.contract.settlement.line'

    qty_final = fields.Float(
        string='Cantidad final', digits='Product Unit',
        help='Liquidación: el acumulado validado; se reduce con motivo.')
    final_reason = fields.Text(string='Motivo de la reducción')
    qty_released = fields.Float(string='Liberado', compute='_compute_released',
                                digits='Product Unit')
    amount_released = fields.Monetary(string='Importe liberado', compute='_compute_released',
                                      currency_field='currency_id')

    @api.depends('qty_period', 'pct_manual', 'qty_settled_before', 'is_rework', 'qty_final',
                 'qty_previous', 'rework_paid', 'no_progress')
    def _compute_qty_settle(self):
        super()._compute_qty_settle()
        for line in self.filtered(lambda l: l.settlement_id.settlement_type == 'settlement'
                                  and not l.is_rework and l.qty_final and not l.no_progress):
            line.qty_settle = max(line.qty_final - line.qty_previous, 0.0)

    def _construction_has_decision(self):
        # La cantidad final reducida con motivo (CR-15).
        return super()._construction_has_decision() or bool(self.final_reason)

    @api.model
    def _decision_fields(self):
        return super()._decision_fields() | {'qty_final', 'final_reason'}

    def _record_decision(self, vals):
        if self.env.context.get('construction_final_sync'):
            return
        super()._record_decision(vals)

    def _sync_refresh(self):
        """Sin reducción con motivo, la cantidad final sigue al acumulado
        validado, como al crear la línea."""
        super()._sync_refresh()
        for line in self.filtered(lambda l: l.settlement_id.settlement_type == 'settlement'
                                  and not l.is_rework and not l.final_reason):
            line.with_context(construction_final_sync=True).qty_final = \
                line.qty_previous + line.qty_period

    def _compute_released(self):
        for line in self:
            final = line.qty_previous + line.qty_settle
            line.qty_released = max(line.qty_contracted - final, 0.0) \
                if line.settlement_id.settlement_type == 'settlement' else 0.0
            line.amount_released = line.currency_id.round(line.qty_released * line.price_unit)

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        for line in lines.filtered(lambda l: l.settlement_id.settlement_type == 'settlement'
                                   and not l.is_rework):
            line.with_context(construction_final_sync=True).qty_final = \
                line.qty_previous + line.qty_period
        return lines

    def write(self, vals):
        if 'qty_final' in vals and not self.env.context.get('construction_final_sync'):
            for line in self:
                validated = line.qty_previous + line.qty_period
                uom = line.purchase_line_id.uom_id
                if line.settlement_id.state not in ('draft', 'submitted'):
                    raise UserError(self.env._(
                        'La cantidad final se escribe con la liquidación en borrador o presentada.'))
                if uom.compare(vals['qty_final'], validated) > 0:
                    raise UserError(self.env._(
                        '%(activity)s: la cantidad final no puede pasar el acumulado validado '
                        '(%(qty)s).', activity=line.activity_id.display_name,
                        qty=round(validated, 2)))
                if uom.compare(vals['qty_final'], validated) < 0 and not (
                        vals.get('final_reason') or line.final_reason):
                    raise UserError(self.env._('Una cantidad final reducida pide su motivo.'))
        res = super().write(vals)
        if 'qty_final' in vals and not self.env.context.get('construction_final_sync'):
            self.settlement_id._terms_recompute()
        return res

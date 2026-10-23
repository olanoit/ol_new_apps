# -*- coding: utf-8 -*-
"""Fondo de garantía de contratas (requerimiento CREVAL v1.0, 3.8): una fila
por cuota de fondo de cada factura de valorizado (o de la valorización de
apertura), con su vencimiento y el estado de los requisitos de devolución de
la orden. Cuando todos se cumplen, administración programa el pago; si uno
falla, marca la devolución como retenida con su motivo."""
from odoo import api, fields, models
from odoo.exceptions import UserError

FUND_STATES = [
    ('pending', 'Por cumplir requisitos'),
    ('ready', 'Lista para devolver'),
    ('retained', 'Devolución retenida'),
    ('paid', 'Devuelto'),
]
# Documentos que pueden retener la devolución (el ticket de postventa).
HOLD_REFERENCE_MODELS = [
    ('helpdesk.ticket', 'Ticket de postventa'),
    ('project.task', 'Tarea'),
]


class ConstructionGuaranteeFund(models.Model):
    _name = 'construction.guarantee.fund'
    _description = 'Fondo de garantía de contrata'
    _inherit = ['mail.thread']
    _order = 'date_maturity, id'
    _check_company_auto = True
    _rec_name = 'display_name'

    purchase_order_id = fields.Many2one(
        'purchase.order', string='Orden de contrata', required=True, index=True,
        check_company=True, ondelete='cascade')
    partner_id = fields.Many2one(related='purchase_order_id.partner_id', string='Contratista',
                                 store=True, index=True)
    project_id = fields.Many2one(related='purchase_order_id.construction_project_id',
                                 string='Obra', store=True, index=True)
    company_id = fields.Many2one(related='purchase_order_id.company_id', string='Compañía',
                                 store=True, index=True)
    currency_id = fields.Many2one(related='purchase_order_id.currency_id', string='Moneda')
    settlement_id = fields.Many2one('construction.contract.settlement', string='Valorización',
                                    check_company=True, index='btree_not_null')
    move_id = fields.Many2one('account.move', string='Factura', check_company=True,
                              index='btree_not_null', ondelete='cascade')
    move_line_id = fields.Many2one('account.move.line', string='Cuota', index='btree_not_null')
    amount = fields.Monetary(string='Monto', required=True, currency_field='currency_id')
    amount_residual = fields.Monetary(
        string='Por devolver', compute='_compute_amount_residual', store=True,
        currency_field='currency_id')
    date_maturity = fields.Date(string='Vencimiento', required=True)
    is_opening = fields.Boolean(string='De la carga inicial', readonly=True)
    requirement_summary = fields.Char(string='Requisitos', compute='_compute_state')
    requirements_ok = fields.Boolean(string='Requisitos cumplidos', compute='_compute_state')
    hold = fields.Boolean(string='Devolución retenida', tracking=True, copy=False)
    hold_reason = fields.Text(string='Motivo de la retención', tracking=True, copy=False)
    hold_reference = fields.Reference(
        selection='_selection_hold_reference', string='Observación de postventa', copy=False)
    state = fields.Selection(FUND_STATES, string='Estado', compute='_compute_state')

    @api.model
    def _selection_hold_reference(self):
        return [(model, label) for model, label in HOLD_REFERENCE_MODELS if model in self.env]

    @api.depends('purchase_order_id', 'date_maturity')
    def _compute_display_name(self):
        for fund in self:
            fund.display_name = '%s · %s' % (fund.purchase_order_id.name or '',
                                             fields.Date.to_string(fund.date_maturity) or '')

    @api.depends('amount', 'move_line_id.amount_residual', 'move_line_id.reconciled')
    def _compute_amount_residual(self):
        for fund in self:
            line = fund.move_line_id
            fund.amount_residual = abs(line.amount_residual) if line else fund.amount

    def _requirement_status(self, today):
        """[(requisito, cumplido)] de la orden: el vencimiento del plazo se
        cumple con la fecha; los demás, con la marca de administración."""
        self.ensure_one()
        result = []
        for status in self.purchase_order_id.construction_requirement_ids:
            done = status.done
            if status.requirement_id.code == 'term':
                done = bool(self.date_maturity and self.date_maturity <= today)
            result.append((status.requirement_id, done))
        return result

    @api.depends('hold', 'amount_residual', 'date_maturity',
                 'purchase_order_id.construction_requirement_ids.done')
    def _compute_state(self):
        today = fields.Date.context_today(self)
        for fund in self:
            status = fund._requirement_status(today)
            fund.requirements_ok = all(done for _req, done in status)
            fund.requirement_summary = ', '.join(
                '%s %s' % ('✔' if done else '✘', req.name) for req, done in status) or False
            if fund.currency_id.is_zero(fund.amount_residual):
                fund.state = 'paid'
            elif fund.hold:
                fund.state = 'retained'
            elif fund.requirements_ok and fund.date_maturity and fund.date_maturity <= today:
                fund.state = 'ready'
            else:
                fund.state = 'pending'

    def write(self, vals):
        if {'hold', 'hold_reason', 'hold_reference'} & set(vals) and not self.env.su \
                and not self.env.user.has_groups(
                    'account.group_account_invoice,'
                    'al_construction_planner.group_planner_exec_approver'):
            raise UserError(self.env._(
                'Retiene la devolución del fondo administración o la gerencia.'))
        if vals.get('hold') and not (vals.get('hold_reason') or all(self.mapped('hold_reason'))):
            raise UserError(self.env._('Escriba el motivo de la retención del fondo.'))
        return super().write(vals)

    def action_view_move(self):
        self.ensure_one()
        return {'type': 'ir.actions.act_window', 'res_model': 'account.move',
                'res_id': self.move_id.id, 'view_mode': 'form'}


class ConstructionContractOrderRequirement(models.Model):
    _name = 'construction.contract.order.requirement'
    _description = 'Requisito de devolución del fondo en la orden de contrata'
    _order = 'order_id, sequence, id'

    order_id = fields.Many2one('purchase.order', string='Orden de contrata', required=True,
                               ondelete='cascade', index=True)
    company_id = fields.Many2one(related='order_id.company_id', store=True, index=True)
    requirement_id = fields.Many2one('construction.contract.requirement', string='Requisito',
                                     required=True)
    sequence = fields.Integer(related='requirement_id.sequence')
    code = fields.Selection(related='requirement_id.code')
    done = fields.Boolean(string='Cumplido')
    date = fields.Date(string='Fecha')
    note = fields.Char(string='Nota')
    attachment_ids = fields.Many2many(
        'ir.attachment', 'construction_order_requirement_attachment_rel', 'requirement_id',
        'attachment_id', string='Adjuntos')


class ConstructionContractOrderDocument(models.Model):
    _name = 'construction.contract.order.document'
    _description = 'Documento requerido de la orden de contrata'
    _order = 'order_id, sequence, id'

    order_id = fields.Many2one('purchase.order', string='Orden de contrata', required=True,
                               ondelete='cascade', index=True)
    company_id = fields.Many2one(related='order_id.company_id', store=True, index=True)
    document_type_id = fields.Many2one('construction.contract.document.type', string='Documento',
                                       required=True)
    sequence = fields.Integer(related='document_type_id.sequence')
    attachment_ids = fields.Many2many(
        'ir.attachment', 'construction_order_document_attachment_rel', 'document_id',
        'attachment_id', string='Adjuntos')
    is_attached = fields.Boolean(string='Adjuntado', compute='_compute_is_attached', store=True)

    @api.depends('attachment_ids')
    def _compute_is_attached(self):
        for document in self:
            document.is_attached = bool(document.attachment_ids)

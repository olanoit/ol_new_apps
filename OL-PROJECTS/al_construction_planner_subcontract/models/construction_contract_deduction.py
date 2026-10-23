# -*- coding: utf-8 -*-
"""Deductivos de contrata (requerimiento CREVAL v1.0, 3.7): un monto que se
descuenta al contratista con sustento (un remate que terminó el personal
propio, una reposición, un consumo a su cargo o material entregado sobre lo
planificado). Entra a la siguiente valorización de su orden; aplicado, no se
edita: se corrige con otro de signo contrario."""
from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

DEDUCTION_STATES = [
    ('pending', 'Pendiente'),
    ('in_valuation', 'En valorización'),
    ('applied', 'Aplicado'),
    ('cancel', 'Anulado'),
]
# Documentos que puede citar un deductivo, si su módulo está instalado.
REFERENCE_MODELS = [
    ('project.task', 'Tarea'),
    ('construction.labor.cost.allocation', 'Cierre de costo de personal'),
    ('construction.material.request', 'Requerimiento de material'),
]


class ConstructionContractDeductionType(models.Model):
    _name = 'construction.contract.deduction.type'
    _description = 'Tipo de deductivo de contrata'
    _order = 'sequence, name, id'

    name = fields.Char(string='Tipo', required=True, translate=True)
    code = fields.Char(string='Código')
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)


class ConstructionContractDeduction(models.Model):
    _name = 'construction.contract.deduction'
    _description = 'Deductivo de contrata'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'
    _check_company_auto = True

    name = fields.Char(string='Número', required=True, readonly=True, copy=False, default='/')
    purchase_order_id = fields.Many2one(
        'purchase.order', string='Orden de contrata', required=True, index=True,
        check_company=True, tracking=True,
        domain="[('construction_is_service_order', '=', True), ('state', 'in', ('purchase', 'done'))]")
    project_id = fields.Many2one(
        related='purchase_order_id.construction_project_id', string='Obra', store=True,
        index=True)
    partner_id = fields.Many2one(
        related='purchase_order_id.partner_id', string='Contratista', store=True, index=True)
    company_id = fields.Many2one(
        related='purchase_order_id.company_id', string='Compañía', store=True, index=True)
    currency_id = fields.Many2one(related='purchase_order_id.currency_id', string='Moneda')
    date = fields.Date(string='Fecha', required=True, default=fields.Date.context_today,
                       tracking=True)
    type_id = fields.Many2one(
        'construction.contract.deduction.type', string='Tipo', required=True, tracking=True)
    description = fields.Text(string='Descripción', required=True)
    amount = fields.Monetary(string='Monto sin IGV', required=True, tracking=True,
                             currency_field='currency_id')
    is_reversal = fields.Boolean(
        string='Corrige otro deductivo', readonly=True, copy=False,
        help='Signo contrario: devuelve al contratista lo descontado de más.')
    reversed_id = fields.Many2one('construction.contract.deduction', string='Corrige a',
                                  readonly=True, copy=False)
    signed_amount = fields.Monetary(string='Monto con signo', compute='_compute_signed_amount',
                                    store=True, currency_field='currency_id')
    task_id = fields.Many2one(
        'project.task', string='Partida', check_company=True,
        domain="[('project_id', '=', project_id), ('construction_level', '!=', False)]",
        help='Su analítica va a la línea del deductivo en la factura.')
    reference = fields.Reference(
        selection='_selection_reference', string='Referencia',
        help='Tarea de servicio externo, cierre de costo de personal o requerimiento de material '
             'extra que justifica el deductivo.')
    attachment_ids = fields.Many2many(
        'ir.attachment', 'construction_deduction_attachment_rel', 'deduction_id',
        'attachment_id', string='Sustento')
    state = fields.Selection(DEDUCTION_STATES, string='Estado', required=True, default='pending',
                             tracking=True, copy=False)
    settlement_id = fields.Many2one(
        'construction.contract.settlement', string='Valorización', readonly=True, copy=False,
        index='btree_not_null', check_company=True)

    @api.model
    def _selection_reference(self):
        return [(model, label) for model, label in REFERENCE_MODELS if model in self.env]

    @api.depends('amount', 'is_reversal')
    def _compute_signed_amount(self):
        for deduction in self:
            deduction.signed_amount = -deduction.amount if deduction.is_reversal \
                else deduction.amount

    @api.constrains('amount')
    def _check_amount(self):
        for deduction in self:
            if deduction.currency_id.compare_amounts(deduction.amount, 0.0) <= 0:
                raise ValidationError(self.env._(
                    'El monto del deductivo debe ser mayor que cero.'))

    @api.constrains('attachment_ids', 'state')
    def _check_support(self):
        for deduction in self:
            # El material extra trae su sustento en el requerimiento.
            if deduction.state != 'cancel' and not deduction.attachment_ids \
                    and not deduction.reversed_id and not deduction.reference:
                raise ValidationError(self.env._(
                    'Adjunte el sustento del deductivo (%s).', deduction.display_name))

    @api.model_create_multi
    def create(self, vals_list):
        orders = self.env['purchase.order'].browse(
            [vals['purchase_order_id'] for vals in vals_list if vals.get('purchase_order_id')])
        for vals in vals_list:
            if vals.get('name', '/') == '/':
                order = orders.filtered(lambda o: o.id == vals.get('purchase_order_id'))
                vals['name'] = self._next_name(order.construction_project_id)
        deductions = super().create(vals_list)
        # El sustento queda también en el historial del deductivo.
        for deduction in deductions:
            deduction.attachment_ids.filtered(lambda a: not a.res_id).write(
                {'res_model': deduction._name, 'res_id': deduction.id})
        return deductions

    def _next_name(self, project):
        """Secuencia por obra: «<código de la obra>-DED-0001»."""
        code = project and (project._fields.get('construction_code') and project.construction_code
                            or (project.name or '').split(' ')[0])
        prefix = (code or 'DED') + '-DED-'
        count = self.sudo().with_context(active_test=False).search_count(
            [('project_id', '=', project.id)]) if project else 0
        return '%s%04d' % (prefix, count + 1)

    def write(self, vals):
        protected = set(vals) - {'state', 'settlement_id', 'message_main_attachment_id'}
        if protected and self.filtered(lambda d: d.state in ('in_valuation', 'applied')) \
                and not self.env.context.get('construction_deduction_sync'):
            raise UserError(self.env._(
                'Un deductivo en una valorización o aplicado no se edita: corríjalo con otro de '
                'signo contrario.'))
        return super().write(vals)

    @api.ondelete(at_uninstall=False)
    def _unlink_only_pending(self):
        if self.filtered(lambda d: d.state not in ('pending', 'cancel')):
            raise UserError(self.env._('Solo se borran deductivos pendientes o anulados.'))

    def action_cancel(self):
        if self.filtered(lambda d: d.state == 'applied'):
            raise UserError(self.env._(
                'Un deductivo aplicado no se anula: corríjalo con otro de signo contrario.'))
        self.filtered(lambda d: d.state == 'in_valuation').settlement_id._check_state(('draft',))
        self.with_context(construction_deduction_sync=True).write(
            {'state': 'cancel', 'settlement_id': False})

    def action_draft(self):
        self.filtered(lambda d: d.state == 'cancel').state = 'pending'

    def action_reverse(self):
        """Deductivo de signo contrario que corrige uno aplicado."""
        self.ensure_one()
        if self.state != 'applied':
            raise UserError(self.env._('Solo se corrige un deductivo aplicado.'))
        reversal = self.copy({
            'is_reversal': not self.is_reversal, 'reversed_id': self.id,
            'description': self.env._('Corrige %(name)s: %(text)s', name=self.name,
                                      text=self.description),
            'attachment_ids': [(6, 0, self.attachment_ids.ids)],
        })
        return {
            'type': 'ir.actions.act_window', 'res_model': self._name, 'res_id': reversal.id,
            'view_mode': 'form',
        }

    def _analytic_distribution(self):
        self.ensure_one()
        task = self.task_id
        if task:
            plan_lines = self.env['construction.resource.plan.line'].sudo().search(
                [('task_id', '=', task.id), ('analytic_distribution', '!=', False)], limit=1)
            if plan_lines.analytic_distribution:
                return plan_lines.analytic_distribution
        account = self.project_id.account_id
        return {str(account.id): 100.0} if account else False

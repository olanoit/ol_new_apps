# -*- coding: utf-8 -*-
"""Asistentes de la valorización: preparar (W-13) y confirmar (W-14)."""
from odoo import Command, api, fields, models
from odoo.exceptions import UserError


class ConstructionValuationPrepareWizard(models.TransientModel):
    """Preparar valorización (W-13): las entregas confirmadas no valorizadas
    de la obra hasta el corte y su monto por partida; crea la valorización en
    borrador."""
    _name = 'construction.valuation.prepare.wizard'
    _description = 'Preparar valorización'
    _check_company_auto = True

    project_id = fields.Many2one(
        'project.project', string='Obra', required=True, check_company=True,
        domain=[('is_construction_site', '=', True), ('construction_sale_order_id', '!=', False)])
    company_id = fields.Many2one(
        'res.company', string='Compañía', compute='_compute_company_id',
        help='La de la obra o, si la obra es compartida, la activa (como las entregas).')
    currency_id = fields.Many2one(
        'res.currency', string='Moneda', compute='_compute_preview')
    cutoff_date = fields.Date(
        string='Corte', required=True, compute='_compute_cutoff_date', store=True,
        readonly=False, help='Por defecto, el último corte de la obra hasta hoy.')
    delivery_ids = fields.Many2many(
        'construction.weekly.delivery', string='Entregas', compute='_compute_preview',
        check_company=True)
    line_ids = fields.One2many(
        'construction.valuation.prepare.wizard.line', 'wizard_id', string='Monto por partida',
        compute='_compute_preview')
    amount_delivered = fields.Monetary(string='Entregado', compute='_compute_preview')

    @api.depends('project_id')
    def _compute_company_id(self):
        for wizard in self:
            wizard.company_id = wizard.project_id.company_id or self.env.company

    @api.depends('project_id')
    def _compute_cutoff_date(self):
        today = fields.Date.context_today(self)
        for wizard in self:
            cutoffs = [c for c in wizard.project_id._construction_valuation_cutoffs()
                       if c <= today] if wizard.project_id else []
            wizard.cutoff_date = cutoffs[-1] if cutoffs else today

    @api.depends('project_id', 'cutoff_date')
    def _compute_preview(self):
        Valuation = self.env['construction.valuation']
        for wizard in self:
            wizard.currency_id = (wizard.company_id or self.env.company).currency_id
            if not wizard.project_id or not wizard.cutoff_date:
                wizard.delivery_ids = wizard.line_ids = False
                wizard.amount_delivered = 0.0
                continue
            deliveries = Valuation._get_pending_deliveries(wizard.project_id, wizard.cutoff_date)
            values = Valuation._get_line_values(wizard.project_id, deliveries, wizard.cutoff_date)
            wizard.delivery_ids = deliveries
            wizard.line_ids = [Command.clear()] + [Command.create({
                'sale_line_id': vals['sale_line_id'],
                'progress_delivered': vals['progress_delivered'],
                'amount_delivered': vals['amount_delivered'],
            }) for vals in values]
            wizard.amount_delivered = sum(v['amount_delivered'] for v in values)

    def action_create(self):
        self.ensure_one()
        deliveries = self.env['construction.valuation']._get_pending_deliveries(
            self.project_id, self.cutoff_date)
        valuation = self.env['construction.valuation']._create_from_deliveries(
            self.project_id, self.cutoff_date, deliveries)
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'construction.valuation',
            'res_id': valuation.id,
            'view_mode': 'form',
            'target': 'current',
        }


class ConstructionValuationPrepareWizardLine(models.TransientModel):
    _name = 'construction.valuation.prepare.wizard.line'
    _description = 'Partida de la valorización por preparar'

    wizard_id = fields.Many2one(
        'construction.valuation.prepare.wizard', string='Asistente', required=True,
        ondelete='cascade')
    currency_id = fields.Many2one(related='wizard_id.currency_id', string='Moneda')
    sale_line_id = fields.Many2one('sale.order.line', string='Partida', readonly=True)
    progress_delivered = fields.Float(string='Avance entregado', readonly=True)
    amount_delivered = fields.Monetary(string='Entregado', readonly=True)


class ConstructionValuationConfirmWizard(models.TransientModel):
    """Confirmar valorización (W-14): fecha, quién confirma, su cargo y el
    documento de conformidad, obligatorios, y el monto confirmado por
    partida; lo no confirmado queda por valorizar."""
    _name = 'construction.valuation.confirm.wizard'
    _description = 'Confirmar valorización'

    valuation_id = fields.Many2one(
        'construction.valuation', string='Valorización', required=True, readonly=True)
    currency_id = fields.Many2one(related='valuation_id.currency_id', string='Moneda')
    confirm_date = fields.Date(
        string='Fecha de conformidad', required=True, default=fields.Date.context_today)
    confirm_name = fields.Char(string='Confirmado por', required=True,
                               help='Nombre de quien confirma por el cliente.')
    confirm_role = fields.Char(string='Cargo', required=True)
    attachment_ids = fields.Many2many(
        'ir.attachment', 'construction_valuation_confirm_wizard_attachment_rel', 'wizard_id',
        'attachment_id', string='Documento de conformidad',
        help='Acta, correo o carta del cliente; queda como adjunto de la valorización.')
    line_ids = fields.One2many(
        'construction.valuation.confirm.wizard.line', 'wizard_id', string='Partidas',
        compute='_compute_line_ids', store=True, readonly=False)
    amount_delivered = fields.Monetary(string='Entregado', compute='_compute_totals')
    amount_confirmed = fields.Monetary(string='Confirmado', compute='_compute_totals')
    amount_pending = fields.Monetary(string='Por valorizar', compute='_compute_totals')

    @api.depends('valuation_id')
    def _compute_line_ids(self):
        for wizard in self:
            wizard.line_ids = [Command.clear()] + [Command.create({
                'valuation_line_id': line.id,
                'amount_confirmed': line.amount_delivered,
            }) for line in wizard.valuation_id.line_ids]

    @api.depends('line_ids.amount_confirmed', 'line_ids.amount_delivered')
    def _compute_totals(self):
        for wizard in self:
            wizard.amount_delivered = sum(wizard.line_ids.mapped('amount_delivered'))
            wizard.amount_confirmed = sum(wizard.line_ids.mapped('amount_confirmed'))
            wizard.amount_pending = wizard.amount_delivered - wizard.amount_confirmed

    def action_confirm(self):
        self.ensure_one()
        missing = [label for field, label in (
            ('confirm_date', self.env._('fecha')), ('confirm_name', self.env._('nombre')),
            ('confirm_role', self.env._('cargo')), ('attachment_ids', self.env._('documento')))
            if not self[field]]
        if missing:
            raise UserError(self.env._(
                'Para confirmar la valorización falta: %s.', ', '.join(missing)))
        valuation = self.valuation_id
        # Los adjuntos subidos en el asistente pasan a la valorización.
        self.attachment_ids.write({'res_model': valuation._name, 'res_id': valuation.id})
        valuation._action_confirm({
            'confirm_date': self.confirm_date,
            'confirm_name': self.confirm_name,
            'confirm_role': self.confirm_role,
            'confirm_attachment_ids': [Command.set(self.attachment_ids.ids)],
        }, {line.valuation_line_id: line.amount_confirmed for line in self.line_ids})
        valuation.message_post(
            body=self.env._(
                'Conformidad del cliente del %(date)s: %(name)s (%(role)s). Confirmado: '
                '%(confirmed)s de %(delivered)s entregado.',
                date=self.confirm_date.strftime('%d/%m/%Y'), name=self.confirm_name,
                role=self.confirm_role, confirmed=round(valuation.amount_confirmed, 2),
                delivered=round(valuation.amount_delivered, 2)),
            attachment_ids=self.attachment_ids.ids)
        return {'type': 'ir.actions.act_window_close'}


class ConstructionValuationConfirmWizardLine(models.TransientModel):
    _name = 'construction.valuation.confirm.wizard.line'
    _description = 'Monto confirmado por partida'

    wizard_id = fields.Many2one(
        'construction.valuation.confirm.wizard', string='Asistente', required=True,
        ondelete='cascade')
    currency_id = fields.Many2one(related='wizard_id.currency_id', string='Moneda')
    valuation_line_id = fields.Many2one(
        'construction.valuation.line', string='Línea', required=True, readonly=True)
    sale_line_id = fields.Many2one(related='valuation_line_id.sale_line_id', string='Partida')
    amount_delivered = fields.Monetary(
        related='valuation_line_id.amount_delivered', string='Entregado')
    amount_confirmed = fields.Monetary(string='Confirmado')
    amount_difference = fields.Monetary(
        string='Diferencia', compute='_compute_difference',
        help='Entregado menos confirmado: queda por valorizar.')

    @api.depends('amount_delivered', 'amount_confirmed')
    def _compute_difference(self):
        for line in self:
            line.amount_difference = line.amount_delivered - line.amount_confirmed

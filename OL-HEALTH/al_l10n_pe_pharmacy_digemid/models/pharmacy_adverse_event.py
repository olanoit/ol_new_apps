# -*- coding: utf-8 -*-
"""Sospechas de reacciones adversas (BPOF 7.5.3; notificación por NotiMED,
Comunicado DIGEMID 002-2025): registro correlativo con el plazo de
notificación (graves 24 horas; las demás, los días de la compañía)."""
from datetime import timedelta

from odoo import api, fields, models


class PharmacyAdverseEvent(models.Model):
    _name = 'pharmacy.adverse.event'
    _description = 'Sospecha de reacción adversa'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_detected desc, id desc'
    _check_company_auto = True

    name = fields.Char(string='Número', readonly=True, copy=False, default='/')
    date_detected = fields.Datetime(string='Detectada el', required=True, default=fields.Datetime.now)
    patient_initials = fields.Char(string='Iniciales del paciente', required=True)
    patient_age = fields.Integer(string='Edad')
    patient_sex = fields.Selection([('f', 'Femenino'), ('m', 'Masculino')], string='Sexo')
    patient_weight = fields.Float(string='Peso (kg)')
    product_id = fields.Many2one('product.product', string='Medicamento sospechoso', required=True,
                                 check_company=True)
    lot_id = fields.Many2one('stock.lot', string='Lote', check_company=True,
                             domain="[('product_id', '=', product_id)]")
    dose = fields.Char(string='Dosis y frecuencia')
    route_id = fields.Many2one('pharmacy.route', string='Vía')
    therapy_start = fields.Date(string='Inicio del tratamiento')
    reaction_start = fields.Date(string='Inicio de la reacción')
    reaction = fields.Text(string='Descripción de la reacción', required=True)
    severity = fields.Selection([('serious', 'Grave'), ('non_serious', 'No grave')],
                                string='Gravedad', required=True, default='non_serious')
    outcome = fields.Selection([
        ('recovered', 'Recuperado'),
        ('recovering', 'En recuperación'),
        ('not_recovered', 'No recuperado'),
        ('sequelae', 'Recuperado con secuelas'),
        ('death', 'Muerte'),
        ('unknown', 'Desconocido'),
    ], string='Desenlace', default='unknown')
    reporter_id = fields.Many2one('res.users', string='Notificador', default=lambda self: self.env.user)
    deadline = fields.Datetime(string='Notificar hasta', compute='_compute_deadline', store=True)
    notified_date = fields.Datetime(string='Notificada el', tracking=True)
    notimed_reference = fields.Char(string='Código NotiMED', tracking=True)
    state = fields.Selection([('draft', 'Por notificar'), ('notified', 'Notificada')],
                             string='Estado', default='draft', tracking=True)
    overdue = fields.Boolean(string='Fuera de plazo', compute='_compute_overdue')
    company_id = fields.Many2one('res.company', string='Compañía', required=True, readonly=True,
                                 default=lambda self: self.env.company)

    @api.depends('date_detected', 'severity', 'company_id.pharmacy_adverse_event_days')
    def _compute_deadline(self):
        for event in self:
            if not event.date_detected:
                event.deadline = False
            elif event.severity == 'serious':
                event.deadline = event.date_detected + timedelta(hours=24)
            else:
                event.deadline = event.date_detected + timedelta(
                    days=event.company_id.pharmacy_adverse_event_days or 15)

    def _compute_overdue(self):
        now = fields.Datetime.now()
        for event in self:
            event.overdue = event.state == 'draft' and bool(event.deadline) and event.deadline < now

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', '/') == '/':
                vals['name'] = self.env['ir.sequence'].next_by_code('pharmacy.adverse.event') or '/'
        events = super().create(vals_list)
        for event in events:
            self.env['pharmacy.logbook.entry']._log('adverse_event', self.env._(
                'Sospecha de reacción adversa %(name)s (%(severity)s) a %(product)s: notificar '
                'hasta el %(deadline)s.', name=event.name,
                severity=dict(event._fields['severity'].selection)[event.severity],
                product=event.product_id.display_name,
                deadline=fields.Datetime.to_string(event.deadline)), record=event)
        return events

    def action_mark_notified(self):
        self.write({'state': 'notified', 'notified_date': fields.Datetime.now()})

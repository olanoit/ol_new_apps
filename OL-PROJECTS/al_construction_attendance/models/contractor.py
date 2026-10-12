# -*- coding: utf-8 -*-
"""Personal y marcación de las contratas (v1.5, fase 17).

No son trabajadores de la empresa: no entran a la planilla ni al T-Registro.
Marcan en el quiosco de la sede con su documento o PIN; la marcación queda
para la asistencia diaria de la obra y para revisar los avances de las
contratas que reportan trabajo sin haber marcado.
"""
from odoo import api, fields, models
from odoo.exceptions import ValidationError


class ConstructionContractorWorker(models.Model):
    _name = 'construction.contractor.worker'
    _description = 'Personal de contrata'
    _order = 'partner_id, name'
    _check_company_auto = True

    name = fields.Char(string='Nombre', required=True)
    document_number = fields.Char(string='Documento', required=True, index=True)
    pin = fields.Char(string='PIN', groups='al_construction_planner.group_planner_user',
                      help='Opcional: para marcar sin escribir el documento.')
    partner_id = fields.Many2one(
        'res.partner', string='Contrata', required=True, index=True, check_company=True)
    company_id = fields.Many2one(
        'res.company', string='Compañía', required=True, index=True,
        default=lambda self: self.env.company)
    sctr_valid_until = fields.Date(string='SCTR vigente hasta')
    sctr_expired = fields.Boolean(string='SCTR vencido', compute='_compute_sctr_expired')
    active = fields.Boolean(default=True)
    attendance_ids = fields.One2many(
        'construction.contractor.attendance', 'worker_id', string='Marcaciones')

    _document_unique = models.Constraint(
        'UNIQUE(company_id, document_number)',
        'Ya hay una persona de contrata con ese documento.')

    def _compute_sctr_expired(self):
        today = fields.Date.context_today(self)
        for worker in self:
            worker.sctr_expired = not worker.sctr_valid_until or worker.sctr_valid_until < today


class ConstructionContractorAttendance(models.Model):
    _name = 'construction.contractor.attendance'
    _description = 'Marcación de personal de contrata'
    _order = 'check_in desc, id desc'
    _check_company_auto = True

    worker_id = fields.Many2one(
        'construction.contractor.worker', string='Persona', required=True, index=True,
        check_company=True, ondelete='restrict')
    partner_id = fields.Many2one(related='worker_id.partner_id', string='Contrata', store=True,
                                 index=True)
    site_id = fields.Many2one(
        'l10n_pe.hr.construction.site', string='Sede', required=True, index=True,
        check_company=True)
    project_id = fields.Many2one(related='site_id.project_id', string='Obra', store=True, index=True)
    company_id = fields.Many2one(related='worker_id.company_id', store=True, index=True)
    check_in = fields.Datetime(string='Ingreso', required=True, default=fields.Datetime.now)
    check_out = fields.Datetime(string='Salida')
    date = fields.Date(string='Día', compute='_compute_date', store=True, index=True)
    latitude = fields.Float(string='Latitud', digits=(10, 7))
    longitude = fields.Float(string='Longitud', digits=(10, 7))
    distance_m = fields.Float(string='Distancia (m)', compute='_compute_checks', store=True,
                              digits=(12, 1))
    late = fields.Boolean(string='Fuera de hora', compute='_compute_checks', store=True)
    out_of_range = fields.Boolean(string='Fuera de rango', compute='_compute_checks', store=True)
    sctr_expired = fields.Boolean(string='SCTR vencido al marcar', readonly=True)
    mode = fields.Selection(
        [('kiosk', 'Tablet de la sede'), ('portal', 'Portal'), ('manual', 'Manual')],
        string='Modo', default='manual', required=True)

    @api.depends('check_in', 'site_id')
    def _compute_date(self):
        for attendance in self:
            if attendance.check_in and attendance.site_id:
                tz = attendance.site_id._tz()
                attendance.date = fields.Datetime.context_timestamp(
                    attendance.with_context(tz=tz.zone), attendance.check_in).date()
            else:
                attendance.date = attendance.check_in and attendance.check_in.date()

    @api.depends('check_in', 'latitude', 'longitude', 'site_id.latitude', 'site_id.longitude',
                 'site_id.radius_m', 'site_id.entry_deadline')
    def _compute_checks(self):
        for attendance in self:
            site = attendance.site_id
            attendance.distance_m = site._distance_to(attendance.latitude, attendance.longitude) \
                if site else 0.0
            attendance.out_of_range = bool(site) and site._out_of_range(
                attendance.latitude, attendance.longitude)
            attendance.late = bool(site) and site._is_late(attendance.check_in)

    @api.constrains('check_in', 'check_out')
    def _check_dates(self):
        for attendance in self:
            if attendance.check_out and attendance.check_out < attendance.check_in:
                raise ValidationError(self.env._('La salida no puede ser anterior al ingreso.'))

# -*- coding: utf-8 -*-
"""Parte diario de obra (requerimiento CREVAL v1.0, 4.11, pantalla 6): uno por
obra y día, con el clima, el personal propio y por contrata, los trabajos del
día (tomados de los avances registrados), las restricciones, las ocurrencias,
las fotos y la firma del maestro de obra."""
from markupsafe import Markup

from odoo import api, fields, models

WEATHER = [
    ('sunny', 'Soleado'),
    ('cloudy', 'Nublado'),
    ('rain', 'Lluvia'),
    ('wind', 'Viento fuerte'),
]
RESTRICTIONS = [
    ('material', 'Falta de material'),
    ('front', 'Frente no liberado por el cliente'),
    ('weather', 'Lluvia o paralización'),
]


class ConstructionDailyReport(models.Model):
    _name = 'construction.daily.report'
    _description = 'Parte diario de obra'
    _inherit = ['mail.thread']
    _order = 'date desc, id desc'
    _check_company_auto = True

    name = fields.Char(string='Parte', compute='_compute_name', store=True)
    project_id = fields.Many2one('project.project', string='Obra', required=True, index=True,
                                 check_company=True, domain=[('is_construction_site', '=', True)])
    company_id = fields.Many2one(related='project_id.company_id', store=True, index=True)
    date = fields.Date(string='Fecha', required=True, default=fields.Date.context_today,
                       index=True)
    user_id = fields.Many2one('res.users', string='Maestro de obra', required=True,
                              default=lambda self: self.env.user)
    weather = fields.Selection(WEATHER, string='Clima')
    staff_line_ids = fields.One2many('construction.daily.report.staff', 'report_id',
                                     string='Personal en obra')
    staff_total = fields.Integer(string='Personal total', compute='_compute_staff_total',
                                 store=True)
    work_html = fields.Html(string='Trabajos del día', compute='_compute_work_html',
                            sanitize=False)
    restriction_material = fields.Boolean(string='Falta de material')
    restriction_front = fields.Boolean(string='Frente no liberado por el cliente')
    restriction_weather = fields.Boolean(string='Lluvia o paralización')
    occurrences = fields.Text(string='Ocurrencias y visitas')
    attachment_ids = fields.Many2many('ir.attachment', 'construction_daily_report_attachment_rel',
                                      'report_id', 'attachment_id', string='Fotos generales')
    signature = fields.Binary(string='Firma del maestro de obra', attachment=True)
    state = fields.Selection([('draft', 'Borrador'), ('sent', 'Enviado al residente')],
                             string='Estado', default='draft', required=True, tracking=True)

    _project_date_unique = models.UniqueIndex(
        '(project_id, date)', 'La obra ya tiene su parte diario de ese día.')

    @api.depends('project_id', 'date')
    def _compute_name(self):
        for report in self:
            report.name = '%s · %s' % (report.project_id.display_name or '',
                                       report.date or '')

    @api.depends('staff_line_ids.count')
    def _compute_staff_total(self):
        for report in self:
            report.staff_total = sum(report.staff_line_ids.mapped('count'))

    def _day_progress(self):
        self.ensure_one()
        # sudo: el parte muestra los avances de la obra del día, de todos.
        return self.env['construction.task.progress'].sudo().search([
            ('project_id', '=', self.project_id.id), ('date', '=', self.date),
            ('state', '!=', 'rejected')])

    @api.depends('project_id', 'date')
    def _compute_work_html(self):
        for report in self:
            rows = Markup('').join(
                Markup('<li>%s · %s %s%s</li>') % (
                    progress.task_id.display_name, round(progress.qty, 2),
                    progress.activity_id.uom_id.name or '',
                    (' · %s' % progress.partner_id.name) if progress.partner_id else '')
                for progress in report._day_progress()) if report.project_id else ''
            report.work_html = Markup('<ul>%s</ul>') % rows if rows else False


class ConstructionDailyReportStaff(models.Model):
    _name = 'construction.daily.report.staff'
    _description = 'Personal del parte diario'
    _order = 'report_id, id'

    report_id = fields.Many2one('construction.daily.report', string='Parte', required=True,
                                ondelete='cascade', index=True)
    name = fields.Char(string='Cuadrilla o contrata', required=True)
    source = fields.Selection([('own', 'Personal propio'), ('contract', 'Contrata')],
                              string='Origen', required=True, default='own')
    count = fields.Integer(string='Personas')

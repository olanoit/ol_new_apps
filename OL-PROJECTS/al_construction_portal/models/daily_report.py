# -*- coding: utf-8 -*-
"""Partes diarios de obra (requerimiento CREVAL v1.0, 4.11, pantalla 6, y
paquete 6, CR-56).

* **Parte del personal** (``kind = 'member'``): uno por persona, obra y día.
  Lo envían al residente el capataz, la contrata y la oficina técnica: clima,
  personal, trabajos del día, restricciones, ocurrencias, fotos y firma.
* **Parte diario de obra** (``kind = 'site'``): uno por obra y día. Lo arma el
  residente con los partes del día, la asistencia y los avances; al «Cerrar el
  día» sale en PDF al contacto del cliente de la obra y los partes del
  personal quedan «Revisado por el residente»."""
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
REPORT_STATES = [
    ('draft', 'Borrador'),
    ('sent', 'Enviado al residente'),
    ('reviewed', 'Revisado por el residente'),
    ('closed', 'Cerrado y enviado al cliente'),
]


class ConstructionDailyReport(models.Model):
    _name = 'construction.daily.report'
    _description = 'Parte diario de obra'
    _inherit = ['mail.thread']
    _order = 'date desc, kind desc, id desc'
    _check_company_auto = True

    name = fields.Char(string='Parte', compute='_compute_name', store=True)
    kind = fields.Selection(
        [('member', 'Parte del personal'), ('site', 'Parte diario de obra')],
        string='Tipo', required=True, default='member', index=True,
        help='Parte del personal: lo envía cada capataz, contrata u oficina técnica. Parte '
             'diario de obra: el del día de la obra, que el residente cierra y envía al cliente.')
    project_id = fields.Many2one('project.project', string='Obra', required=True, index=True,
                                 check_company=True, domain=[('is_construction_site', '=', True)])
    company_id = fields.Many2one(related='project_id.company_id', store=True, index=True)
    date = fields.Date(string='Fecha', required=True, default=fields.Date.context_today,
                       index=True)
    user_id = fields.Many2one('res.users', string='Enviado por', required=True,
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
    signature = fields.Binary(string='Firma', attachment=True)
    state = fields.Selection(REPORT_STATES, string='Estado', default='draft', required=True,
                             tracking=True)
    # Parte diario de obra (CR-56).
    site_report_id = fields.Many2one(
        'construction.daily.report', string='Parte diario de obra', index='btree_not_null',
        readonly=True, copy=False, ondelete='set null',
        help='El parte del día de la obra en que el residente revisó este parte.')
    member_report_ids = fields.One2many(
        'construction.daily.report', 'site_report_id', string='Partes del personal',
        readonly=True)
    resident_comment = fields.Text(string='Comentario del residente')
    closed_by_id = fields.Many2one('res.users', string='Cerrado por', readonly=True, copy=False)
    closed_at = fields.Datetime(string='Cerrado el', readonly=True, copy=False)
    sent_to_id = fields.Many2one('res.partner', string='Enviado a', readonly=True, copy=False)

    _member_unique = models.UniqueIndex(
        "(project_id, date, user_id) WHERE kind = 'member'",
        'La persona ya envió su parte de ese día en esta obra.')
    _site_unique = models.UniqueIndex(
        "(project_id, date) WHERE kind = 'site'",
        'La obra ya tiene su parte diario de ese día.')

    @api.depends('project_id', 'date', 'kind', 'user_id')
    def _compute_name(self):
        for report in self:
            parts = [report.project_id.display_name or '', str(report.date or '')]
            if report.kind == 'member' and report.user_id:
                parts.append(report.user_id.name)
            report.name = ' · '.join(parts)

    @api.depends('staff_line_ids.count')
    def _compute_staff_total(self):
        for report in self:
            report.staff_total = sum(report.staff_line_ids.mapped('count'))

    def _day_progress(self):
        self.ensure_one()
        # sudo: el parte muestra los avances de la obra del día, de todos.
        return self.env['construction.task.progress'].sudo().search([
            ('project_id', '=', self.project_id.id), ('date', '=', self.date),
            ('state', '!=', 'rejected')], order='state desc, id')

    @api.depends('project_id', 'date')
    def _compute_work_html(self):
        states = dict(self.env['construction.task.progress']._fields['state']._description_selection(
            self.env))
        for report in self:
            rows = Markup('').join(
                Markup('<li>%s · %s %s%s · %s</li>') % (
                    progress.task_id.display_name, round(progress.qty, 2),
                    progress.activity_id.uom_id.name or '',
                    (' · %s' % progress.partner_id.name) if progress.partner_id else '',
                    states.get(progress.state, '').lower())
                for progress in report._day_progress()) if report.project_id else ''
            report.work_html = Markup('<ul>%s</ul>') % rows if rows else False

    # ------------------------------------------------------------------
    # Parte diario de obra (CR-56)
    # ------------------------------------------------------------------
    def _site_summary(self):
        """Lo que el PDF del día dice, armado con los partes revisados, la
        asistencia y los avances del día."""
        self.ensure_one()
        members = self.member_report_ids
        progress = self._day_progress()
        validated = progress.filtered(lambda p: p.state == 'validated')
        pending = progress.filtered(lambda p: p.state == 'draft')
        restrictions = [label for code, label in RESTRICTIONS
                        if any(members.mapped('restriction_%s' % code))]
        occurrences = [(m.user_id.name, m.occurrences) for m in members if m.occurrences]
        photos = (members.attachment_ids | self.attachment_ids
                  | validated.attachment_ids).filtered(
            lambda a: (a.mimetype or '').startswith('image/'))
        weather = dict(WEATHER)
        return {
            'members': members, 'validated': validated, 'pending': pending,
            'restrictions': restrictions, 'occurrences': occurrences,
            'photos': photos[:24], 'staff': self.staff_line_ids,
            'weather': ', '.join(sorted({weather[w] for w in members.mapped('weather') if w}))
            or (weather.get(self.weather) or ''),
        }


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

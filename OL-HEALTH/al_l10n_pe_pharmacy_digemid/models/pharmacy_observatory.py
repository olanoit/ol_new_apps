# -*- coding: utf-8 -*-
"""Observatorio Peruano de Productos Farmacéuticos (DS 014-2011-SA, art. 30;
Ley 29459, art. 28-A): el establecimiento informa el precio de su oferta y lo
actualiza cuando cambia o entra un producto nuevo. Cada cambio de precio de
un producto con código DIGEMID queda «pendiente de informar» hasta que se
exporta."""
from datetime import datetime, time, timedelta

import pytz

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models


class PharmacyObservatoryPrice(models.Model):
    _name = 'pharmacy.observatory.price'
    _description = 'Precio para el Observatorio de productos farmacéuticos'
    _order = 'date desc, id desc'
    _check_company_auto = True

    product_tmpl_id = fields.Many2one('product.template', string='Producto', required=True,
                                      ondelete='cascade', index=True, check_company=True)
    digemid_code = fields.Char(string='Código DIGEMID', required=True)
    date = fields.Datetime(string='Fecha', required=True, default=fields.Datetime.now)
    unit_price = fields.Monetary(string='Precio unitario', currency_field='currency_id')
    package_price = fields.Monetary(string='Precio por empaque', currency_field='currency_id',
                                    help='Precio de la presentación más grande (caja).')
    state = fields.Selection([('pending', 'Pendiente de informar'), ('reported', 'Informado')],
                             string='Estado', default='pending', required=True, index=True)
    reported_date = fields.Datetime(string='Informado el', readonly=True)
    currency_id = fields.Many2one(related='company_id.currency_id')
    company_id = fields.Many2one('res.company', string='Compañía', required=True, readonly=True,
                                 default=lambda self: self.env.company)

    @api.model
    def _pharmacy_register_prices(self, templates):
        """Un pendiente por producto: si ya hay uno, se actualiza el precio."""
        company = self.env.company
        for template in templates:
            box = template.pharmacy_presentation_ids.sorted('factor')[-1:]
            values = {
                'digemid_code': template.pharmacy_digemid_code,
                'unit_price': template.list_price,
                'package_price': box.price if box else template.list_price,
                'date': fields.Datetime.now(),
            }
            pending = self.search([('product_tmpl_id', '=', template.id), ('state', '=', 'pending'),
                                   ('company_id', '=', company.id)], limit=1)
            if pending:
                pending.write(values)
            else:
                self.create({**values, 'product_tmpl_id': template.id, 'company_id': company.id})


class PharmacyPresentation(models.Model):
    _inherit = 'pharmacy.presentation'

    def write(self, vals):
        result = super().write(vals)
        if 'price' in vals:
            self.product_tmpl_id.filtered(lambda t: t.pharmacy_ok and t.pharmacy_digemid_code) \
                ._pharmacy_observatory_register()
        return result


def add_business_days(day, days, holidays=()):
    """``days`` días hábiles después de ``day``: de lunes a viernes, sin los
    días de ``holidays``."""
    while days > 0:
        day += timedelta(days=1)
        if day.weekday() < 5 and day not in holidays:
            days -= 1
    return day


class ResCompany(models.Model):
    _inherit = 'res.company'

    def _pharmacy_holidays(self, date_from, date_to):
        """Feriados entre dos fechas: las ausencias globales (sin recurso) del
        calendario laboral de la compañía, como en Empleados ‣ Configuración ‣
        Horarios de trabajo. Del calendario no cuenta el horario, solo los
        feriados: los días hábiles son de lunes a viernes."""
        self.ensure_one()
        calendar = self.resource_calendar_id
        if not calendar:
            return set()
        tz = pytz.timezone(calendar.tz or 'America/Lima')
        start = tz.localize(datetime.combine(date_from, time.min)).astimezone(pytz.utc).replace(tzinfo=None)
        end = tz.localize(datetime.combine(date_to, time.max)).astimezone(pytz.utc).replace(tzinfo=None)
        # sudo: los feriados son configuración de Recursos Humanos que el
        # director técnico puede no ver; solo se leen sus fechas.
        leaves_sudo = self.env['resource.calendar.leaves'].sudo().search([
            ('calendar_id', 'in', (calendar.id, False)), ('resource_id', '=', False),
            ('company_id', 'in', (self.id, False)),
            ('date_from', '<=', end), ('date_to', '>=', start)])
        holidays = set()
        for leave_sudo in leaves_sudo:
            day = pytz.utc.localize(leave_sudo.date_from).astimezone(tz).date()
            # Una ausencia que termina a las 00:00 no toma el día siguiente.
            last = pytz.utc.localize(leave_sudo.date_to - timedelta(seconds=1)).astimezone(tz).date()
            while day <= last:
                holidays.add(day)
                day += timedelta(days=1)
        return holidays

    def _pharmacy_add_business_days(self, day, days):
        """Fecha a ``days`` días hábiles de ``day``, sin los feriados de la
        compañía (se miran hasta dos meses adelante)."""
        self.ensure_one()
        return add_business_days(day, days, self._pharmacy_holidays(day, day + timedelta(days=60)))


class PharmacyObservatorySubmission(models.Model):
    """Envío mensual de precios de un local al Observatorio (Directiva
    176-MINSA/DIGEMID): al menos una carga al mes, la primera con toda la
    oferta (reemplaza la lista) y las siguientes solo con los cambios.
    Después de cada carga hay una sola rectificación dentro de los 7 días
    hábiles siguientes."""
    _name = 'pharmacy.observatory.submission'
    _description = 'Envío de precios al Observatorio'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'period desc, date_sent desc, id desc'
    _check_company_auto = True

    name = fields.Char(string='Envío', compute='_compute_name', store=True)
    warehouse_id = fields.Many2one('stock.warehouse', string='Local', required=True,
                                   check_company=True, index=True)
    establishment_code = fields.Char(string='Código de establecimiento',
                                     related='warehouse_id.pharmacy_establishment_code')
    period = fields.Date(string='Mes', required=True, index=True,
                         help='Primer día del mes que se informa.')
    state = fields.Selection([('draft', 'Por informar'), ('sent', 'Informado')],
                             string='Estado', default='draft', required=True, tracking=True)
    mode = fields.Selection([('full', 'Carga completa del mes'), ('changes', 'Solo cambios')],
                            string='Tipo de carga', readonly=True)
    date_sent = fields.Datetime(string='Exportado el', readonly=True)
    user_id = fields.Many2one('res.users', string='Exportado por', readonly=True)
    line_count = fields.Integer(string='Productos', readonly=True)
    rectification_deadline = fields.Date(
        string='Rectificación hasta', readonly=True,
        help='Una sola rectificación dentro de los 7 días hábiles siguientes a la carga '
             '(sin los feriados del calendario laboral de la compañía).')
    file_data = fields.Binary(string='Archivo', readonly=True, attachment=True)
    file_name = fields.Char(readonly=True)
    company_id = fields.Many2one('res.company', string='Compañía', required=True, readonly=True,
                                 default=lambda self: self.env.company)

    @api.depends('warehouse_id', 'period', 'mode')
    def _compute_name(self):
        for submission in self:
            submission.name = '%s · %s' % (
                submission.period and submission.period.strftime('%m/%Y') or '',
                submission.warehouse_id.name or '')

    @api.model
    def _month_start(self, day=None):
        day = day or fields.Date.context_today(self)
        return day.replace(day=1)

    @api.model
    def _last_sent(self, warehouse):
        return self.search([('warehouse_id', '=', warehouse.id), ('state', '=', 'sent')],
                           order='date_sent desc', limit=1)

    @api.model
    def _has_full_this_month(self, warehouse):
        return bool(self.search_count([
            ('warehouse_id', '=', warehouse.id), ('state', '=', 'sent'), ('mode', '=', 'full'),
            ('period', '=', self._month_start())]))

    @api.model
    def _cron_monthly_reminder(self):
        """Desde el día de recordatorio de la compañía, un envío «por informar»
        del mes con una actividad para el director técnico de cada local con
        código de establecimiento que aún no informó."""
        activity_type = self.env.ref('mail.mail_activity_data_todo', raise_if_not_found=False)
        warehouses = self.env['stock.warehouse'].search([('pharmacy_establishment_code', '!=', False)])
        for warehouse in warehouses:
            company = warehouse.company_id
            today = fields.Date.context_today(self.with_company(company))
            if today.day < (company.pharmacy_observatory_reminder_day or 1):
                continue
            Submission = self.with_company(company)
            month = Submission._month_start(today)
            if Submission.search_count([('warehouse_id', '=', warehouse.id), ('period', '=', month)]):
                continue
            submission = Submission.create({'warehouse_id': warehouse.id, 'period': month,
                                            'company_id': company.id})
            user = warehouse.pharmacy_director_id.user_id
            if user and activity_type:
                submission.activity_schedule(
                    activity_type_id=activity_type.id, user_id=user.id,
                    date_deadline=month + relativedelta(months=1, days=-1),
                    summary=self.env._('Informar precios al Observatorio'),
                    note=self.env._('El local %(warehouse)s no informó sus precios de %(month)s: '
                                    'exporte la carga completa del mes.',
                                    warehouse=warehouse.name, month=month.strftime('%m/%Y')))

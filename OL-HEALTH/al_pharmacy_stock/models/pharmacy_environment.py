# -*- coding: utf-8 -*-
"""Control de temperatura y humedad (BPOF 7.5.1.14-7.5.1.26): puntos de
control (ambiente, refrigeradora) con sus rangos, lecturas con acción
correctiva obligatoria fuera de rango y recordatorio diario."""
from odoo import api, fields, models
from odoo.exceptions import ValidationError


class PharmacyEnvironmentPoint(models.Model):
    _name = 'pharmacy.environment.point'
    _description = 'Punto de control ambiental'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'warehouse_id, name'
    _check_company_auto = True

    name = fields.Char(string='Punto de control', required=True,
                       help='Por ejemplo «Sala de ventas» o «Refrigeradora 1».')
    warehouse_id = fields.Many2one('stock.warehouse', string='Local', required=True,
                                   check_company=True)
    location_id = fields.Many2one('stock.location', string='Ubicación', check_company=True)
    point_type = fields.Selection([
        ('ambient', 'Ambiente'),
        ('cold', 'Cadena de frío (2 °C a 8 °C)'),
    ], string='Tipo', required=True, default='ambient')
    temp_min = fields.Float(string='Temperatura mínima (°C)', default=15.0)
    temp_max = fields.Float(string='Temperatura máxima (°C)', default=30.0)
    humidity_max = fields.Float(string='Humedad máxima (%)', default=70.0,
                                help='Cero si no se controla la humedad.')
    equipment = fields.Char(string='Equipo', help='Termohigrómetro o data logger y su serie.')
    calibration_date = fields.Date(string='Última calibración')
    next_calibration_date = fields.Date(string='Próxima calibración')
    responsible_id = fields.Many2one('res.users', string='Responsable',
                                     default=lambda self: self.env.user)
    reading_ids = fields.One2many('pharmacy.environment.reading', 'point_id', string='Lecturas')
    last_reading_date = fields.Datetime(compute='_compute_last_reading', string='Última lectura')
    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', string='Compañía', required=True, readonly=True,
                                 default=lambda self: self.env.company)

    @api.onchange('point_type')
    def _onchange_point_type(self):
        if self.point_type == 'cold':
            self.temp_min, self.temp_max, self.humidity_max = 2.0, 8.0, 0.0
        else:
            self.temp_min, self.temp_max, self.humidity_max = 15.0, 30.0, 70.0

    @api.constrains('temp_min', 'temp_max')
    def _check_range(self):
        for point in self:
            if point.temp_min >= point.temp_max:
                raise ValidationError(self.env._('La temperatura mínima debe ser menor que la máxima.'))

    def _compute_last_reading(self):
        for point in self:
            point.last_reading_date = max(point.reading_ids.mapped('date'), default=False)

    @api.model
    def _cron_pharmacy_reading_reminder(self):
        """Actividad para el responsable de cada punto sin lectura hoy."""
        today_start = fields.Datetime.to_datetime(fields.Date.context_today(self))
        Reading = self.env['pharmacy.environment.reading']
        activity_type = self.env.ref('mail.mail_activity_data_todo')
        for point in self.search([]):
            if Reading.search_count([('point_id', '=', point.id), ('date', '>=', today_start)],
                                    limit=1):
                continue
            if point.activity_ids.filtered(lambda a: a.activity_type_id == activity_type
                                           and a.date_deadline == fields.Date.context_today(self)):
                continue
            point.activity_schedule(
                activity_type_id=activity_type.id,
                summary=self.env._('Registrar temperatura y humedad de hoy'),
                user_id=(point.responsible_id or self.env.user).id)


class PharmacyEnvironmentReading(models.Model):
    _name = 'pharmacy.environment.reading'
    _description = 'Lectura de temperatura y humedad'
    _order = 'date desc, id desc'
    _check_company_auto = True

    point_id = fields.Many2one('pharmacy.environment.point', string='Punto de control',
                               required=True, ondelete='restrict', check_company=True)
    date = fields.Datetime(string='Fecha y hora', required=True, default=fields.Datetime.now)
    temperature = fields.Float(string='Temperatura (°C)', required=True)
    humidity = fields.Float(string='Humedad (%)')
    user_id = fields.Many2one('res.users', string='Registró', required=True, readonly=True,
                              default=lambda self: self.env.user)
    out_of_range = fields.Boolean(string='Fuera de rango', compute='_compute_out_of_range',
                                  store=True)
    corrective_action = fields.Text(
        string='Acción correctiva',
        help='Obligatoria si la lectura está fuera de rango (BPOF 7.5.1.26).')
    company_id = fields.Many2one(related='point_id.company_id', store=True, index=True)

    @api.depends('temperature', 'humidity', 'point_id.temp_min', 'point_id.temp_max',
                 'point_id.humidity_max')
    def _compute_out_of_range(self):
        for reading in self:
            point = reading.point_id
            reading.out_of_range = bool(point) and (
                not point.temp_min <= reading.temperature <= point.temp_max
                or (point.humidity_max and reading.humidity > point.humidity_max))

    @api.constrains('out_of_range', 'corrective_action')
    def _check_corrective_action(self):
        for reading in self:
            if reading.out_of_range and not (reading.corrective_action or '').strip():
                raise ValidationError(self.env._(
                    'La lectura de %(point)s está fuera de rango: registre la acción correctiva.',
                    point=reading.point_id.name))

    @api.model_create_multi
    def create(self, vals_list):
        readings = super().create(vals_list)
        for reading in readings.filtered('out_of_range'):
            self.env['pharmacy.logbook.entry']._log(
                'incident', self.env._(
                    'Lectura fuera de rango en %(point)s: %(temp)s °C, %(hum)s %%. Acción: '
                    '%(action)s', point=reading.point_id.name, temp=reading.temperature,
                    hum=reading.humidity, action=reading.corrective_action),
                warehouse=reading.point_id.warehouse_id, record=reading)
        return readings

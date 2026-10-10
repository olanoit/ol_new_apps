# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import ValidationError
from odoo.fields import Domain

from .common import ML_GROUPS, STAGES


class ConstructionLaborActivity(models.Model):
    """Actividad de contrata o de personal propio: su unidad es el driver de
    pago (módulo armado, metro lineal instalado, tapa colocada…)."""
    _name = 'construction.labor.activity'
    _description = 'Actividad de obra (driver de pago)'
    _order = 'stage, sequence, name'
    _check_company_auto = True

    code = fields.Char(string='Código', required=True)
    name = fields.Char(string='Nombre', required=True, translate=True)
    sequence = fields.Integer(string='Secuencia', default=10)
    active = fields.Boolean(string='Activo', default=True)
    company_id = fields.Many2one(
        'res.company', string='Compañía', index=True, default=lambda self: self.env.company,
        help='La activa al crearla. Vacía (solo por importación): se comparte entre compañías.')
    stage = fields.Selection(STAGES, string='Etapa', required=True)
    uom_id = fields.Many2one(
        'uom.uom', string='Unidad del driver', required=True,
        help='Unidad en la que la contrata reporta su avance y cobra (UND, ML…).')
    product_id = fields.Many2one(
        'product.product', string='Producto de servicio', check_company=True,
        domain=[('type', '=', 'service')],
        help='Servicio de recepción manual que va en la OC de servicio de la contrata.')
    module_level = fields.Boolean(
        string='Se mide por módulo',
        help='Una unidad por módulo (armado): la línea del plan cuelga del módulo.')
    ml_based = fields.Boolean(
        string='Se mide por ML',
        help='Se mide en metros lineales de mueble: cuelga del módulo si se conoce su '
             'ancho; si no, del ambiente.')
    ml_group = fields.Selection(
        ML_GROUPS, string='Grupo ML', default='none',
        help='Qué metros lineales mide: los de mueble bajo o los de mueble alto.')
    default_price = fields.Monetary(
        string='Tarifa base', currency_field='currency_id',
        help='Tarifa si no hay una tarifa vigente de la obra o de la contrata.')
    currency_id = fields.Many2one(
        'res.currency', string='Moneda', compute='_compute_currency_id')
    role_id = fields.Many2one('planning.role', string='Rol', help='Personal propio.')
    productivity = fields.Float(string='Rendimiento', help='Unidades de driver por hora.')
    productivity_source = fields.Selection(
        [('estimated', 'Estimado'), ('measured', 'Medido')], string='Origen del rendimiento',
        default='estimated')
    rate_ids = fields.One2many('construction.labor.rate', 'activity_id', string='Tarifas')

    _code_company_unique = models.Constraint(
        'UNIQUE(code, company_id)', 'El código de la actividad debe ser único por compañía.')

    @api.depends('company_id')
    def _compute_currency_id(self):
        for activity in self:
            activity.currency_id = (activity.company_id or self.env.company).currency_id

    @api.constrains('module_level', 'ml_based')
    def _check_measure(self):
        for activity in self:
            if activity.module_level and activity.ml_based:
                raise ValidationError(self.env._(
                    'La actividad %s se mide por módulo o por ML, no por ambos.', activity.name))

    @api.depends('code', 'name')
    def _compute_display_name(self):
        for activity in self:
            activity.display_name = activity.name or activity.code

    def _get_rate(self, project=None, partner=None, date=None):
        """Tarifa vigente de la actividad. Prioridad: obra y contrata, solo
        obra, solo contrata, tarifa base de la actividad (especificación,
        construction.labor.rate). Devuelve ``(precio, % de retención, tarifa)``."""
        self.ensure_one()
        date = date or fields.Date.context_today(self)
        rates = self.env['construction.labor.rate'].search(Domain.AND([
            [('activity_id', '=', self.id)],
            ['|', ('date_from', '=', False), ('date_from', '<=', date)],
            ['|', ('date_to', '=', False), ('date_to', '>=', date)],
            [('company_id', 'in', ((project and project.company_id) or self.env.company).ids)],
        ]))
        candidates = [
            (bool(project and partner),
             lambda r: r.project_id == project and r.partner_id == partner),
            (bool(project), lambda r: r.project_id == project and not r.partner_id),
            (bool(partner), lambda r: not r.project_id and r.partner_id == partner),
            (True, lambda r: not r.project_id and not r.partner_id),
        ]
        for applies, match in candidates:
            if not applies:
                continue
            rate = rates.filtered(match)[:1]
            if rate:
                return rate.price, rate.retention_pct, rate
        return self.default_price, 0.0, self.env['construction.labor.rate']


class ConstructionLaborRate(models.Model):
    """Tarifa de una actividad, general o de una obra o contrata, con vigencia."""
    _name = 'construction.labor.rate'
    _description = 'Tarifa de contrata'
    _order = 'activity_id, project_id, partner_id, date_from desc'
    _check_company_auto = True

    activity_id = fields.Many2one(
        'construction.labor.activity', string='Actividad', required=True,
        ondelete='cascade', index=True, check_company=True)
    uom_id = fields.Many2one(related='activity_id.uom_id', string='Unidad del driver')
    company_id = fields.Many2one(
        'res.company', string='Compañía', required=True, index=True, readonly=True,
        default=lambda self: self.env.company)
    currency_id = fields.Many2one(related='company_id.currency_id', string='Moneda')
    project_id = fields.Many2one(
        'project.project', string='Obra', index=True, check_company=True,
        help='Vacía: la tarifa vale para cualquier obra.')
    partner_id = fields.Many2one(
        'res.partner', string='Contrata', index=True, check_company=True,
        help='Vacía: la tarifa vale para cualquier contrata.')
    price = fields.Monetary(string='Tarifa', required=True, currency_field='currency_id')
    retention_pct = fields.Float(
        string='Retención (%)', digits=(5, 2),
        help='Porcentaje del monto que se retiene a la contrata en cada liquidación.')
    date_from = fields.Date(string='Vigente desde')
    date_to = fields.Date(string='Vigente hasta')

    @api.constrains('date_from', 'date_to')
    def _check_dates(self):
        for rate in self:
            if rate.date_from and rate.date_to and rate.date_from > rate.date_to:
                raise ValidationError(self.env._('La vigencia de la tarifa termina antes de empezar.'))

    @api.constrains('activity_id', 'project_id', 'partner_id', 'date_from', 'date_to', 'company_id')
    def _check_overlap(self):
        """Sin superposición de vigencias para la misma actividad, obra y contrata."""
        for rate in self:
            others = self.search([
                ('id', '!=', rate.id),
                ('activity_id', '=', rate.activity_id.id),
                ('project_id', '=', rate.project_id.id),
                ('partner_id', '=', rate.partner_id.id),
                ('company_id', '=', rate.company_id.id),
            ])
            start = rate.date_from or fields.Date.to_date('1900-01-01')
            end = rate.date_to or fields.Date.to_date('9999-12-31')
            for other in others:
                o_start = other.date_from or fields.Date.to_date('1900-01-01')
                o_end = other.date_to or fields.Date.to_date('9999-12-31')
                if start <= o_end and o_start <= end:
                    raise ValidationError(self.env._(
                        'La tarifa de %(activity)s se superpone con otra vigente para la '
                        'misma obra y contrata.', activity=rate.activity_id.display_name))

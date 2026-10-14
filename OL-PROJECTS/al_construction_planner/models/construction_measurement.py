# -*- coding: utf-8 -*-
"""Metrado del ambiente (v1.6, M16-03 y M16-04).

El supervisor registra la medida real del ambiente en la unidad de cada
driver (ML de mueble bajo, ML de mueble alto y módulos) frente a lo
planificado. La diferencia se valoriza con el costo por unidad de driver de
las líneas de contrata y personal propio del plan vigente que dependen de ese
driver. Un metrado con diferencia pasa por la validación por niveles antes de
lanzar la orden de fabricación del ambiente (W-04)."""
from lxml import etree
from markupsafe import Markup

from odoo import api, fields, models
from odoo.exceptions import UserError

from .construction_resource_plan import OPEN_STATES

MEASUREMENT_STATES = [
    ('draft', 'Borrador'),
    ('submitted', 'En aprobación'),
    ('approved', 'Aprobado'),
]
# Las medidas van con dos decimales: por debajo de medio centésimo no hay
# diferencia.
DIFFERENCE_TOLERANCE = 0.005


def _is_zero(qty):
    return abs(qty) < DIFFERENCE_TOLERANCE


MEASUREMENT_DRIVERS = [
    ('ml_low', 'ML de mueble bajo'),
    ('ml_high', 'ML de mueble alto'),
    ('units', 'Módulos'),
]


class ConstructionMeasurement(models.Model):
    _name = 'construction.measurement'
    _description = 'Metrado del ambiente'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'tier.validation']
    _order = 'date desc, id desc'
    _check_company_auto = True
    # Aprobación por niveles (jefatura de proyectos) del metrado con
    # diferencia; sin diferencia se aprueba al enviarlo.
    _state_from = ['submitted']
    _state_to = ['approved']
    _cancel_state = 'draft'
    _tier_validation_manual_config = False

    _task_unique = models.Constraint(
        'unique(task_id)', 'Cada ambiente tiene un solo metrado: corrija el existente.')

    name = fields.Char(string='Número', required=True, readonly=True, copy=False, default='/')
    task_id = fields.Many2one(
        'project.task', string='Ambiente', required=True, index=True, check_company=True,
        domain="[('construction_level', '=', 'space')]", tracking=True)
    project_id = fields.Many2one(
        related='task_id.project_id', string='Obra', store=True, index=True)
    floor_task_id = fields.Many2one(
        related='task_id.construction_floor_task_id', string='Piso', store=True, index=True)
    apartment_task_id = fields.Many2one(
        related='task_id.construction_apartment_task_id', string='Departamento', store=True)
    typology_id = fields.Many2one(
        related='task_id.construction_typology_id', string='Tipología', store=True)
    company_id = fields.Many2one(
        'res.company', string='Compañía', compute='_compute_company_id', store=True, index=True,
        precompute=True)
    plan_id = fields.Many2one(
        'construction.resource.plan', string='Plan', readonly=True, check_company=True,
        help='Plan vigente de la obra cuando se creó el metrado: de él salen lo planificado y '
             'el costo por unidad de driver.')
    user_id = fields.Many2one(
        'res.users', string='Supervisor', default=lambda self: self.env.user, tracking=True)
    date = fields.Date(string='Fecha', required=True, default=fields.Date.context_today)
    state = fields.Selection(
        MEASUREMENT_STATES, string='Estado', required=True, default='draft', tracking=True,
        copy=False)
    line_ids = fields.One2many(
        'construction.measurement.line', 'measurement_id', string='Medidas', copy=True)
    has_difference = fields.Boolean(
        string='Con diferencia', compute='_compute_totals', store=True,
        help='Alguna medida difiere de lo planificado: hay que aprobarla antes de lanzar la '
             'orden de fabricación del ambiente.')
    amount_difference = fields.Monetary(
        string='Diferencia en soles', compute='_compute_totals', store=True,
        currency_field='currency_id')
    currency_id = fields.Many2one(related='company_id.currency_id', string='Moneda')
    note = fields.Text(string='Observaciones')

    @api.depends('task_id.company_id', 'task_id.project_id.company_id')
    def _compute_company_id(self):
        # En Odoo 19 la obra puede no tener compañía: la de la tarea, la de la
        # obra o la activa (como las variantes de la unidad).
        for measurement in self:
            measurement.company_id = measurement.task_id.company_id \
                or measurement.task_id.project_id.company_id or self.env.company

    @api.depends('line_ids.qty_difference', 'line_ids.amount_difference')
    def _compute_totals(self):
        for measurement in self:
            lines = measurement.line_ids
            measurement.has_difference = any(not _is_zero(line.qty_difference) for line in lines)
            measurement.amount_difference = sum(lines.mapped('amount_difference'))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', '/') == '/':
                vals['name'] = self.env['ir.sequence'].next_by_code('construction.measurement') or '/'
        measurements = super().create(vals_list)
        for measurement in measurements.filtered(lambda m: not m.line_ids):
            measurement._fill_from_plan()
        return measurements

    # ------------------------------------------------------------------
    # Lo planificado
    # ------------------------------------------------------------------
    def _current_plan(self):
        self.ensure_one()
        return self.env['construction.resource.plan'].search([
            ('project_id', '=', self.project_id.id), ('state', 'in', OPEN_STATES)], limit=1)

    def _planned_driver_qty(self):
        """{driver: cantidad planificada} del ambiente: los ML de su
        tipología y la cantidad de módulos del ambiente."""
        self.ensure_one()
        space = self.task_id
        typology = space.construction_typology_id
        modules = self.env['project.task'].search_count([
            ('construction_space_task_id', '=', space.id), ('construction_level', '=', 'module')])
        return {'ml_low': typology.ml_low, 'ml_high': typology.ml_high, 'units': modules}

    def _driver_lines(self, plan, driver):
        """Líneas de contrata y personal propio del ambiente que dependen del
        driver en ``plan``."""
        self.ensure_one()
        lines = self.env['construction.resource.plan.line'].search([
            ('plan_id', '=', plan.id), ('space_task_id', '=', self.task_id.id),
            ('resource_type', 'in', ('contract', 'labor')), ('activity_id', '!=', False)])
        if driver == 'units':
            return lines.filtered(lambda l: l.activity_id.module_level)
        group = 'low' if driver == 'ml_low' else 'high'
        return lines.filtered(lambda l: l.activity_id.ml_based and l.activity_id.ml_group == group)

    def _fill_from_plan(self):
        """Una medida por driver con lo planificado y el costo por unidad de
        driver; la medida real empieza igual a lo planificado."""
        self.ensure_one()
        plan = self._current_plan()
        planned = self._planned_driver_qty()
        values = []
        for driver, _label in MEASUREMENT_DRIVERS:
            qty = planned[driver]
            if not qty:
                continue
            amount = sum(self._driver_lines(plan, driver).mapped('amount_planned')) if plan else 0.0
            values.append({
                'driver': driver,
                'qty_planned': qty,
                'qty_measured': qty,
                'unit_amount': amount / qty,
            })
        self.write({'plan_id': plan.id, 'line_ids': [(0, 0, vals) for vals in values]})

    # ------------------------------------------------------------------
    # Flujo
    # ------------------------------------------------------------------
    def _check_state(self, states):
        for measurement in self:
            if measurement.state not in states:
                raise UserError(self.env._(
                    'El metrado %(name)s está %(state)s: esta acción no se puede hacer.',
                    name=measurement.name,
                    state=dict(MEASUREMENT_STATES)[measurement.state].lower()))

    def action_submit(self):
        """Sin diferencia, se aprueba; con diferencia, pide las revisiones de
        la jefatura (tier validation). Sin reglas que apliquen, se aprueba."""
        self._check_state(('draft',))
        self.write({'state': 'submitted'})
        for measurement in self:
            reviews = False
            if measurement.has_difference and measurement.need_validation:
                reviews = measurement.request_validation()
            if not reviews:
                measurement._action_approve()

    def _validate_tier(self, tiers=False):
        res = super()._validate_tier(tiers)
        if not self.env.context.get('al_construction_approving'):
            for measurement in self:
                if measurement.state == 'submitted' and measurement.validation_status == 'validated':
                    measurement._action_approve()
        return res

    def _rejected_tier(self, tiers=False):
        res = super()._rejected_tier(tiers)
        for measurement in self:
            if measurement.state == 'submitted' and measurement.validation_status == 'rejected':
                # Lo escribe el revisor, que no puede editar el metrado en
                # revisión: se omite ese control solo para el estado.
                measurement.with_context(skip_validation_check=True).write({'state': 'draft'})
                measurement.message_post(body=self.env._(
                    'Rechazado por la jefatura: vuelve a borrador para corregir la medida.'))
        return res

    def _action_approve(self):
        # need_validation no tiene depends: su caché conserva el valor de
        # antes de las revisiones.
        self.invalidate_recordset(['need_validation', 'review_ids', 'validation_status'])
        for measurement in self:
            measurement.with_context(al_construction_approving=True).write({'state': 'approved'})
            if measurement.has_difference:
                measurement.message_post(body=Markup(self.env._(
                    'Metrado aprobado con una diferencia de <b>%(amount)s</b>: ya se puede lanzar '
                    'la orden de fabricación del ambiente.',
                    amount=measurement.currency_id.format(measurement.amount_difference))))

    def action_draft(self):
        """Volver a borrador para corregir la medida: se descartan las
        revisiones y hay que enviarlo de nuevo."""
        self._check_state(('submitted', 'approved'))
        if self.env['mrp.production'].search_count([
                ('construction_space_task_ids', 'in', self.task_id.ids), ('state', '!=', 'cancel')]):
            raise UserError(self.env._(
                'El ambiente ya tiene una orden de fabricación: el metrado no se puede reabrir.'))
        self.restart_validation()
        self.write({'state': 'draft'})

    @api.ondelete(at_uninstall=False)
    def _unlink_only_draft(self):
        if any(measurement.state != 'draft' for measurement in self):
            raise UserError(self.env._('Solo se puede borrar un metrado en borrador.'))

    def _get_to_validate_message(self):
        # El es.po de base_tier_validation no traduce este aviso.
        icon = Markup('<i class="fa fa-lg fa-info-circle"></i>')
        pending = self.review_ids.filtered(lambda r: r.status == 'pending')[:1]
        if pending and pending.todo_by:
            text = self.env._('Pendiente de aprobación por %s', pending.todo_by)
        else:
            text = self.env._('Este metrado necesita aprobación')
        return Markup('%s %s') % (icon, text)

    @api.model
    def get_view(self, view_id=None, view_type='form', **options):
        """Quita los botones OCA «Request/Restart Validation»: las revisiones
        se piden al enviar el metrado."""
        res = super().get_view(view_id=view_id, view_type=view_type, **options)
        if view_type == 'form':
            doc = etree.XML(res['arch'])
            for node in doc.xpath(
                    "//button[@name='request_validation' or @name='restart_validation']"):
                node.getparent().remove(node)
            res['arch'] = etree.tostring(doc, encoding='unicode')
        return res

    @api.model
    def _construction_blocked_spaces(self, spaces):
        """Ambientes con un metrado con diferencia que todavía no está
        aprobado: su orden de fabricación espera la aprobación (M16-04)."""
        return self.search([
            ('task_id', 'in', spaces.ids), ('has_difference', '=', True),
            ('state', '!=', 'approved')]).task_id


class ConstructionMeasurementLine(models.Model):
    _name = 'construction.measurement.line'
    _description = 'Medida del metrado'
    _order = 'measurement_id, driver'
    _check_company_auto = True

    measurement_id = fields.Many2one(
        'construction.measurement', string='Metrado', required=True, ondelete='cascade',
        index=True, check_company=True)
    company_id = fields.Many2one(
        related='measurement_id.company_id', string='Compañía', store=True, index=True)
    task_id = fields.Many2one(
        related='measurement_id.task_id', string='Ambiente', store=True, index=True)
    floor_task_id = fields.Many2one(
        related='measurement_id.floor_task_id', string='Piso', store=True)
    state = fields.Selection(related='measurement_id.state', string='Estado', store=True)
    driver = fields.Selection(MEASUREMENT_DRIVERS, string='Driver', required=True)
    qty_planned = fields.Float(string='Planificado', digits=(16, 2), readonly=True)
    qty_measured = fields.Float(
        string='Medido', digits=(16, 2), required=True,
        help='La medida real del ambiente en la unidad del driver.')
    qty_difference = fields.Float(
        string='Diferencia', digits=(16, 2), compute='_compute_difference', store=True)
    unit_amount = fields.Float(
        string='Costo por unidad', readonly=True, digits=(16, 4),
        help='Monto planificado de las líneas de contrata y personal propio que dependen de este '
             'driver, entre lo planificado.')
    amount_difference = fields.Monetary(
        string='Diferencia en soles', compute='_compute_difference', store=True,
        currency_field='currency_id')
    currency_id = fields.Many2one(related='measurement_id.currency_id', string='Moneda')

    _driver_unique = models.Constraint(
        'unique(measurement_id, driver)', 'Cada driver va una sola vez en el metrado.')

    @api.depends('qty_planned', 'qty_measured', 'unit_amount')
    def _compute_difference(self):
        for line in self:
            line.qty_difference = round(line.qty_measured - line.qty_planned, 2)
            line.amount_difference = line.currency_id.round(line.qty_difference * line.unit_amount) \
                if line.currency_id else line.qty_difference * line.unit_amount

    def write(self, vals):
        if 'qty_measured' in vals and any(line.state != 'draft' for line in self):
            raise UserError(self.env._(
                'La medida solo se corrige en borrador: vuelva el metrado a borrador.'))
        return super().write(vals)

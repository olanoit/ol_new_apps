# -*- coding: utf-8 -*-
"""Datos de construcción civil en la versión del trabajador.

El jornal **no se escribe a mano**: se calcula desde la tabla salarial
vigente a la fecha de la versión. Así, cuando entra un convenio nuevo,
basta con cargar su tabla; no hay que reescribir el jornal de trescientos
trabajadores ni queda nadie con el importe del año pasado.
"""
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class HrVersion(models.Model):
    _inherit = 'hr.version'

    l10n_pe_construction_category_id = fields.Many2one(
        'l10n_pe.hr.construction.category',
        string='Categoría (construcción)', tracking=True,
        help='Operario, oficial o peón. De ella salen el jornal y el '
             'porcentaje de BUC.')
    l10n_pe_construction_site_id = fields.Many2one(
        'l10n_pe.hr.construction.site', string='Obra',
        check_company=True, tracking=True,
        help='En este régimen el vínculo es por obra determinada.')
    l10n_pe_construction_bae_id = fields.Many2one(
        'l10n_pe.hr.construction.bonus', string='Especialidad (BAE)',
        domain=[('bonus_type', '=', 'bae')],
        help='Solo para operarios: operador de equipo mediano o pesado, '
             'electromecánico, topógrafo…')
    l10n_pe_construction_bonus_ids = fields.Many2many(
        'l10n_pe.hr.construction.bonus',
        'l10n_pe_version_construction_bonus_rel', 'version_id', 'bonus_id',
        string='Bonificaciones del puesto',
        domain=[('bonus_type', '=', 'condition')],
        help='Las que dependen del puesto y no de la obra. Las de la obra '
             'se suman solas.')

    l10n_pe_sctr_health = fields.Boolean(
        string='Cobertura SCTR salud',
        help='El T-Registro solo pide la cobertura de pensión; la de '
             'salud hace falta para calcular su aporte en planilla.')
    l10n_pe_daily_wage = fields.Monetary(
        string='Jornal básico', compute='_compute_l10n_pe_construction',
        currency_field='currency_id',
        help='Sale de la tabla salarial vigente a la fecha de la versión, '
             'según la categoría.')
    l10n_pe_wage_line_id = fields.Many2one(
        'l10n_pe.hr.construction.wage.line', string='Línea de la tabla',
        compute='_compute_l10n_pe_construction',
        help='Fila del convenio de la que sale el jornal.')
    l10n_pe_is_construction = fields.Boolean(
        string='Es construcción civil',
        compute='_compute_l10n_pe_is_construction', store=True)

    @api.depends('l10n_pe_labor_regime')
    def _compute_l10n_pe_is_construction(self):
        for version in self:
            version.l10n_pe_is_construction = (
                version.l10n_pe_labor_regime == 'construccion')

    @api.depends('l10n_pe_construction_category_id', 'date_version',
                 'company_id')
    def _compute_l10n_pe_construction(self):
        Table = self.env['l10n_pe.hr.construction.wage.table']
        for version in self:
            line = version._l10n_pe_get_wage_line(Table=Table)
            version.l10n_pe_wage_line_id = line
            version.l10n_pe_daily_wage = line.daily_wage if line else 0.0

    def _l10n_pe_get_wage_line(self, on_date=None, Table=None):
        """Fila del convenio para la categoría y la fecha dadas.

        Se resuelve por fecha —y no una sola vez— porque una boleta de
        marzo tiene que seguir usando el jornal de marzo aunque en abril
        entre un convenio nuevo.
        """
        self.ensure_one()
        category = self.l10n_pe_construction_category_id
        if not category:
            return self.env['l10n_pe.hr.construction.wage.line']
        Table = Table or self.env['l10n_pe.hr.construction.wage.table']
        on_date = on_date or self.date_version or fields.Date.context_today(
            self)
        table = Table._get_table_for_date(on_date, self.company_id)
        return table.line_ids.filtered(
            lambda line: line.category_id == category)[:1]

    def _l10n_pe_construction_bonuses(self):
        """Bonificaciones que le corresponden: las del puesto, las de la
        obra y su BAE."""
        self.ensure_one()
        bonuses = (self.l10n_pe_construction_bonus_ids
                   | self.l10n_pe_construction_site_id.bonus_ids)
        if self.l10n_pe_construction_bae_id:
            bonuses |= self.l10n_pe_construction_bae_id
        category = self.l10n_pe_construction_category_id
        return bonuses.filtered(lambda b: b._applies_to(category))

    def _l10n_pe_construction_daily_total(self, on_date=None):
        """Importe diario de todas las bonificaciones aplicables."""
        self.ensure_one()
        line = self._l10n_pe_get_wage_line(on_date)
        wage = line.daily_wage if line else 0.0
        return sum(bonus._daily_amount(wage)
                   for bonus in self._l10n_pe_construction_bonuses())

    @api.constrains('l10n_pe_construction_bae_id',
                    'l10n_pe_construction_category_id')
    def _check_bae_category(self):
        for version in self.filtered('l10n_pe_construction_bae_id'):
            category = version.l10n_pe_construction_category_id
            if category and not category.allows_bae:
                raise ValidationError(_(
                    'La bonificación por alta especialización solo '
                    'corresponde a los operarios; %(category)s no la admite.',
                    category=category.name))

    @api.onchange('l10n_pe_construction_category_id')
    def _onchange_construction_category(self):
        """Cambiar de categoría puede invalidar la BAE."""
        for version in self:
            category = version.l10n_pe_construction_category_id
            if version.l10n_pe_construction_bae_id and category \
                    and not category.allows_bae:
                version.l10n_pe_construction_bae_id = False


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    l10n_pe_construction_site_id = fields.Many2one(
        related='version_id.l10n_pe_construction_site_id', readonly=False,
        inherited=True)
    l10n_pe_construction_category_id = fields.Many2one(
        related='version_id.l10n_pe_construction_category_id', readonly=False,
        inherited=True)

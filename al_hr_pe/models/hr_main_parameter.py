# -*- coding: utf-8 -*-
from calendar import monthrange

from odoo import api, fields, models
from odoo.exceptions import UserError


class HrMainParameter(models.Model):
    """Parámetros principales de la planilla, uno por compañía.

    Cambios vs v18: sin ``dir_create_file`` (los exportadores generan
    ``ir.attachment``, no ficheros en disco — plan §6.5); las referencias
    a reglas salariales son opcionales hasta la Fase 2 (los métodos
    ``check_*`` validan lo que cada flujo necesita); la asignación
    familiar se calcula del RMV (10 %), nunca hardcodeada (plan §7.3).
    """
    _name = 'hr.main.parameter'
    _description = 'Parámetros Principales de Nómina'
    _check_company_auto = True

    name = fields.Char(default='Parámetros Principales')
    company_id = fields.Many2one(
        'res.company', string='Compañía', required=True, index=True,
        default=lambda self: self.env.company)
    rmv = fields.Float(
        string='R.M.V.', default=1130.0,
        help='Remuneración Mínima Vital vigente (S/ 1 130 desde enero '
             '2025, D.S. 006-2024-TR).')
    family_allowance = fields.Float(
        string='Asignación familiar', compute='_compute_family_allowance',
        help='10 % de la RMV (Ley 25129).')
    reprentante_legal_id = fields.Many2one(
        'res.partner', string='Representante legal')
    signature = fields.Binary(string='Firma del empleador')

    # --- Referencias a reglas salariales (se pueblan en Fase 2) ---
    # Sin check_company: hr.salary.rule no tiene company_id en v19 (la
    # regla vive en la estructura); la Fase 2 decidirá si añadirlo como
    # hacía v18 o filtrar por estructura.
    net_to_pay_sr_id = fields.Many2one(
        'hr.salary.rule', string='R.S. Neto a pagar')
    insurable_remuneration = fields.Many2one(
        'hr.salary.rule', string='R.S. Ingresos afectos AFP')

    # --- Clasificación de work entry types por categoría PLAME ---
    wd_dlab = fields.Many2many(
        'hr.work.entry.type', 'wd_dlab_main_parameter_rel',
        'main_parameter_id', 'wd_id', string='W.D. días laborados')
    wd_dnlab = fields.Many2many(
        'hr.work.entry.type', 'wd_dnlab_main_parameter_rel',
        'main_parameter_id', 'wd_id', string='W.D. días no laborados')
    wd_dsub = fields.Many2many(
        'hr.work.entry.type', 'wd_dsub_main_parameter_rel',
        'main_parameter_id', 'wd_id', string='W.D. días subsidiados')
    wd_ext = fields.Many2many(
        'hr.work.entry.type', 'wd_dext_main_parameter_rel',
        'main_parameter_id', 'wd_id', string='W.D. sobretiempo')
    wd_dvac = fields.Many2many(
        'hr.work.entry.type', 'wd_dvac_main_parameter_rel',
        'main_parameter_id', 'wd_id', string='W.D. ausencias')

    # --- Clasificación de categorías de reglas para la boleta ---
    income_categories = fields.Many2many(
        'hr.salary.rule.category', 'src_income_main_parameter_rel',
        'main_parameter_id', 'src_id', string='Categorías de ingresos')
    discounts_categories = fields.Many2many(
        'hr.salary.rule.category', 'src_discounts_main_parameter_rel',
        'main_parameter_id', 'src_id', string='Categorías de descuentos')
    contributions_categories = fields.Many2many(
        'hr.salary.rule.category', 'src_contributions_main_parameter_rel',
        'main_parameter_id', 'src_id',
        string='Categorías aportes del trabajador')
    contributions_emp_categories = fields.Many2many(
        'hr.salary.rule.category', 'src_contributions_emp_main_parameter_rel',
        'main_parameter_id', 'src_id',
        string='Categorías aportes del empleador')

    _unique_company = models.Constraint(
        'UNIQUE(company_id)',
        'Sólo puede existir un registro de Parámetros Principales por '
        'compañía.')

    @api.depends('rmv')
    def _compute_family_allowance(self):
        for param in self:
            param.family_allowance = param.rmv * 0.10

    @api.model
    def get_main_parameter(self, company=None):
        company = company or self.env.company
        param = self.search([('company_id', '=', company.id)], limit=1)
        if not param:
            raise UserError(self.env._(
                'No se han creado los Parámetros Principales para la '
                'compañía %(company)s (Nómina → Configuración → Perú).',
                company=company.display_name))
        return param

    def check_voucher_values(self):
        self.ensure_one()
        if not (self.wd_dlab and self.wd_dnlab and self.wd_dsub
                and self.wd_ext and self.wd_dvac and self.income_categories
                and self.discounts_categories
                and self.contributions_categories
                and self.contributions_emp_categories):
            raise UserError(self.env._(
                'Faltan configuraciones en la pestaña Boleta de los '
                'Parámetros Principales.'))

    # ------------------------------------------------------------------
    # Helpers de cálculo peruano (mes comercial de 30 días — SUNAT)
    # ------------------------------------------------------------------
    @api.model
    def get_month_name(self, month):
        return ['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
                'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre',
                'Diciembre'][month - 1]

    @api.model
    def get_months_of_30_days(self, days, months):
        """Normaliza: cada 30 días acumulados suman un mes."""
        while days >= 30:
            days -= 30
            months += 1
        return days, months

    @api.model
    def diff_months(self, date_from, date_to):
        return (date_to.year - date_from.year) * 12 \
            + date_to.month - date_from.month

    @api.model
    def get_months_days_difference(self, date_from, date_to):
        """(días, meses) entre dos fechas con la convención del mes
        comercial: meses calendario completos + días sueltos de los
        extremos, normalizando 30 días → 1 mes. Portado idéntico de v18
        (base de CTS/grati/vacaciones — no alterar sin fixture)."""
        if (date_from.year, date_from.month) == (date_to.year, date_to.month):
            return 0, date_to.day - date_from.day
        days = 0
        months = (date_to.year - date_from.year) * 12 \
            + (date_to.month - date_from.month - 1)
        if date_from.day == 1:
            months += 1
        else:
            last_day = monthrange(date_from.year, date_from.month)[1]
            days += last_day - date_from.day + 1
        last_day = monthrange(date_to.year, date_to.month)[1]
        if date_to.day == last_day:
            months += 1
        else:
            days += date_to.day
        if days >= 30:
            return self.get_months_of_30_days(days, months)
        return days, months

    # ------------------------------------------------------------------
    # Importe en letras (boletas y actas)
    # ------------------------------------------------------------------
    UNIDADES = (
        '', 'UN ', 'DOS ', 'TRES ', 'CUATRO ', 'CINCO ', 'SEIS ', 'SIETE ',
        'OCHO ', 'NUEVE ', 'DIEZ ', 'ONCE ', 'DOCE ', 'TRECE ', 'CATORCE ',
        'QUINCE ', 'DIECISEIS ', 'DIECISIETE ', 'DIECIOCHO ', 'DIECINUEVE ',
        'VEINTE ')
    DECENAS = ('VENTI', 'TREINTA ', 'CUARENTA ', 'CINCUENTA ', 'SESENTA ',
               'SETENTA ', 'OCHENTA ', 'NOVENTA ', 'CIEN ')
    CENTENAS = ('CIENTO ', 'DOSCIENTOS ', 'TRESCIENTOS ', 'CUATROCIENTOS ',
                'QUINIENTOS ', 'SEISCIENTOS ', 'SETECIENTOS ', 'OCHOCIENTOS ',
                'NOVECIENTOS ')

    @api.model
    def _convert_group(self, n):
        output = ''
        if n == '100':
            output = 'CIEN'
        elif n[0] != '0':
            output = self.CENTENAS[int(n[0]) - 1]
        k = int(n[1:])
        if k <= 20:
            output += self.UNIDADES[k]
        elif k > 30 and n[2] != '0':
            output += '%sY %s' % (self.DECENAS[int(n[1]) - 2],
                                  self.UNIDADES[int(n[2])])
        else:
            output += '%s%s' % (self.DECENAS[int(n[1]) - 2],
                                self.UNIDADES[int(n[2])])
        return output

    @api.model
    def number_to_letter(self, number):
        """Importe en letras estilo boleta: «MIL CIENTO TREINTA CON
        50/100». Portado de v18 (sin la tabla de monedas muerta)."""
        entero, decimales = ('%.2f' % round(float(number), 2)).split('.')
        number = int(entero)
        if not 0 <= number < 999999999:
            raise UserError(self.env._(
                'No es posible convertir %(number)s a letras.',
                number=number))
        converted = ''
        number_str = str(number).zfill(9)
        millones, miles, cientos = \
            number_str[:3], number_str[3:6], number_str[6:]
        if millones == '001':
            converted += 'UN MILLON '
        elif int(millones) > 0:
            converted += '%sMILLONES ' % self._convert_group(millones)
        if miles == '001':
            converted += 'UN MIL '
        elif int(miles) > 0:
            converted += '%sMIL ' % self._convert_group(miles)
        if cientos == '001':
            converted += 'UN '
        elif int(cientos) > 0:
            converted += '%s ' % self._convert_group(cientos)
        if number == 0:
            converted += 'CERO '
        converted += 'CON %s/100' % decimales
        return ' '.join(converted.upper().split())

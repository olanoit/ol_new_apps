# -*- coding: utf-8 -*-
"""Maestros del régimen de construcción civil.

Lo que fija la remuneración en este régimen no es el contrato sino la
**convención colectiva** CAPECO-FTCCP: todos los operarios de la misma
obra ganan el mismo jornal. Por eso el jornal vive en una tabla salarial
con vigencia y el trabajador solo lleva su categoría.

Que la tabla sea un registro fechado no es un capricho: el convenio se
renegocia cada año y en 2026 hasta cambió la ventana de vigencia (venía
siendo de junio a mayo y pasó a enero-diciembre). Un importe incrustado en
el código obligaría a tocarlo cada enero, y a reescribir el jornal de
todos los trabajadores.
"""
from decimal import Decimal

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from odoo.addons.al_hr_pe.tools import custom_round


def round_percent(base, percent):
    """Porcentaje de un importe, con aritmética decimal.

    En binario, 267.90 × 0.15 da 40.184999… y el redondeo SUNAT lo baja a
    40.18 cuando el resultado exacto, 40.185, tiene que subir a 40.19.
    Multiplicar en ``Decimal`` evita esa deriva; sobre los importes de la
    tabla oficial ambos caminos coinciden, así que el cambio no mueve
    ningún número ya validado.
    """
    return custom_round(
        Decimal(str(base)) * Decimal(str(percent)) / Decimal('100'))


class L10nPeHrConstructionCategory(models.Model):
    """Categoría del trabajador de construcción civil."""
    _name = 'l10n_pe.hr.construction.category'
    _description = 'Categoría de construcción civil'
    _order = 'sequence, code'

    name = fields.Char(string='Categoría', required=True, translate=True)
    code = fields.Char(string='Código', required=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    buc_percent = fields.Float(
        string='BUC %', digits=(5, 2), required=True,
        help='Bonificación Unificada de Construcción sobre el jornal '
             'básico: 32 % para el operario y 30 % para oficial y peón.')
    allows_bae = fields.Boolean(
        string='Admite BAE',
        help='La Bonificación por Alta Especialización solo corresponde a '
             'los operarios.')
    company_id = fields.Many2one(
        'res.company', string='Compañía', index=True,
        help='Vacío: categoría global. Con compañía: override propio.')

    _code_company_uniq = models.Constraint(
        'UNIQUE(code, company_id)',
        'Ya existe una categoría con ese código.')


class L10nPeHrConstructionWageTable(models.Model):
    """Tabla salarial de una convención colectiva."""
    _name = 'l10n_pe.hr.construction.wage.table'
    _description = 'Tabla salarial de construcción civil'
    _order = 'date_from desc'
    _check_company_auto = True

    name = fields.Char(
        string='Convenio', required=True,
        help='P. ej. «Convención colectiva 2026».')
    resolution = fields.Char(
        string='Resolución ministerial',
        help='Norma que aprueba la tabla, p. ej. R.M. N.° 197-2025-TR.')
    date_from = fields.Date(string='Vigente desde', required=True)
    date_to = fields.Date(string='Vigente hasta', required=True)
    company_id = fields.Many2one(
        'res.company', string='Compañía',
        help='Vacío: tabla global (es una norma nacional). Con compañía: '
             'override propio.')
    line_ids = fields.One2many(
        'l10n_pe.hr.construction.wage.line', 'table_id',
        string='Jornales por categoría')
    note = fields.Text(string='Notas')
    active = fields.Boolean(default=True)

    @api.constrains('date_from', 'date_to')
    def _check_dates(self):
        for table in self:
            if table.date_to < table.date_from:
                raise ValidationError(_(
                    'La vigencia de %(name)s termina antes de empezar.',
                    name=table.display_name))

    @api.constrains('date_from', 'date_to', 'company_id', 'active')
    def _check_overlap(self):
        """Dos tablas vigentes a la vez dejarían el jornal ambiguo."""
        for table in self.filtered('active'):
            overlapping = self.search([
                ('id', '!=', table.id),
                ('company_id', 'in', (False, table.company_id.id)
                 if table.company_id else (False,)),
                ('date_from', '<=', table.date_to),
                ('date_to', '>=', table.date_from),
            ], limit=1)
            if overlapping:
                raise ValidationError(_(
                    'La vigencia de %(name)s se solapa con %(other)s.',
                    name=table.display_name, other=overlapping.display_name))

    @api.model
    def _get_table_for_date(self, on_date, company=None):
        """Tabla vigente en esa fecha, propia de la compañía o global."""
        company = company or self.env.company
        return self.search([
            ('company_id', 'in', (False, company.id)),
            ('date_from', '<=', on_date),
            ('date_to', '>=', on_date),
        ], order='company_id desc, date_from desc', limit=1)


class L10nPeHrConstructionWageLine(models.Model):
    """Jornal de una categoría dentro de una tabla salarial."""
    _name = 'l10n_pe.hr.construction.wage.line'
    _description = 'Jornal por categoría'
    _order = 'table_id, category_id'

    table_id = fields.Many2one(
        'l10n_pe.hr.construction.wage.table', string='Tabla', required=True,
        ondelete='cascade', index=True)
    category_id = fields.Many2one(
        'l10n_pe.hr.construction.category', string='Categoría',
        required=True, ondelete='restrict')
    currency_id = fields.Many2one(
        'res.currency', string='Moneda',
        default=lambda self: self.env.ref('base.PEN',
                                          raise_if_not_found=False))
    daily_wage = fields.Monetary(
        string='Jornal básico', required=True,
        help='Remuneración de un día de trabajo, según el convenio.')
    mobility_amount = fields.Monetary(
        string='Bonif. movilidad',
        help='Importe diario por 6 pasajes urbanos. Es el mismo para las '
             'tres categorías: es un importe, no un porcentaje.')
    buc_percent = fields.Float(
        string='BUC %', digits=(5, 2),
        help='Deja vacío para usar el de la categoría.')

    # --- Derivados que el convenio fija como porcentaje del jornal ---
    dso_amount = fields.Monetary(
        string='D.S.O.', compute='_compute_derived',
        help='Descanso semanal obligatorio: jornal ÷ 6.')
    buc_amount = fields.Monetary(
        string='BUC', compute='_compute_derived')
    hour_value = fields.Monetary(
        string='Valor hora', compute='_compute_derived',
        help='Jornal ÷ 8.')
    overtime_60 = fields.Monetary(
        string='H.E. 60 %', compute='_compute_derived',
        help='Las dos primeras horas extras del día.')
    overtime_100 = fields.Monetary(
        string='H.E. 100 %', compute='_compute_derived',
        help='A partir de la tercera hora extra.')
    cts_amount = fields.Monetary(
        string='Indemnización 15 %', compute='_compute_derived')
    vacation_amount = fields.Monetary(
        string='Vacaciones 10 %', compute='_compute_derived')
    bonus_july_daily = fields.Monetary(
        string='Grat. F. Patrias diaria', compute='_compute_derived',
        help='40 jornales devengados en 7 meses (enero a julio).')
    bonus_december_daily = fields.Monetary(
        string='Grat. Navidad diaria', compute='_compute_derived',
        help='40 jornales devengados en 5 meses (agosto a diciembre).')
    school_daily = fields.Monetary(
        string='Asig. escolar diaria', compute='_compute_derived',
        help='30 jornales al año por hijo.')

    _category_table_uniq = models.Constraint(
        'UNIQUE(table_id, category_id)',
        'La categoría ya está en esta tabla salarial.')

    @api.depends('daily_wage', 'buc_percent', 'category_id.buc_percent')
    def _compute_derived(self):
        """Derivados del jornal, con el redondeo SUNAT (ROUND_HALF_UP).

        Las sobretasas se calculan sobre el valor hora **sin redondear**:
        con 89.30, la hora es 11.1625 y el 100 % son 22.33, no 22.32 como
        saldría de redondear la hora antes de multiplicar. Es un céntimo
        por hora, pero es el que trae la tabla oficial.
        """
        for line in self:
            wage = line.daily_wage or 0.0
            hour = wage / 8.0 if wage else 0.0
            line.dso_amount = custom_round(wage / 6.0) if wage else 0.0
            line.buc_amount = round_percent(wage, line._buc_rate())
            line.hour_value = custom_round(hour)
            line.overtime_60 = custom_round(hour * 1.6)
            line.overtime_100 = custom_round(hour * 2.0)
            line.cts_amount = round_percent(wage, 15)
            line.vacation_amount = round_percent(wage, 10)
            # Las dos gratificaciones valen 40 jornales, pero se devengan
            # en ventanas distintas: por eso la diaria de Navidad es mayor.
            line.bonus_july_daily = custom_round(wage * 40 / 210.0)
            line.bonus_december_daily = custom_round(wage * 40 / 150.0)
            line.school_daily = custom_round(wage * 30 / 360.0)

    def _buc_rate(self):
        """Porcentaje de BUC: el de la línea si se indicó, si no el de la
        categoría."""
        self.ensure_one()
        return self.buc_percent or self.category_id.buc_percent or 0.0

    def _period_amounts(self, days):
        """Importes de un periodo de ``days`` días trabajados.

        **No es el diario multiplicado por los días.** La tabla oficial
        redondea una sola vez, sobre el importe del periodo: para el
        oficial, el BUC semanal es 30 % de 418.50 = 125.55, mientras que
        6 × 20.93 daría 125.58. Tres céntimos por trabajador y semana que
        no cuadran con la boleta del convenio.

        En el operario ambos caminos dan lo mismo por casualidad (los
        céntimos del D.S.O. y del BUC se compensan), así que validar solo
        con esa categoría esconde el problema.
        """
        self.ensure_one()
        base = (self.daily_wage or 0.0) * days
        return {
            'jornal': custom_round(base),
            # Un día de descanso por cada seis trabajados.
            'dso': custom_round(base / 6.0),
            'buc': round_percent(base, self._buc_rate()),
            'movilidad': custom_round((self.mobility_amount or 0.0) * days),
            'indemnizacion': round_percent(base, 15),
            'vacaciones': round_percent(base, 10),
        }

    def _period_total(self, days):
        """Total de salarios del periodo, como la columna del convenio."""
        self.ensure_one()
        amounts = self._period_amounts(days)
        return custom_round(amounts['jornal'] + amounts['dso']
                            + amounts['buc'] + amounts['movilidad'])


class L10nPeHrConstructionBonus(models.Model):
    """Bonificaciones del convenio: BAE y condiciones de trabajo.

    Van a catálogo y no a reglas fijas por dos razones: cada obra activa
    unas distintas, y sus importes se renegocian. El usuario los corrige
    contra su convenio sin tocar código.
    """
    _name = 'l10n_pe.hr.construction.bonus'
    _description = 'Bonificación de construcción civil'
    _order = 'bonus_type, sequence, code'

    name = fields.Char(string='Bonificación', required=True, translate=True)
    code = fields.Char(string='Código', required=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    bonus_type = fields.Selection(
        selection=[
            ('bae', 'Alta especialización (BAE)'),
            ('condition', 'Condiciones de trabajo'),
        ],
        string='Tipo', required=True, default='condition',
        help='La BAE depende de la especialidad del operario; las de '
             'condiciones dependen de dónde se trabaja.')
    computation = fields.Selection(
        selection=[('percent', 'Porcentaje del jornal'),
                   ('fixed', 'Importe fijo por día')],
        string='Cálculo', required=True, default='percent')
    percent = fields.Float(string='Porcentaje', digits=(5, 2))
    amount = fields.Monetary(string='Importe diario')
    currency_id = fields.Many2one(
        'res.currency', string='Moneda',
        default=lambda self: self.env.ref('base.PEN',
                                          raise_if_not_found=False))
    category_ids = fields.Many2many(
        'l10n_pe.hr.construction.category',
        # Tabla explícita: el nombre que Odoo deriva de los dos modelos
        # pasa de los 63 caracteres que admite PostgreSQL.
        'l10n_pe_construction_bonus_category_rel', 'bonus_id', 'category_id',
        string='Categorías', help='Vacío: aplica a todas.')
    company_id = fields.Many2one('res.company', string='Compañía', index=True)
    note = fields.Text(string='Sustento')
    salary_rule_code = fields.Char(
        string='Código de la regla', required=True,
        help='Regla salarial que paga esta bonificación en la boleta. '
             'Varias bonificaciones pueden compartir regla: se suman. '
             'Añadir una bonificación nueva al convenio es crear el '
             'registro y apuntarlo a una regla, sin tocar código.')

    _code_company_uniq = models.Constraint(
        'UNIQUE(code, company_id)',
        'Ya existe una bonificación con ese código.')

    #: Regla que paga cada bonificación que trae el módulo. Se usa para
    #: rellenar el enlace en bases donde el registro se cargó antes de que
    #: existiera el campo: los datos van con `noupdate`, así que un
    #: `<record>` no los habría tocado.
    _DEFAULT_RULE_BY_XMLID = {
        'bonus_bae_equipo_mediano': 'BAE',
        'bonus_bae_topografo': 'BAE',
        'bonus_bae_equipo_pesado': 'BAE',
        'bonus_bae_electromecanico': 'BAE',
        'bonus_altitud': 'BALTI',
        'bonus_agua': 'BAGUA',
        'bonus_cota_cero': 'BCOTA',
        'bonus_altura': 'BALTU',
    }

    @api.model
    def _l10n_pe_fill_salary_rule_codes(self):
        """Asigna la regla a las bonificaciones del módulo que no la tengan.

        Idempotente y no pisa nada: solo escribe donde está vacío.
        """
        for xmlid, code in self._DEFAULT_RULE_BY_XMLID.items():
            bonus = self.env.ref('al_hr_pe_construction.%s' % xmlid,
                                 raise_if_not_found=False)
            if bonus and not bonus.salary_rule_code:
                bonus.salary_rule_code = code
        return True

    @api.constrains('computation', 'percent', 'amount')
    def _check_value(self):
        for bonus in self:
            if bonus.computation == 'percent' and not bonus.percent:
                raise ValidationError(_(
                    'Indique el porcentaje de %(name)s.', name=bonus.name))
            if bonus.computation == 'fixed' and not bonus.amount:
                raise ValidationError(_(
                    'Indique el importe diario de %(name)s.', name=bonus.name))

    def _daily_amount(self, daily_wage):
        """Cuánto suma esta bonificación por día trabajado."""
        self.ensure_one()
        if self.computation == 'fixed':
            return self.amount
        return round_percent(daily_wage or 0.0, self.percent or 0.0)

    def _applies_to(self, category):
        self.ensure_one()
        return not self.category_ids or category in self.category_ids


class L10nPeHrConstructionSite(models.Model):
    """Obra.

    En construcción civil el vínculo es por obra determinada, y las
    bonificaciones por condiciones de trabajo dependen de dónde está: la
    de altitud la activa la obra, no el trabajador.
    """
    _name = 'l10n_pe.hr.construction.site'
    _description = 'Obra de construcción'
    _order = 'name'
    _check_company_auto = True

    name = fields.Char(string='Obra', required=True)
    code = fields.Char(string='Código')
    company_id = fields.Many2one(
        'res.company', string='Compañía', required=True,
        default=lambda self: self.env.company)
    active = fields.Boolean(default=True)
    date_start = fields.Date(string='Inicio')
    date_end = fields.Date(string='Fin previsto')
    address = fields.Char(string='Dirección')
    district_id = fields.Many2one(
        'l10n_pe.res.city.district', string='Distrito')
    altitude = fields.Integer(
        string='Altitud (m s. n. m.)',
        help='Por encima de 3 000 m corresponde la bonificación por '
             'altitud.')
    work_location_id = fields.Many2one(
        'hr.work.location', string='Establecimiento (T-Registro)',
        check_company=True,
        help='Local del RUC con el que la obra se declara en la '
             'estructura 17 del T-Registro.')
    bonus_ids = fields.Many2many(
        'l10n_pe.hr.construction.bonus', string='Bonificaciones de la obra',
        domain=[('bonus_type', '=', 'condition')],
        help='Las que corresponden por dónde y cómo se trabaja aquí. Se '
             'suman a las propias del puesto de cada trabajador.')
    employee_count = fields.Integer(
        string='Trabajadores', compute='_compute_employee_count')

    _code_company_uniq = models.Constraint(
        'UNIQUE(code, company_id)',
        'Ya existe una obra con ese código en la compañía.')

    def _compute_employee_count(self):
        data = self.env['hr.version']._read_group(
            [('l10n_pe_construction_site_id', 'in', self.ids)],
            ['l10n_pe_construction_site_id'], ['employee_id:count_distinct'])
        counts = {site.id: count for site, count in data}
        for site in self:
            site.employee_count = counts.get(site.id, 0)

    def action_view_employees(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Trabajadores de %s', self.name),
            'res_model': 'hr.employee',
            'view_mode': 'list,form',
            'domain': [('l10n_pe_construction_site_id', '=', self.id)],
        }

# -*- coding: utf-8 -*-
"""Retención mensual del Impuesto a la Renta de 5ta Categoría (IR 5ta).

Liquidación del IR 5ta de todos los empleados de un lote mensual de
planilla, con el método del Inciso a) del Art. 53 LIR + Reglamento
D.S. 122-94-EF Art. 40:

1. Proyección anual: remuneración proyectada × meses restantes
   (12 − mes) + remuneración del mes + gratificaciones (proyectadas con
   el % del seguro social o reales si ya se liquidaron) + remuneraciones
   de meses anteriores + otros empleadores = renta bruta anual.
2. Deducción de 7 UIT (catálogo ``l10n_pe.hr.uit`` por año).
3. Tabla escalonada de tramos ``hr.rate.limit`` (8/14/17/20/30 % sobre
   5/20/35/45/∞ UIT — se generan con ``generate_tramos``).
4. Impuesto anual − retenciones previas (según ventanas del Art. 40) ÷
   equivalencia de meses [12, 11, …, 1] = retención mensual.
5. Reproyección: si existe la quinta del mes anterior
   (``previous_line_id``), la retención anual parte del ``saldo_ret``
   pendiente del empleado.

``line_ids`` contiene los afectos; ``line_excluidos_ids`` los excluidos
(retención proyectada ≤ 0). Estados: ``draft`` → ``verify`` →
``exported`` (volcado a los inputs del payslip).

Portado de ``hr_fifth_category`` (v18). Cambios v19: ``hr.contract`` →
``hr.version``; UIT vía ``l10n_pe.hr.uit`` (``account.fiscal.year``
eliminado); SQL con ``.format()`` → ORM; certificado PDF/Excel quedan
para la Fase 7.
"""
from datetime import date, timedelta

from odoo import api, fields, models
from odoo.exceptions import UserError

from odoo.addons.al_hr_pe.tools import custom_round
from .hr_benefits_engine import notify_success


class HrMainParameter(models.Model):
    _inherit = 'hr.main.parameter'

    # --- Renta de 5ta (nombres v18 conservados) ---
    fifth_afect_sr_id = fields.Many2one(
        'hr.salary.rule', string='R.S. Rem. ordinaria afecta a quinta',
        help='Regla salarial con las remuneraciones ordinarias afectas '
             'a renta de 5ta categoría.')
    fifth_extr_sr_id = fields.Many2one(
        'hr.salary.rule', string='R.S. Rem. extraordinaria afecta a quinta',
        help='Regla salarial con las remuneraciones extraordinarias '
             '(gratificaciones reales, reintegros, utilidades...).')
    proy_afect_sr_id = fields.Many2one(
        'hr.salary.rule', string='R.S. Proyección de ingresos afectos',
        help='Regla salarial cuyo total mensual se proyecta a los meses '
             'restantes del año.')
    gratification_sr_id = fields.Many2one(
        'hr.salary.rule', string='R.S. Gratificación julio y diciembre')
    fifth_category_input_id = fields.Many2one(
        'hr.payslip.input.type', string='Input quinta categoría')
    ret_extraordinary_input_id = fields.Many2one(
        'hr.payslip.input.type', string='Input retención extraordinaria')
    rate_limit_ids = fields.One2many(
        'hr.rate.limit', 'main_parameter_id', string='Tramos de 5ta')

    def generate_tramos(self):
        """Regenera los tramos del IR 5ta: tasas [8, 14, 17, 20, 30] %
        sobre límites [5, 20, 35, 45, ∞] × UIT (∞ se guarda como 0,
        semántica v18 de ``get_tax_proy``). La UIT sale del catálogo
        ``l10n_pe.hr.uit`` del año en curso."""
        self.ensure_one()
        year = fields.Date.context_today(self).year
        uit = self.env['l10n_pe.hr.uit'].get_uit(year)
        self.rate_limit_ids.unlink()
        tasas = [8, 14, 17, 20, 30]
        tramos = [5, 20, 35, 45, 0]
        RateLimit = self.env['hr.rate.limit']
        for c, tasa in enumerate(tasas, 1):
            RateLimit.create({
                'main_parameter_id': self.id,
                'range': c,
                'limit': tramos[c - 1] * uit,
                'rate': tasa,
            })
        return notify_success(self.env._('Se generaron los tramos.'))

    def check_fifth_values(self):
        """Valida la configuración de la pestaña Quinta antes de
        calcular o exportar (paridad v18; la UIT se valida en
        ``l10n_pe.hr.uit.get_uit``)."""
        self.ensure_one()
        missing = []
        if not self.fifth_afect_sr_id:
            missing.append('R.S. Rem. ordinaria afecta a quinta')
        if not self.fifth_extr_sr_id:
            missing.append('R.S. Rem. extraordinaria afecta a quinta')
        if not self.proy_afect_sr_id:
            missing.append('R.S. Proyección de ingresos afectos')
        if not self.gratification_sr_id:
            missing.append('R.S. Gratificación julio y diciembre')
        if not self.fifth_category_input_id:
            missing.append('Input quinta categoría')
        if not self.ret_extraordinary_input_id:
            missing.append('Input retención extraordinaria')
        if not self.rate_limit_ids:
            missing.append('Tramos de quinta categoría')
        if missing:
            raise UserError(self.env._(
                'Faltan configuraciones en la pestaña Quinta categoría '
                'de los Parámetros Principales:\n\n%(missing)s',
                missing='\n'.join('• %s' % item for item in missing)))


class HrRateLimit(models.Model):
    """Tramos de la tabla escalonada del IR 5ta (en múltiplos de UIT).

    Pertenece al ``hr.main.parameter`` de cada compañía; hereda su
    ``company_id`` para que las tasas (personalizables por empresa)
    queden aisladas en multicompañía.
    """
    _name = 'hr.rate.limit'
    _description = 'Tramo de tasa de renta de 5ta categoría'
    _order = 'range'

    main_parameter_id = fields.Many2one(
        'hr.main.parameter', string='Parámetros principales',
        ondelete='cascade', required=True, index=True)
    company_id = fields.Many2one(
        related='main_parameter_id.company_id', string='Compañía',
        store=True, index=True)
    range = fields.Integer(string='Rango')
    limit = fields.Integer(
        string='Límite',
        help='Límite superior del tramo en soles (0 = sin tope).')
    rate = fields.Integer(string='Tasa (%)')


class HrFifthCategory(models.Model):
    _name = 'hr.fifth.category'
    _description = 'Renta de 5ta categoría'
    _order = 'id desc'
    _check_company_auto = True

    name = fields.Char(
        string='Nombre', compute='_compute_name', store=True)
    payslip_run_id = fields.Many2one(
        'hr.payslip.run', string='Lote de nómina', required=True,
        check_company=True)
    company_id = fields.Many2one(
        'res.company', string='Compañía', required=True, index=True,
        default=lambda self: self.env.company)
    line_ids = fields.One2many(
        'hr.fifth.category.line', 'fifth_category_id',
        string='Afectos a quinta')
    line_excluidos_ids = fields.One2many(
        'hr.fifth.category.line.excluidos', 'fifth_category_id',
        string='Excluidos de quinta')
    state = fields.Selection(
        selection=[('draft', 'Borrador'), ('verify', 'En proceso'),
                   ('exported', 'Exportado')],
        string='Estado', default='draft')
    middle_month_number = fields.Integer(
        string='Mes', compute='_compute_middle_month_number', store=True,
        help='Mes (1-12) que representa el lote: mes intermedio entre '
             'las fechas de inicio y fin del lote (o el de la fecha '
             'disponible). Determina los meses restantes de proyección '
             'y la equivalencia de la retención.')
    previous_fifth_category_id = fields.Many2one(
        'hr.fifth.category', string='Quinta anterior',
        compute='_compute_previous_fifth_category_id', store=True,
        help='Quinta del lote inmediatamente anterior; habilita la '
             'reproyección por saldo pendiente.')

    _unique_run = models.Constraint(
        'UNIQUE(company_id, payslip_run_id)',
        'Ya existe una quinta categoría para ese lote de nóminas.')

    @api.depends('payslip_run_id')
    def _compute_name(self):
        for record in self:
            record.name = 'Quinta %s' % record.payslip_run_id.name \
                if record.payslip_run_id else False

    @api.depends('payslip_run_id.date_start', 'payslip_run_id.date_end')
    def _compute_middle_month_number(self):
        """Mes intermedio del lote (v18: hr.payslip.run.get_month_number)."""
        for record in self:
            run = record.payslip_run_id
            if not run or not (run.date_start or run.date_end):
                record.middle_month_number = 0
            elif run.date_start and run.date_end:
                if run.date_start > run.date_end:
                    record.middle_month_number = run.date_end.month
                else:
                    total_days = (run.date_end - run.date_start).days
                    middle = run.date_start + timedelta(days=total_days // 2)
                    record.middle_month_number = middle.month
            else:
                record.middle_month_number = \
                    (run.date_start or run.date_end).month

    @api.depends('payslip_run_id', 'company_id')
    def _compute_previous_fifth_category_id(self):
        """Quinta de la planilla anterior de la misma compañía (el lote
        con ``date_end`` más reciente antes del inicio del actual)."""
        Run = self.env['hr.payslip.run']
        for record in self:
            previous = False
            run = record.payslip_run_id
            if run and run.date_start:
                previous_run = Run.search([
                    ('date_end', '<', run.date_start),
                    ('company_id', '=', record.company_id.id),
                ], order='date_end desc', limit=1)
                if previous_run:
                    previous = self.search([
                        ('payslip_run_id', '=', previous_run.id),
                        ('company_id', '=', record.company_id.id),
                    ], limit=1)
            record.previous_fifth_category_id = previous

    def turn_draft(self):
        """Vuelve a borrador eliminando líneas afectas y excluidas."""
        self.line_ids.unlink()
        self.line_excluidos_ids.unlink()
        self.write({'state': 'draft'})

    def turn_verify(self):
        """Reabre a «en proceso» para revisar antes de exportar."""
        self.write({'state': 'verify'})

    def generate_fifth(self):
        """Crea una línea por boleta del lote y calcula la quinta."""
        self.ensure_one()
        Line = self.env['hr.fifth.category.line']
        for slip in self.payslip_run_id.slip_ids:
            Line.create({
                'fifth_category_id': self.id,
                'slip_id': slip.id,
            })
        self.line_ids.compute_fifth_line()
        self.state = 'verify'
        return notify_success(self.env._('Se generó la quinta '
                                         'correctamente.'))

    def recompute_fifth(self):
        self.line_ids.compute_fifth_line()

    def export_fifth(self):
        """Vuelca la retención IR 5ta al payslip de cada empleado.

        Por cada línea afecta escribe en su boleta:

        * ``fifth_category_input_id`` ← ``monthly_ret``;
        * ``ret_extraordinary_input_id`` ← ``ext_ret``.

        Crea la línea de input si la boleta no la tiene (patrón CTS
        v19). Marca el lote como ``exported``.
        """
        self.ensure_one()
        param = self.env['hr.main.parameter'].get_main_parameter(
            self.company_id)
        param.check_fifth_values()
        for line in self.line_ids:
            slip = line.slip_id
            for input_type, amount in (
                    (param.fifth_category_input_id, line.monthly_ret),
                    (param.ret_extraordinary_input_id, line.ext_ret)):
                input_line = slip.input_line_ids.filtered(
                    lambda inp: inp.input_type_id == input_type)
                if input_line:
                    input_line.amount = amount
                else:
                    slip.write({'input_line_ids': [(0, 0, {
                        'input_type_id': input_type.id,
                        'amount': amount,
                    })]})
        self.state = 'exported'
        return notify_success(self.env._('Se exportó exitosamente.'))

    def get_employees_excluidos(self):
        """Wizard para reincorporar empleados excluidos como afectos."""
        self.ensure_one()
        wizard = self.env['hr.employee.excluidos.wizard'].create({
            'fifth_category_id': self.id,
            'company_id': self.company_id.id,
        })
        return {
            'name': self.env._('Seleccionar empleados'),
            'res_id': wizard.id,
            'view_mode': 'form',
            'res_model': 'hr.employee.excluidos.wizard',
            'view_id': self.env.ref(
                'al_hr_pe_benefits.view_hr_employee_excluidos_wizard').id,
            'target': 'new',
            'type': 'ir.actions.act_window',
        }


class HrFifthCategoryLine(models.Model):
    """Línea de quinta categoría (empleado afecto).

    Leyenda de acrónimos: Rem = remuneración; Proy = proyectada;
    Ret = retención; Ext = extraordinaria; Ant = anterior;
    Emp = empleador(es).
    """
    _name = 'hr.fifth.category.line'
    _description = 'Línea de renta de 5ta categoría'
    _order = 'employee_id'
    _check_company_auto = True

    fifth_category_id = fields.Many2one(
        'hr.fifth.category', string='Quinta cat.', ondelete='cascade',
        index=True)
    company_id = fields.Many2one(
        related='fifth_category_id.company_id', string='Compañía',
        store=True, index=True)
    slip_id = fields.Many2one(
        'hr.payslip', string='Boleta', required=True, check_company=True)
    employee_id = fields.Many2one(
        related='slip_id.employee_id', string='Empleado', store=True,
        index=True)
    identification_id = fields.Char(
        related='slip_id.employee_id.identification_id',
        string='Nro. documento')
    monthly_rem = fields.Float(
        string='Rem. mes', help='Remuneración ordinaria del mes.')
    edit_proy = fields.Boolean(
        string='Editar proy.', default=False,
        help='Permite editar manualmente los valores proyectados.')
    contrac_proy_rem = fields.Float(
        string='Rem. base proy.',
        help='Remuneración base para la proyección.')
    proy_rem = fields.Float(
        string='(+) Total rem. proy.',
        help='Remuneración proyectada anual (base × meses restantes + '
             'mes actual).')
    grat_july = fields.Float(
        string='(+) Grat. julio',
        help='Gratificación de julio (real o proyectada).')
    grat_december = fields.Float(
        string='(+) Grat. diciembre',
        help='Gratificación de diciembre (real o proyectada).')
    other_emp_proy_rem = fields.Float(
        string='Rem. otros emp.',
        help='Remuneración proyectada de otros empleadores.')
    past_rem = fields.Float(
        string='Rem. meses ant.',
        help='Remuneración acumulada de meses anteriores del año.')
    total_proy = fields.Float(
        string='Rem. bruta anual',
        help='Total de remuneración bruta proyectada.')
    seven_uit = fields.Float(
        string='(-) Deducción (7 UIT)', help='Monto deducible de 7 UIT.')
    net_rent = fields.Float(
        string='Rem. neta anual',
        help='Remuneración neta después de la deducción.')
    tax_proy = fields.Float(
        string='Imp. anual proy.',
        help='Impuesto anual proyectado (tabla de tramos).')
    past_months_ret = fields.Float(
        string='Ret. meses ant.',
        help='Retenciones de meses anteriores (ventanas del Art. 40).')
    other_emp_ret = fields.Float(
        string='Ret. otros emp.',
        help='Retenciones efectuadas por otros empleadores.')
    annual_ret = fields.Float(
        string='Renta anual',
        help='Retención anual pendiente (impuesto proyectado menos '
             'retenciones previas; con reproyección si hay quinta '
             'anterior).')
    monthly_rent = fields.Float(
        string='Renta mensual',
        help='Proporción mensual de la retención anual.')
    ext_rem = fields.Float(
        string='Rem. ext.', help='Remuneraciones extraordinarias del mes.')
    total_net_rent = fields.Float(
        string='Rem. neta + ext.',
        help='Remuneración neta anual + extraordinaria.')
    ext_ret = fields.Float(
        string='Ret. ext.',
        help='Retención extraordinaria (ingreso manual, criterio v18).')
    monthly_ret = fields.Float(
        string='Ret. mensual', help='Monto a retener en el mes.')
    saldo_ret = fields.Float(
        string='Saldo ret.', compute='_compute_saldo_ret', store=True,
        help='Saldo anual pendiente de retener.')
    previous_line_id = fields.Many2one(
        'hr.fifth.category.line', string='Línea anterior',
        compute='_compute_previous_line_id', store=True,
        help='Línea del mismo empleado en la quinta del mes anterior.')

    @api.depends('annual_ret', 'monthly_ret', 'ext_ret')
    def _compute_saldo_ret(self):
        """Saldo pendiente = retención anual − mensual − extraordinaria
        (0 si algún valor es negativo, paridad v18)."""
        for record in self:
            values = (record.annual_ret, record.monthly_ret,
                      record.ext_ret)
            if any(value < 0 for value in values):
                record.saldo_ret = 0.0
            else:
                record.saldo_ret = (record.annual_ret - record.monthly_ret
                                    - record.ext_ret)

    @api.depends('fifth_category_id.previous_fifth_category_id',
                 'employee_id')
    def _compute_previous_line_id(self):
        for line in self:
            prev_cat = line.fifth_category_id.previous_fifth_category_id
            previous_line = prev_cat.line_ids.filtered(
                lambda prev: prev.employee_id == line.employee_id) \
                if prev_cat else self.browse()
            line.previous_line_id = previous_line[:1].id \
                if previous_line else False

    # ------------------------------------------------------------------
    # Helpers de cálculo
    # ------------------------------------------------------------------
    @api.model
    def _sum_payslip_rule_totals(self, employee, company, rules,
                                 date_from, date_before):
        """Suma los totales de ``rules`` en boletas de lote del empleado
        con ``date_to`` en [date_from, date_before). Sustituye al SQL
        con ``.format()`` del v18 por ORM puro."""
        if not rules:
            return 0.0
        lines = self.env['hr.payslip.line'].search([
            ('slip_id.date_to', '>=', date_from),
            ('slip_id.date_to', '<', date_before),
            ('employee_id', '=', employee.id),
            ('salary_rule_id', 'in', rules.ids),
            ('slip_id.payslip_run_id', '!=', False),
            ('slip_id.company_id', '=', company.id),
        ])
        return sum(lines.mapped('total'))

    @api.model
    def _get_quinta_rule(self, company):
        """Regla QUINTA de la estructura BASE (v18 buscaba por código y
        compañía; en v19 la regla vive en la estructura)."""
        # TODO(fase4-revisar): confirmar que la Fase 2 crea la regla con
        # código QUINTA en al_hr_pe.base_structure.
        struct = self.env.ref('al_hr_pe.base_structure')
        return self.env['hr.salary.rule'].search([
            ('struct_id', '=', struct.id),
            ('code', '=', 'QUINTA'),
        ], limit=1)

    def get_past_rem(self, slip, date_from):
        """Remuneraciones afectas (ordinarias + extraordinarias) de las
        boletas de lote anteriores del año, más lo declarado de otros
        empleadores en quintas previas."""
        company = slip.company_id
        param = self.env['hr.main.parameter'].get_main_parameter(company)
        param.check_fifth_values()
        rem_ant = self._sum_payslip_rule_totals(
            slip.employee_id, company,
            param.fifth_afect_sr_id + param.fifth_extr_sr_id,
            date_from, slip.date_to)
        other_past_rem = self.search([
            ('slip_id.date_to', '>=', date_from),
            ('slip_id.date_to', '<', slip.date_to),
            ('employee_id', '=', slip.employee_id.id),
            ('company_id', '=', company.id),
        ])
        return rem_ant + sum(other_past_rem.mapped('other_emp_proy_rem'))

    @api.model
    def get_tax_proy(self, net_rent, lines):
        """Impuesto proyectado por la tabla escalonada de tramos
        (límite 0 = tramo final sin tope, paridad v18)."""
        tax_proy = tax = 0
        for line in lines:
            if net_rent > line.limit and line.limit > 0:
                tax_proy += (line.limit - tax) * line.rate * 0.01
                tax += line.limit - tax
            else:
                tax_proy += (net_rent - tax) * line.rate * 0.01
                break
        return tax_proy

    def get_past_months_ret(self, slip, date_from):
        """Retenciones previas del año según las ventanas del Art. 40
        del Reglamento (paridad v18, incluidos sus límites exclusivos):

        * ene-mar: 0;
        * abr, may, ago, sep, dic: QUINTA retenida hasta el mes previo;
        * jun-jul: QUINTA retenida de enero a abril;
        * oct-nov: QUINTA retenida de enero a agosto.

        Siempre se suman las retenciones de otros empleadores declaradas
        en quintas previas del año.
        """
        # TODO(fase4-revisar): los límites '< 30/04' y '< 31/08' (v18)
        # excluyen la boleta cuyo date_to cae exactamente ese día; se
        # conserva por paridad exacta.
        company = slip.company_id
        other_past_ret = self.search([
            ('slip_id.date_to', '>=', date_from),
            ('slip_id.date_to', '<', slip.date_to),
            ('employee_id', '=', slip.employee_id.id),
            ('company_id', '=', company.id),
        ])
        other_ret = sum(other_past_ret.mapped('other_emp_ret'))
        if slip.date_from.month in (1, 2, 3):
            return 0 + other_ret
        if slip.date_from.month in (4, 5, 8, 9, 12):
            date_before = slip.date_to
        elif slip.date_to.month in (6, 7):
            date_before = date(date_from.year, 4, 30)
        elif slip.date_to.month in (10, 11):
            date_before = date(date_from.year, 8, 31)
        else:
            return other_ret
        ret_ant = self._sum_payslip_rule_totals(
            slip.employee_id, company, self._get_quinta_rule(company),
            date_from, date_before)
        return ret_ant + other_ret

    @api.model
    def get_month_equivalence_proy(self, month):
        """Meses restantes del año a proyectar."""
        return 12 - month

    @api.model
    def get_month_equivalence_rent(self, month):
        """Divisor de la retención anual según el mes (Art. 40)."""
        month_equivalence = [12, 11, 10, 9, 8, 7, 6, 5, 4, 3, 2, 1]
        return month_equivalence[month - 1]

    def _get_renta_anual_proyecta(self):
        """Retención anual pendiente, con reproyección.

        Base: impuesto proyectado − retenciones de meses anteriores −
        retenciones de otros empleadores. Si existe la línea del mes
        anterior: con igual impuesto proyectado se arrastra su
        ``saldo_ret``; si el impuesto cambió (reintegros, aumentos) se
        reproyecta descontando lo ya retenido
        (``tax_proy_ant − saldo_ret_ant``).
        """
        self.ensure_one()
        annual_ret = ((self.tax_proy or 0.0) - (self.past_months_ret or 0.0)
                      - (self.other_emp_ret or 0.0))
        previous_line = self.previous_line_id
        if previous_line:
            if previous_line.tax_proy != self.tax_proy:
                annual_ret = self.tax_proy - (
                    previous_line.tax_proy - previous_line.saldo_ret)
            else:
                annual_ret = previous_line.saldo_ret
        return annual_ret

    def compute_fifth_line(self):
        """Calcula la línea completa (proyección → tramos → retención).

        Paridad de fórmulas v18 exacta; cambios v19: versión en lugar de
        contrato, UIT por catálogo, gratificaciones reales por año
        entero (``hr.gratification.year``) y todo filtrado por compañía.
        Si la retención mensual resulta ≤ 0 la línea pasa a excluidos.
        """
        # Limpieza v18: líneas huérfanas creadas al descartar el editor.
        self.search([('fifth_category_id', '=', False),
                     ('id', 'not in', self.ids)]).unlink()
        GratLine = self.env['hr.gratification.line']
        Uit = self.env['l10n_pe.hr.uit']
        for record in self:
            slip = record.slip_id
            company = record.fifth_category_id.company_id \
                or slip.company_id
            param = self.env['hr.main.parameter'].get_main_parameter(
                company)
            param.check_fifth_values()
            month = record.fifth_category_id.middle_month_number
            proy_month = self.get_month_equivalence_proy(month)
            rent_month = self.get_month_equivalence_rent(month)
            year = slip.date_to.year
            uit = Uit.get_uit(year)
            year_start = date(year, 1, 1)
            employee, version = slip.employee_id, slip.version_id

            grat_july = grat_december = GratLine
            if month >= 7:
                grat_july = GratLine.search([
                    ('gratification_id.type', '=', '07'),
                    ('employee_id', '=', employee.id),
                    ('gratification_id.year', '=', year),
                    ('gratification_id.company_id', '=', company.id),
                ])
            if month == 12:
                grat_december = GratLine.search([
                    ('gratification_id.type', '=', '12'),
                    ('employee_id', '=', employee.id),
                    ('gratification_id.year', '=', year),
                    ('gratification_id.company_id', '=', company.id),
                ])

            record.monthly_rem = sum(slip.line_ids.filtered(
                lambda line: line.salary_rule_id == param.fifth_afect_sr_id
            ).mapped('total'))
            if not record.edit_proy:
                record.contrac_proy_rem = sum(slip.line_ids.filtered(
                    lambda line:
                    line.salary_rule_id == param.proy_afect_sr_id
                ).mapped('total'))
            record.proy_rem = (record.contrac_proy_rem * proy_month) \
                + record.monthly_rem

            # Gratificaciones: reales si ya se liquidaron (incluye bono
            # extraordinario EsSalud); proyectadas con el % del seguro
            # social de la versión en caso contrario.
            insurance_percent = version.social_insurance_id.percent or 0.0
            grat_proy = record.contrac_proy_rem \
                * (1 + insurance_percent / 100)
            grat_july_proy = grat_proy if not record.edit_proy \
                else record.grat_july
            record.grat_july = (
                sum(grat_july.mapped('total_grat'))
                + sum(grat_july.mapped('bonus_essalud'))
            ) if month >= 7 and grat_july else grat_july_proy
            grat_december_proy = grat_proy if not record.edit_proy \
                else record.grat_december
            record.grat_december = (
                sum(grat_december.mapped('total_grat'))
                + sum(grat_december.mapped('bonus_essalud'))
            ) if month == 12 and grat_december else grat_december_proy

            record.past_rem = self.get_past_rem(slip, year_start)
            record.total_proy = (record.proy_rem + record.grat_july
                                 + record.grat_december
                                 + record.other_emp_proy_rem
                                 + record.past_rem)
            record.seven_uit = 7 * uit
            record.net_rent = record.total_proy - record.seven_uit
            tax_proy = self.get_tax_proy(
                record.net_rent, param.rate_limit_ids)
            record.tax_proy = 0 if tax_proy < 0 else tax_proy
            record.past_months_ret = self.get_past_months_ret(
                slip, year_start)
            record.annual_ret = record._get_renta_anual_proyecta()
            record.monthly_rent = custom_round(
                record.annual_ret / rent_month, 2)
            record.ext_rem = sum(slip.line_ids.filtered(
                lambda line: line.salary_rule_id == param.fifth_extr_sr_id
            ).mapped('total'))
            record.total_net_rent = record.ext_rem + record.net_rent
            # La retención extraordinaria es de ingreso manual (criterio
            # v18): la mensual descuenta la extraordinaria del anual.
            record.monthly_ret = custom_round(
                (record.annual_ret - record.ext_ret) / rent_month, 2)

            if not record.monthly_ret > 0 \
                    and not self.env.context.get('line_form') \
                    and record.fifth_category_id.state == 'draft':
                self.env['hr.fifth.category.line.excluidos'].create({
                    'fifth_category_id': record.fifth_category_id.id,
                    'slip_id': record.slip_id.id,
                    'monthly_rem': record.monthly_rem,
                    'contrac_proy_rem': record.contrac_proy_rem,
                    'proy_rem': record.proy_rem,
                    'grat_july': record.grat_july,
                    'grat_december': record.grat_december,
                    'total_proy': record.total_proy,
                    'seven_uit': record.seven_uit,
                    'net_rent': record.net_rent,
                })
                record.unlink()


class HrFifthCategoryLineExcluidos(models.Model):
    """Empleado excluido de la retención (retención proyectada ≤ 0)."""
    _name = 'hr.fifth.category.line.excluidos'
    _description = 'Línea de renta de 5ta categoría - Excluidos'
    _rec_name = 'employee_id'
    _order = 'employee_id'
    _check_company_auto = True

    fifth_category_id = fields.Many2one(
        'hr.fifth.category', string='Quinta cat.', ondelete='cascade',
        required=True, index=True)
    company_id = fields.Many2one(
        related='fifth_category_id.company_id', string='Compañía',
        store=True, index=True)
    slip_id = fields.Many2one(
        'hr.payslip', string='Boleta', required=True, check_company=True)
    employee_id = fields.Many2one(
        related='slip_id.employee_id', string='Empleado', store=True,
        index=True)
    identification_id = fields.Char(
        related='slip_id.employee_id.identification_id',
        string='Nro. documento')
    monthly_rem = fields.Float(string='Rem. mes')
    contrac_proy_rem = fields.Float(string='Rem. base proy.')
    proy_rem = fields.Float(string='(+) Total rem. proy.')
    grat_july = fields.Float(string='(+) Grat. julio')
    grat_december = fields.Float(string='(+) Grat. diciembre')
    total_proy = fields.Float(string='Rem. bruta anual')
    seven_uit = fields.Float(string='(-) Deducción (7 UIT)')
    net_rent = fields.Float(string='Rem. neta anual')


class HrEmployeeExcluidosWizard(models.TransientModel):
    """Reincorpora empleados excluidos como líneas afectas (para forzar
    la retención de un excluido, p. ej. por rentas de otro empleador)."""
    _name = 'hr.employee.excluidos.wizard'
    _description = 'Asistente de empleados excluidos de quinta'

    fifth_category_id = fields.Many2one(
        'hr.fifth.category', string='Quinta cat.', required=True)
    company_id = fields.Many2one(
        'res.company', string='Compañía', required=True, readonly=True,
        default=lambda self: self.env.company)
    employees = fields.Many2many(
        'hr.fifth.category.line.excluidos',
        'hr_fifth_category_employee_excluidos_rel', 'wizard_id',
        'excluido_id', string='Empleados excluidos', required=True,
        domain="[('fifth_category_id', '=', fifth_category_id)]")

    def insert(self):
        """Crea una línea afecta por cada excluido seleccionado (el
        usuario recalcula después con «Recalcular quinta»)."""
        self.ensure_one()
        self.env['hr.fifth.category.line'].create([{
            'fifth_category_id': self.fifth_category_id.id,
            'slip_id': excluido.slip_id.id,
        } for excluido in self.employees])

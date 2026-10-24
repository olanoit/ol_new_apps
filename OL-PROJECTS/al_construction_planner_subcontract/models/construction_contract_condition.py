# -*- coding: utf-8 -*-
"""Condiciones de contrata y esquema de cálculo (requerimiento CREVAL v1.0,
3.4). Las condiciones son una plantilla que la empresa configura y que se
copia a cada orden de contrata al asignar la contrata: la copia queda enlazada
a la orden (``order_id``) y en ella se ajustan los porcentajes pactados. El
esquema de cálculo es la lista ordenada de conceptos que arma el resumen del
valorizado; ningún porcentaje ni base queda fijo en el código.

Una orden sin condiciones se comporta como hasta ahora (retención por línea de
la tarifa y liquidación semanal por contrata)."""
from odoo import Command, api, fields, models
from odoo.exceptions import UserError, ValidationError

ADVANCE_METHODS = [
    ('total', 'Proporcional al total de cada valorizado'),
    ('subtotal', 'Proporcional al subtotal de cada valorizado'),
    ('fixed', 'Monto fijo por valorizado'),
    ('manual', 'Manual'),
]
GUARANTEE_BASES = [
    ('total', 'Total con IGV'),
    ('subtotal', 'Subtotal sin IGV'),
]
GUARANTEE_FROM = [
    ('invoice', 'Desde cada factura'),
    ('settlement', 'Desde la liquidación'),
]
FREQUENCIES = [
    ('weekly', 'Semanal'),
    ('biweekly', 'Quincenal'),
    ('monthly', 'Mensual'),
    ('end', 'Al término'),
]
MONTHLY_CUTOFFS = [
    ('month_end', 'Fin de mes'),
    ('day', 'Día de corte'),
]
LINE_DETAILS = [
    ('task', 'Por partida'),
    ('activity', 'Por actividad'),
]
SCHEME_KINDS = [
    ('price_adjustment', 'Ajuste de precio'),
    ('deduction', 'Deductivo'),
    ('tax', 'Impuesto'),
    ('advance', 'Amortización del adelanto'),
    ('retention', 'Retención (fondo de garantía)'),
]
SCHEME_BASES = [
    ('direct', 'Costo directo'),
    ('direct_additional', 'Costo directo más adicionales'),
    ('subtotal', 'Subtotal'),
    ('total', 'Total con impuestos'),
    ('own', 'Monto propio'),
]
SCHEME_SIGNS = [
    ('add', 'Suma'),
    ('subtract', 'Resta'),
]
INVOICE_MODES = [
    ('service_line', 'Línea de servicio'),
    ('own_line', 'Línea propia'),
    ('payment_discount', 'Descuento al pago'),
    ('tax', 'Impuesto'),
    ('regularization', 'Regularización'),
    ('installment', 'Cuota'),
]
# Reflejo en la factura que admite cada tipo de fila.
KIND_INVOICE_MODES = {
    'price_adjustment': ('service_line', 'own_line'),
    'deduction': ('own_line', 'payment_discount'),
    'tax': ('tax',),
    'advance': ('regularization',),
    'retention': ('installment',),
}
REQUIREMENT_CODES = [
    ('term', 'Vencimiento del plazo'),
    ('reception_act', 'Acta de recepción'),
    ('no_debt_letter', 'Carta de no deuda'),
    ('no_after_sales', 'Ninguna observación de postventa abierta'),
    ('other', 'Otro'),
]


class ConstructionContractRequirement(models.Model):
    _name = 'construction.contract.requirement'
    _description = 'Requisito de devolución del fondo de garantía'
    _order = 'sequence, name, id'

    name = fields.Char(string='Requisito', required=True, translate=True)
    sequence = fields.Integer(default=10)
    code = fields.Selection(REQUIREMENT_CODES, string='Tipo', required=True, default='other',
                            help='«Vencimiento del plazo» se cumple solo al llegar la fecha; los '
                                 'demás los marca administración.')
    active = fields.Boolean(default=True)


class ConstructionContractDocumentType(models.Model):
    _name = 'construction.contract.document.type'
    _description = 'Documento requerido para la liquidación de contrata'
    _order = 'sequence, name, id'

    name = fields.Char(string='Documento', required=True, translate=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)


class ConstructionContractCondition(models.Model):
    _name = 'construction.contract.condition'
    _description = 'Condiciones de contrata'
    _inherit = ['mail.thread']
    _order = 'sequence, name, id'
    _check_company_auto = True

    name = fields.Char(string='Nombre', required=True, tracking=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', string='Compañía', index=True,
                                 help='Vacía: disponibles en todas las compañías.')
    currency_id = fields.Many2one(
        'res.currency', string='Moneda', compute='_compute_currency_id')
    # La copia de una orden de contrata (no aparece entre las plantillas).
    order_id = fields.Many2one(
        'purchase.order', string='Orden de contrata', index='btree_not_null', readonly=True,
        ondelete='cascade', check_company=True, copy=False)
    template_id = fields.Many2one(
        'construction.contract.condition', string='Plantilla', readonly=True, copy=False,
        help='Las condiciones de las que se copió esta.')

    # Adelanto
    advance_pct = fields.Float(string='Adelanto (%)', digits=(16, 6), tracking=True)
    advance_method = fields.Selection(
        ADVANCE_METHODS, string='Forma de amortizar', required=True, default='total',
        tracking=True)
    advance_fixed_amount = fields.Monetary(
        string='Amortización fija por valorizado', currency_field='currency_id',
        help='Solo con «Monto fijo por valorizado».')
    # Fondo de garantía
    guarantee_pct = fields.Float(string='Fondo de garantía (%)', digits=(16, 6), tracking=True)
    guarantee_base = fields.Selection(
        GUARANTEE_BASES, string='Base del fondo', required=True, default='total', tracking=True)
    guarantee_days = fields.Integer(string='Plazo de devolución (días)', tracking=True)
    guarantee_from = fields.Selection(
        GUARANTEE_FROM, string='Plazo contado', required=True, default='invoice',
        tracking=True)
    requirement_ids = fields.Many2many(
        'construction.contract.requirement', 'construction_condition_requirement_rel',
        'condition_id', 'requirement_id', string='Requisitos de devolución',
        help='Lo que debe cumplirse para devolver el fondo de garantía.')
    # Valorización
    frequency = fields.Selection(
        FREQUENCIES, string='Periodicidad', required=True, default='weekly', tracking=True,
        help='Semanal: la semana de liquidación de la obra (o el día de corte de abajo). '
             'Quincenal: del 1 al 15 y del 16 a fin de mes. Mensual: a fin de mes o al día de '
             'corte. Al término: una sola valorización, que es la liquidación.')
    cutoff_weekday = fields.Selection(
        [('0', 'Lunes'), ('1', 'Martes'), ('2', 'Miércoles'), ('3', 'Jueves'),
         ('4', 'Viernes'), ('5', 'Sábado'), ('6', 'Domingo')],
        string='Día de corte semanal',
        help='Vacío: el cierre de la semana de la obra. En una orden, fija el cierre de la '
             'semana de la obra, que usan el avance y la valorización.')
    monthly_cutoff = fields.Selection(
        MONTHLY_CUTOFFS, string='Corte mensual', default='month_end')
    cutoff_day = fields.Integer(string='Día de corte del mes', default=25)
    progress_tolerance_pct = fields.Float(
        string='Tolerancia de avance (%)', digits=(16, 2),
        help='Exceso de la cantidad acumulada sobre lo contratado que admite el avance sin '
             'autorización.')
    line_detail = fields.Selection(
        LINE_DETAILS, string='Líneas de la orden', required=True, default='task',
        help='Por partida: una línea de la orden por actividad y partida, con su analítica. '
             'Por actividad: una línea por actividad para toda la obra.')
    document_type_ids = fields.Many2many(
        'construction.contract.document.type', 'construction_condition_document_type_rel',
        'condition_id', 'document_type_id', string='Documentos requeridos',
        help='Los que la liquidación exige antes de cerrar la orden.')
    scheme_line_ids = fields.One2many(
        'construction.contract.scheme.line', 'condition_id', string='Esquema de cálculo',
        copy=True)
    note = fields.Text(string='Notas')

    _cutoff_day_range = models.Constraint(
        'CHECK (cutoff_day IS NULL OR (cutoff_day >= 1 AND cutoff_day <= 31))',
        'El día de corte del mes va del 1 al 31.')

    def _compute_currency_id(self):
        for condition in self:
            condition.currency_id = (condition.order_id.currency_id or condition.company_id.currency_id
                                     or self.env.company.currency_id)

    @api.constrains('advance_pct', 'guarantee_pct', 'progress_tolerance_pct')
    def _check_percentages(self):
        for condition in self:
            for value in (condition.advance_pct, condition.guarantee_pct):
                if value < 0 or value >= 100:
                    raise ValidationError(self.env._(
                        'Los porcentajes de adelanto y de fondo de garantía van de 0 a menos de '
                        '100 (%s).', condition.display_name))
            if condition.progress_tolerance_pct < 0:
                raise ValidationError(self.env._('La tolerancia de avance no puede ser negativa.'))

    @api.depends('name', 'order_id')
    def _compute_display_name(self):
        for condition in self:
            condition.display_name = '%s · %s' % (condition.order_id.name, condition.name) \
                if condition.order_id else condition.name

    # ------------------------------------------------------------------
    # Copia a la orden
    # ------------------------------------------------------------------
    def _copy_for_order(self, order, overrides=None):
        """Copia de las condiciones para ``order`` con los valores pactados en
        ``overrides``."""
        self.ensure_one()
        values = dict(order_id=order.id, template_id=self.id, company_id=order.company_id.id,
                      name=self.name, active=True)
        values.update(overrides or {})
        # sudo: la copia nace de la asignación de la contrata, que puede hacer
        # quien no administra la configuración; queda ligada a la orden.
        terms = self.sudo().copy(values).sudo(False)
        terms._construction_align_project_week()
        return terms

    def write(self, vals):
        self._check_order_locked(vals)
        res = super().write(vals)
        if {'frequency', 'cutoff_weekday'} & set(vals):
            self._construction_align_project_week()
        return res

    def _construction_align_project_week(self):
        """Una sola semana para el avance y la valorización (CREVAL v1.0,
        CR-10): el corte semanal de la orden fija el cierre de la semana de la
        obra. Si la obra ya tiene valorizaciones con otra semana, no se cambia
        y se pide corregir el corte."""
        Settlement = self.env['construction.contract.settlement'].sudo()
        weekdays = dict(self._fields['cutoff_weekday']._description_selection(self.env))
        for terms in self.filtered(lambda c: c.order_id and c.frequency == 'weekly'
                                   and c.cutoff_weekday):
            project = terms.order_id.construction_project_id
            start_day = str((int(terms.cutoff_weekday) + 1) % 7)
            if not project or project.construction_week_start_day == start_day:
                continue
            if Settlement.search_count([('project_id', '=', project.id),
                                        ('state', '!=', 'cancel')]):
                current = str((int(project.construction_week_start_day or '3') - 1) % 7)
                raise UserError(self.env._(
                    'La semana de la obra %(project)s cierra el %(current)s y ya tiene '
                    'valorizaciones: el corte del %(cutoff)s haría que el avance y la '
                    'valorización usen semanas distintas. Deje el corte del %(current)s o '
                    'cambie la semana en los ajustes de la obra.',
                    project=project.display_name, current=weekdays[current].lower(),
                    cutoff=weekdays[terms.cutoff_weekday].lower()))
            # sudo: quien asigna la contrata no siempre edita los ajustes de
            # la obra; solo se mueve el día de inicio de su semana.
            project.sudo().construction_week_start_day = start_day
            project.message_post(body=self.env._(
                'La semana de la obra cierra el %(day)s, el corte de la orden %(order)s: el '
                'avance y la valorización usan la misma semana.',
                day=weekdays[terms.cutoff_weekday].lower(), order=terms.order_id.name))

    def _check_order_locked(self, vals):
        """Con la orden confirmada, las condiciones solo las cambia el
        administrador del planificador (queda en el historial de la orden) o
        una ampliación aprobada."""
        tracked = set(vals) - {'message_main_attachment_id'}
        if not tracked or self.env.su or self.env.context.get('construction_amendment'):
            return
        locked = self.filtered(lambda c: c.order_id.state in ('purchase', 'done'))
        if not locked:
            return
        if not self.env.user.has_group('al_construction_planner.group_planner_manager'):
            raise UserError(self.env._(
                'La orden %s ya está confirmada: sus condiciones las cambia el administrador del '
                'planificador o una ampliación aprobada.', ', '.join(locked.order_id.mapped('name'))))
        labels = ', '.join(self._fields[name].string for name in sorted(tracked)
                           if name in self._fields)
        for condition in locked:
            condition.order_id.message_post(body=self.env._(
                'Condiciones de contrata cambiadas por el administrador: %s.', labels))

    def _scheme_lines(self, kind=None):
        lines = self.scheme_line_ids.sorted(lambda l: (l.sequence, l.id))
        return lines.filtered(lambda l: l.kind == kind) if kind else lines

    @api.model
    def _default_scheme_values(self):
        """Esquema del producto: el del ejemplo «Contrato de obra»."""
        return [
            {'sequence': 10, 'name': 'Gastos generales y utilidades', 'kind': 'price_adjustment',
             'base': 'direct_additional', 'percent': 0.0, 'sign': 'add',
             'invoice_mode': 'service_line'},
            {'sequence': 20, 'name': 'Descuento', 'kind': 'price_adjustment',
             'base': 'direct_additional', 'percent': 0.0, 'sign': 'subtract',
             'invoice_mode': 'service_line'},
            {'sequence': 30, 'name': 'Deductivos', 'kind': 'deduction', 'base': 'own',
             'sign': 'subtract', 'invoice_mode': 'own_line'},
            {'sequence': 40, 'name': 'IGV', 'kind': 'tax', 'base': 'subtotal', 'percent': 18.0,
             'sign': 'add', 'invoice_mode': 'tax'},
            {'sequence': 50, 'name': 'Adelanto', 'kind': 'advance', 'base': 'total',
             'sign': 'subtract', 'invoice_mode': 'regularization'},
            {'sequence': 60, 'name': 'Fondo de garantía', 'kind': 'retention', 'base': 'total',
             'sign': 'subtract', 'invoice_mode': 'installment'},
        ]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if 'scheme_line_ids' not in vals and not self.env.context.get('construction_no_scheme'):
                vals['scheme_line_ids'] = [Command.create(v) for v in self._default_scheme_values()]
        return super().create(vals_list)


class ConstructionContractSchemeLine(models.Model):
    _name = 'construction.contract.scheme.line'
    _description = 'Concepto del esquema de cálculo de la contrata'
    _order = 'sequence, id'

    condition_id = fields.Many2one(
        'construction.contract.condition', string='Condiciones', required=True,
        ondelete='cascade', index=True)
    sequence = fields.Integer(string='Secuencia', default=10)
    name = fields.Char(string='Concepto', required=True, translate=True)
    kind = fields.Selection(SCHEME_KINDS, string='Tipo', required=True)
    base = fields.Selection(SCHEME_BASES, string='Base', required=True, default='direct')
    percent = fields.Float(
        string='%', digits=(16, 6),
        help='En el adelanto y el fondo de garantía manda el porcentaje de las condiciones.')
    sign = fields.Selection(SCHEME_SIGNS, string='Signo', required=True, default='add')
    invoice_mode = fields.Selection(INVOICE_MODES, string='En la factura', required=True,
                                    default='service_line')
    account_id = fields.Many2one(
        'account.account', string='Cuenta',
        help='Solo para «Línea propia» de un ajuste de precio; vacía: la del servicio.')
    effective_percent = fields.Float(
        string='% aplicado', digits=(16, 6), compute='_compute_effective',
        help='El del concepto o, en el adelanto y el fondo, el de las condiciones.')
    effective_base = fields.Selection(SCHEME_BASES, string='Base aplicada',
                                      compute='_compute_effective')

    @api.depends('percent', 'base', 'kind', 'condition_id.advance_pct',
                 'condition_id.advance_method', 'condition_id.guarantee_pct',
                 'condition_id.guarantee_base')
    def _compute_effective(self):
        for line in self:
            condition = line.condition_id
            if line.kind == 'advance':
                line.effective_percent = condition.advance_pct
                line.effective_base = 'subtotal' if condition.advance_method == 'subtotal' \
                    else 'total'
            elif line.kind == 'retention':
                line.effective_percent = condition.guarantee_pct
                line.effective_base = condition.guarantee_base
            else:
                line.effective_percent = line.percent
                line.effective_base = 'own' if line.kind == 'deduction' else line.base

    @api.constrains('kind', 'invoice_mode', 'base')
    def _check_mode(self):
        for line in self:
            if line.invoice_mode not in KIND_INVOICE_MODES[line.kind]:
                modes = dict(INVOICE_MODES)
                raise ValidationError(self.env._(
                    '%(concept)s: un concepto de este tipo va en la factura como %(modes)s.',
                    concept=line.name, modes=', '.join(
                        modes[m].lower() for m in KIND_INVOICE_MODES[line.kind])))
            if line.kind == 'price_adjustment' and line.base in ('subtotal', 'total', 'own'):
                raise ValidationError(self.env._(
                    '%s: un ajuste de precio se calcula sobre el costo directo (con o sin '
                    'adicionales).', line.name))
            if line.kind == 'tax' and line.base != 'subtotal':
                raise ValidationError(self.env._(
                    '%s: un impuesto se calcula sobre el subtotal.', line.name))

    @api.constrains('kind', 'condition_id')
    def _check_unique_kinds(self):
        for condition in self.condition_id:
            for kind in ('deduction', 'advance', 'retention'):
                if len(condition.scheme_line_ids.filtered(lambda l: l.kind == kind)) > 1:
                    raise ValidationError(self.env._(
                        'El esquema de %(condition)s tiene más de un concepto de tipo '
                        '«%(kind)s».', condition=condition.display_name,
                        kind=dict(SCHEME_KINDS)[kind]))

    def write(self, vals):
        self.condition_id._check_order_locked(vals)
        return super().write(vals)


def compute_cascade(condition, currency, direct, additional, deductions, advance=None,
                    advance_pct=None, guarantee_pct=None):
    """Resumen del valorizado según el esquema de ``condition``.

    ``advance`` es la amortización ya decidida (tope, monto fijo o manual); si
    es None se calcula con el porcentaje. ``advance_pct`` y ``guarantee_pct``
    reemplazan los de las condiciones (lo pactado en el asistente). Devuelve ``(filas, totales)``: una
    fila por concepto del esquema (en su secuencia) con su importe con signo y
    los totales ``direct``, ``additional``, ``subtotal``, ``tax``, ``total``,
    ``advance``, ``retention``, ``deductions``, ``adjustments`` y ``to_pay``."""
    lines = condition._scheme_lines()
    bases = {'direct': direct, 'direct_additional': direct + additional}
    rows = {}
    adjustments = 0.0
    for line in lines.filtered(lambda l: l.kind == 'price_adjustment'):
        amount = currency.round(bases[line.base] * line.percent / 100.0)
        amount = amount if line.sign == 'add' else -amount
        rows[line.id] = amount
        adjustments += amount
    deduction_line = lines.filtered(lambda l: l.kind == 'deduction')[:1]
    if deduction_line:
        rows[deduction_line.id] = -deductions if deduction_line.sign == 'subtract' else deductions
    deduction_amount = rows.get(deduction_line.id, -deductions)
    # Descontado al pago, el deductivo no baja la base de la factura: se
    # resta del total a pagar.
    at_payment = deduction_line.invoice_mode == 'payment_discount'
    subtotal = currency.round(direct + additional + adjustments
                              + (0.0 if at_payment else deduction_amount))
    tax = 0.0
    for line in lines.filtered(lambda l: l.kind == 'tax'):
        amount = currency.round(subtotal * line.percent / 100.0)
        amount = amount if line.sign == 'add' else -amount
        rows[line.id] = amount
        tax += amount
    total = currency.round(subtotal + tax)
    bases.update(subtotal=subtotal, total=total)
    advance_line = lines.filtered(lambda l: l.kind == 'advance')[:1]
    if advance is None:
        base = subtotal if condition.advance_method == 'subtotal' else total
        pct = condition.advance_pct if advance_pct is None else advance_pct
        advance = currency.round(base * pct / 100.0)
    pct = condition.guarantee_pct if guarantee_pct is None else guarantee_pct
    retention = currency.round(bases[condition.guarantee_base] * pct / 100.0)
    if advance_line:
        rows[advance_line.id] = -advance
    retention_line = lines.filtered(lambda l: l.kind == 'retention')[:1]
    if retention_line:
        rows[retention_line.id] = -retention
    totals = {
        'direct': direct, 'additional': additional, 'adjustments': adjustments,
        'deductions': -deduction_amount, 'subtotal': subtotal, 'tax': tax, 'total': total,
        'advance': advance, 'retention': retention,
        'to_pay': currency.round(total - advance - retention
                                 + (deduction_amount if at_payment else 0.0)),
    }
    return rows, totals

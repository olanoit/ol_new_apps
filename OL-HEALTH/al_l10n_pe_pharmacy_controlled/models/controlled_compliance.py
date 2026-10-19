# -*- coding: utf-8 -*-
"""Cumplimiento del DS 023-2001-SA verificado en docs/farmacia/VERIFICACIONES.md:

* Libros de estupefacientes y de psicotrópicos por local, foliados y visados
  por la autoridad de salud (visación D5) o registro electrónico «RE»
  calificado por DIGEMID.
* Balance trimestral de las listas IIA, IIIA, IIIB y IIIC: se cierra el último
  día del trimestre y se presenta dentro de los 15 días calendario
  siguientes, con las recetas especiales originales. El saldo final debe
  cuadrar con el stock (art. 41); una diferencia necesita su justificación.
"""
from datetime import datetime, time, timedelta

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

# Listas que van en el balance trimestral (el cannabis tiene su propio registro).
BALANCE_LISTS = ('IIA', 'IIIA', 'IIIB', 'IIIC')
BALANCE_DEADLINE_DAYS = 15
BOOKS = [
    ('narcotic', 'Libro de estupefacientes'),
    ('psychotropic', 'Libro de psicotrópicos'),
    ('cannabis', 'Registro de cannabis'),
]
QUARTERS = [('1', 'Enero - marzo'), ('2', 'Abril - junio'), ('3', 'Julio - setiembre'),
            ('4', 'Octubre - diciembre')]


def quarter_dates(year, quarter):
    first_month = (int(quarter) - 1) * 3 + 1
    date_from = fields.Date.to_date('%04d-%02d-01' % (year, first_month))
    last_month = first_month + 2
    next_month = fields.Date.to_date('%04d-%02d-01' % (year + (last_month == 12), last_month % 12 + 1))
    return date_from, next_month - timedelta(days=1)


class PharmacyControlledBookRegister(models.Model):
    _name = 'pharmacy.controlled.book.register'
    _description = 'Libro oficial de controlados'
    _order = 'warehouse_id, book, date_start desc'
    _check_company_auto = True

    name = fields.Char(string='Libro', compute='_compute_name', store=True)
    warehouse_id = fields.Many2one('stock.warehouse', string='Local', required=True,
                                   check_company=True, index=True)
    book = fields.Selection(BOOKS, string='Tipo de libro', required=True)
    mode = fields.Selection([('physical', 'Libro foliado y visado'),
                             ('electronic', 'Registro electrónico (RE)')],
                            string='Modalidad', required=True, default='physical')
    folio_from = fields.Integer(string='Folio desde')
    folio_to = fields.Integer(string='Folio hasta')
    visa_number = fields.Char(string='Visación (D5)',
                              help='Número de la visación del libro por la DIRIS, DIRESA o GERESA.')
    visa_date = fields.Date(string='Fecha de visación')
    authority = fields.Char(string='Autoridad', help='DIRIS, DIRESA o GERESA que visó el libro.')
    electronic_resolution = fields.Char(
        string='Resolución del registro electrónico',
        help='Resolución de DIGEMID que califica el registro electrónico («RE»).')
    electronic_date = fields.Date(string='Fecha de la resolución')
    date_start = fields.Date(string='En uso desde', required=True,
                             default=fields.Date.context_today)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', string='Compañía', required=True, readonly=True,
                                 default=lambda self: self.env.company)

    _active_book_unique = models.UniqueIndex(
        '(warehouse_id, book) WHERE active IS TRUE',
        'Cada local tiene un solo libro activo de cada tipo.')

    @api.depends('warehouse_id', 'book', 'mode')
    def _compute_name(self):
        books = dict(BOOKS)
        for register in self:
            register.name = '%s · %s' % (books.get(register.book, ''), register.warehouse_id.name or '')

    @api.constrains('mode', 'folio_from', 'folio_to', 'visa_number', 'electronic_resolution')
    def _check_mode_data(self):
        for register in self:
            if register.mode == 'physical':
                if not register.visa_number:
                    raise ValidationError(self.env._('Indique la visación (D5) del libro foliado.'))
                if register.folio_from <= 0 or register.folio_to < register.folio_from:
                    raise ValidationError(self.env._('Indique el rango de folios del libro.'))
            elif not register.electronic_resolution:
                raise ValidationError(self.env._(
                    'Indique la resolución de DIGEMID que califica el registro electrónico.'))

    @api.model
    def _get_active(self, warehouse, book):
        return self.search([('warehouse_id', '=', warehouse.id), ('book', '=', book)], limit=1)


class PharmacyControlledBalance(models.Model):
    _name = 'pharmacy.controlled.balance'
    _description = 'Balance trimestral de controlados'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_to desc, warehouse_id, book'
    _check_company_auto = True

    name = fields.Char(string='Balance', compute='_compute_name', store=True)
    warehouse_id = fields.Many2one('stock.warehouse', string='Local', required=True,
                                   check_company=True, index=True)
    book = fields.Selection(BOOKS[:2], string='Sustancias', required=True, default='psychotropic')
    year = fields.Integer(string='Año', required=True,
                          default=lambda self: fields.Date.today().year)
    quarter = fields.Selection(QUARTERS, string='Trimestre', required=True,
                               default=lambda self: str((fields.Date.today().month - 1) // 3 + 1))
    date_from = fields.Date(string='Desde', compute='_compute_dates', store=True)
    date_to = fields.Date(string='Cierre', compute='_compute_dates', store=True)
    deadline = fields.Date(string='Presentar hasta', compute='_compute_dates', store=True,
                           help='15 días calendario después del cierre del trimestre.')
    form_code = fields.Char(string='Formato de la autoridad',
                            help='Nombre o código del formato que pide la DIRIS, DIRESA o GERESA '
                                 '(cada una usa el suyo).')
    state = fields.Selection([('draft', 'Borrador'), ('computed', 'Calculado'),
                              ('submitted', 'Presentado')],
                             string='Estado', default='draft', required=True, tracking=True)
    submitted_date = fields.Date(string='Presentado el', readonly=True, tracking=True)
    authority_reference = fields.Char(string='Expediente o cargo', tracking=True)
    line_ids = fields.One2many('pharmacy.controlled.balance.line', 'balance_id', string='Productos')
    difference_count = fields.Integer(string='Productos con diferencia',
                                      compute='_compute_difference_count')
    difference_note = fields.Text(
        string='Justificación de diferencias',
        help='Robo, pérdida o merma, con la autorización de la autoridad (art. 41).')
    company_id = fields.Many2one('res.company', string='Compañía', required=True, readonly=True,
                                 default=lambda self: self.env.company)

    _period_unique = models.Constraint(
        'unique(warehouse_id, book, year, quarter)',
        'Ya existe el balance de ese trimestre para el local.')

    @api.depends('warehouse_id', 'book', 'year', 'quarter')
    def _compute_name(self):
        books = dict(BOOKS)
        for balance in self:
            balance.name = '%s T%s %s · %s' % (
                books.get(balance.book, '').replace('Libro de ', '').capitalize(),
                balance.quarter or '', balance.year or '', balance.warehouse_id.name or '')

    @api.depends('year', 'quarter')
    def _compute_dates(self):
        for balance in self:
            if balance.year and balance.quarter:
                balance.date_from, balance.date_to = quarter_dates(balance.year, balance.quarter)
                balance.deadline = balance.date_to + timedelta(days=BALANCE_DEADLINE_DAYS)
            else:
                balance.date_from = balance.date_to = balance.deadline = False

    @api.depends('line_ids.difference')
    def _compute_difference_count(self):
        for balance in self:
            rounding = 0.0001
            balance.difference_count = len(balance.line_ids.filtered(
                lambda line: abs(line.difference) > rounding))

    def _report_wizard(self):
        self.ensure_one()
        return self.env['pharmacy.controlled.report'].create({
            'report_type': 'balance', 'book': self.book, 'warehouse_id': self.warehouse_id.id,
            'year': self.year, 'quarter': self.quarter, 'company_id': self.company_id.id})

    def _stock_at_closing(self, product):
        self.ensure_one()
        return product.with_context(
            location=self.warehouse_id.view_location_id.id,
            to_date=datetime.combine(self.date_to, time.max)).qty_available

    def action_compute(self):
        for balance in self:
            if balance.state == 'submitted':
                raise UserError(self.env._('El balance %s ya se presentó.', balance.name))
            rows = [row for row in balance._report_wizard()._get_balance_lines()
                    if row['control_list'] in BALANCE_LISTS]
            balance.line_ids = [fields.Command.clear()] + [fields.Command.create({
                'product_id': row['product'].id,
                'initial': row['initial'], 'qty_in': row['qty_in'], 'qty_out': row['qty_out'],
                'final': row['final'], 'stock_qty': balance._stock_at_closing(row['product']),
            }) for row in rows]
            balance.state = 'computed'

    def action_submit(self):
        for balance in self:
            if balance.state != 'computed':
                raise UserError(self.env._('Calcule el balance %s antes de presentarlo.', balance.name))
            if balance.difference_count and not balance.difference_note:
                raise UserError(self.env._(
                    'El saldo de %(count)s producto(s) no cuadra con el stock: justifique la '
                    'diferencia (robo, pérdida o merma autorizada) antes de presentar %(name)s.',
                    count=balance.difference_count, name=balance.name))
        self.write({'state': 'submitted', 'submitted_date': fields.Date.context_today(self)})
        self.activity_feedback(['mail.mail_activity_data_todo'])

    def action_draft(self):
        self.write({'state': 'draft', 'submitted_date': False})

    def action_print(self):
        return self.env.ref(
            'al_l10n_pe_pharmacy_controlled.action_report_controlled_balance_record').report_action(self)

    def _get_period_prescriptions(self):
        self.ensure_one()
        return self._report_wizard()._get_period_prescriptions().filtered(
            lambda p: any(d.product_id.pharmacy_control_list in BALANCE_LISTS
                          for d in p.dispensation_ids))

    @api.model
    def _cron_quarter_balances(self):
        """El primer día de cada trimestre: balance en borrador del trimestre
        anterior por local y tipo de sustancia que tuvo movimiento, con una
        actividad para el director técnico que vence el día 15."""
        activity_type = self.env.ref('mail.mail_activity_data_todo', raise_if_not_found=False)
        today = fields.Date.context_today(self)
        if today.month not in (1, 4, 7, 10) or today.day != 1:
            return
        quarter = str((today.month - 2) // 3 + 1) if today.month != 1 else '4'
        year = today.year if today.month != 1 else today.year - 1
        date_from, date_to = quarter_dates(year, quarter)
        for warehouse in self.env['stock.warehouse'].search([]):
            Balance = self.with_company(warehouse.company_id)
            for book in ('narcotic', 'psychotropic'):
                moved = self.env['stock.move.line'].search_count([
                    ('state', '=', 'done'), ('company_id', '=', warehouse.company_id.id),
                    ('product_id.pharmacy_control_book', '=', book),
                    ('product_id.pharmacy_control_list', 'in', BALANCE_LISTS),
                    ('date', '<=', datetime.combine(date_to, time.max)),
                    '|', ('location_id', 'child_of', warehouse.view_location_id.id),
                    ('location_dest_id', 'child_of', warehouse.view_location_id.id),
                ], limit=1)
                if not moved or Balance.search_count([
                        ('warehouse_id', '=', warehouse.id), ('book', '=', book),
                        ('year', '=', year), ('quarter', '=', quarter)]):
                    continue
                balance = Balance.create({'warehouse_id': warehouse.id, 'book': book,
                                          'year': year, 'quarter': quarter,
                                          'company_id': warehouse.company_id.id})
                user = warehouse.pharmacy_director_id.user_id
                if user and activity_type:
                    balance.activity_schedule(
                        activity_type_id=activity_type.id, user_id=user.id,
                        date_deadline=balance.deadline,
                        summary=self.env._('Presentar el balance trimestral'),
                        note=self.env._('Calcule, revise el cuadre con el stock y presente %(name)s '
                                        'con las recetas especiales originales hasta el %(date)s.',
                                        name=balance.name, date=balance.deadline))


class PharmacyControlledBalanceLine(models.Model):
    _name = 'pharmacy.controlled.balance.line'
    _description = 'Producto del balance trimestral'
    _order = 'balance_id, product_id'

    balance_id = fields.Many2one('pharmacy.controlled.balance', required=True, ondelete='cascade',
                                 index=True)
    company_id = fields.Many2one(related='balance_id.company_id', store=True)
    product_id = fields.Many2one('product.product', string='Producto', required=True)
    control_list = fields.Selection(related='product_id.pharmacy_control_list', string='Lista')
    composition = fields.Char(related='product_id.pharmacy_composition', string='Principio activo')
    uom_id = fields.Many2one(related='product_id.uom_id', string='Unidad')
    initial = fields.Float(string='Saldo anterior', digits='Product Unit')
    qty_in = fields.Float(string='Ingresos', digits='Product Unit')
    qty_out = fields.Float(string='Egresos', digits='Product Unit')
    final = fields.Float(string='Saldo final', digits='Product Unit')
    stock_qty = fields.Float(string='Stock al cierre', digits='Product Unit')
    difference = fields.Float(string='Diferencia', digits='Product Unit',
                              compute='_compute_difference', store=True)

    @api.depends('final', 'stock_qty')
    def _compute_difference(self):
        for line in self:
            line.difference = line.stock_qty - line.final

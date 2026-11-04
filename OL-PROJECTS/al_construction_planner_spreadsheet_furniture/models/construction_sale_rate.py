# -*- coding: utf-8 -*-
"""Tarifario de venta de mobiliario (paquete 1.17, M117-19, decisión del 04-nov).

Los ítems no son productos: no se venden, no se facturan ni se guardan. Lleva solo
lo que el precio necesita y se carga desde Excel con la importación nativa.
"""
from odoo import api, fields, models
from odoo.exceptions import ValidationError

from .sale_sheet import PARTIDAS, RATE_GROUPS


class ConstructionSaleRate(models.Model):
    _name = 'construction.sale.rate'
    _description = 'Tarifario de venta de mobiliario'
    _order = 'partida, item, date_from desc, id'
    _check_company_auto = True

    company_id = fields.Many2one('res.company', string='Compañía', required=True, index=True,
                                 default=lambda self: self.env.company)
    partida = fields.Selection([(name, name) for name in PARTIDAS], string='Partida',
                               required=True)
    item = fields.Char(string='Ítem', required=True)
    uom = fields.Selection([('ML', 'ML'), ('UND', 'UND')], string='Unidad', required=True,
                           default='UND')
    base_size = fields.Float(string='Medida base (cm)')
    adjust = fields.Selection([('Alto', 'Alto'), ('Ancho', 'Ancho'), ('Ninguna', 'Ninguna')],
                              string='Medida que ajusta', required=True, default='Ninguna')
    structure = fields.Boolean(string='Lleva estructura')
    fronts = fields.Boolean(string='Lleva frentes')
    rule = fields.Selection([('Por costo', 'Por costo')], string='Regla')
    group = fields.Selection([(name, name) for name in RATE_GROUPS], string='Grupo',
                             required=True, default='Accesorio')
    price = fields.Float(string='Precio base', digits='Product Price')
    currency_id = fields.Many2one('res.currency', string='Moneda', required=True,
                                  default=lambda self: self.env.company.currency_id)
    partner_id = fields.Many2one('res.partner', string='Cliente con convenio', index=True,
                                 help='Vacío: lista general.')
    date_from = fields.Date(string='Desde')
    date_to = fields.Date(string='Hasta')
    active = fields.Boolean(string='Activo', default=True)

    def _same_line_domain(self):
        self.ensure_one()
        return [('id', '!=', self.id), ('company_id', '=', self.company_id.id),
                ('partida', '=', self.partida), ('item', '=', self.item),
                ('currency_id', '=', self.currency_id.id),
                ('partner_id', '=', self.partner_id.id)]

    @api.model_create_multi
    def create(self, vals_list):
        rates = self.browse()
        # Uno por uno: al importar un precio con «Desde», cierra el anterior antes
        # de que la regla de vigencias lo revise (M117-19, punto 1).
        for vals in vals_list:
            rate = super(ConstructionSaleRate, self.with_context(
                construction_rate_closing=True)).create([vals])
            rate._close_previous()
            rates |= rate
        rates._check_periods()
        return rates

    def _close_previous(self):
        for rate in self.filtered('date_from'):
            previous = self.search(rate._same_line_domain() + [
                '|', ('date_from', '=', False), ('date_from', '<', rate.date_from),
                '|', ('date_to', '=', False), ('date_to', '>=', rate.date_from)])
            previous.write({'date_to': fields.Date.subtract(rate.date_from, days=1)})

    @api.constrains('date_from', 'date_to', 'partida', 'item', 'currency_id', 'partner_id',
                    'company_id', 'active')
    def _check_periods(self):
        if self.env.context.get('construction_rate_closing'):
            return
        for rate in self.filtered('active'):
            if rate.date_from and rate.date_to and rate.date_to < rate.date_from:
                raise ValidationError(self.env._(
                    '%s: «Hasta» es anterior a «Desde».', rate.item))
            for other in self.search(rate._same_line_domain()):
                starts_before = not rate.date_to or not other.date_from \
                    or other.date_from <= rate.date_to
                ends_after = not rate.date_from or not other.date_to \
                    or other.date_to >= rate.date_from
                if starts_before and ends_after:
                    raise ValidationError(self.env._(
                        'Hay dos líneas vigentes para %(partida)s · %(item)s en la misma moneda '
                        'y cliente.', partida=rate.partida, item=rate.item))

    @api.model
    def _construction_rates_for(self, company, currency, partner, date):
        """Las líneas de una hoja: vigentes a ``date``, en ``currency``; las del
        cliente con convenio y, lo que su convenio no tiene, de la lista general."""
        lines = self.search([
            ('company_id', '=', company.id), ('currency_id', '=', currency.id),
            ('partner_id', 'in', [False, partner.commercial_partner_id.id]),
            '|', ('date_from', '=', False), ('date_from', '<=', date),
            '|', ('date_to', '=', False), ('date_to', '>=', date)])
        result = {}
        # Las de la lista general primero: las del convenio las reemplazan.
        for line in lines.sorted(lambda rate: bool(rate.partner_id)):
            result[(line.partida, line.item)] = line
        return list(result.values())

    def _sheet_row(self):
        """Fila de TARIFARIO, en el orden de sus columnas de dato, y el id."""
        self.ensure_one()
        return {
            'A': self.partida, 'B': self.item, 'C': self.uom,
            'D': ('%g' % self.base_size) if self.base_size else '', 'E': self.adjust,
            'F': '%s' % self.price, 'G': 'Sí' if self.structure else 'No',
            'H': 'Sí' if self.fronts else 'No', 'I': self.rule or '', 'J': self.group,
            'L': str(self.id),
        }

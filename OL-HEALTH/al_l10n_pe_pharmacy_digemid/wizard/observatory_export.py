# -*- coding: utf-8 -*-
"""Archivo de precios para el Observatorio Peruano de Productos
Farmacéuticos (Directiva 176-MINSA/DIGEMID, RM 341-2011).

Formato (docs/farmacia/VERIFICACIONES.md): hoja «Hoja1» con el código del
establecimiento como texto, el código de producto del catálogo de DIGEMID y
los precios de venta al público con IGV y 2 decimales: «Precio 1» por
empaque y «Precio 2» por unidad. Solo medicamentos y productos biológicos en
oferta y con stock en el local.

La primera carga del mes lleva toda la oferta (reemplaza la lista del
local); las siguientes, solo los precios que cambiaron desde la última carga.

Las columnas están en OBSERVATORY_COLUMNS para ajustarlas a la plantilla que
descarga el aplicativo: confírmela antes de la primera carga."""
import io

import xlsxwriter

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools import BinaryBytes

from ..models.product_template import OBSERVATORY_CLASSES

OBSERVATORY_SHEET = 'Hoja1'
OBSERVATORY_COLUMNS = [
    ('establishment_code', 'CodEstab'),
    ('digemid_code', 'CodProd'),
    ('package_price', 'Precio 1'),
    ('unit_price', 'Precio 2'),
]
RECTIFICATION_BUSINESS_DAYS = 7


class PharmacyObservatoryExport(models.TransientModel):
    _name = 'pharmacy.observatory.export'
    _description = 'Exportar precios al Observatorio'
    _check_company_auto = True

    warehouse_id = fields.Many2one('stock.warehouse', string='Local', required=True,
                                   check_company=True,
                                   default=lambda self: self.env['stock.warehouse'].search(
                                       [('company_id', '=', self.env.company.id)], limit=1))
    scope = fields.Selection([('pending', 'Solo los cambios desde la última carga'),
                              ('all', 'Carga completa del mes (toda la oferta en existencia)')],
                             string='Qué exportar', compute='_compute_scope',
                             store=True, readonly=False)
    needs_full = fields.Boolean(compute='_compute_scope', store=True,
                                help='El local aún no hizo la carga completa de este mes.')
    company_id = fields.Many2one('res.company', required=True, readonly=True,
                                 default=lambda self: self.env.company)
    file_data = fields.Binary(readonly=True)
    file_name = fields.Char(readonly=True)

    @api.depends('warehouse_id')
    def _compute_scope(self):
        Submission = self.env['pharmacy.observatory.submission']
        for wizard in self:
            wizard.needs_full = bool(wizard.warehouse_id) and not Submission._has_full_this_month(
                wizard.warehouse_id)
            wizard.scope = 'all' if wizard.needs_full else 'pending'

    # ------------------------------------------------------------------
    # Datos
    # ------------------------------------------------------------------
    def _price_with_tax(self, template, price):
        """Precio de venta al público con IGV, como lo informa el Observatorio."""
        taxes = template.taxes_id._filter_taxes_by_company(self.company_id)
        if not taxes:
            return self.company_id.currency_id.round(price)
        result = taxes.compute_all(price, currency=self.company_id.currency_id, quantity=1.0,
                                   product=template.product_variant_id)
        return self.company_id.currency_id.round(result['total_included'])

    def _row(self, template, unit_price, package_price):
        return {
            'digemid_code': template.pharmacy_digemid_code,
            'unit_price': self._price_with_tax(template, unit_price),
            'package_price': self._price_with_tax(template, package_price),
        }

    def _offer(self):
        """Medicamentos y biológicos con código DIGEMID, a la venta y con stock
        en el local."""
        self.ensure_one()
        templates = self.env['product.template'].with_context(
            warehouse_id=self.warehouse_id.id).search([
                ('pharmacy_ok', '=', True), ('pharmacy_digemid_code', '!=', False),
                ('pharmacy_digemid_class', 'in', OBSERVATORY_CLASSES), ('sale_ok', '=', True),
                '|', ('company_id', '=', False), ('company_id', '=', self.company_id.id)])
        return templates.filtered(lambda t: t.qty_available > 0)

    def _rows(self):
        self.ensure_one()
        Price = self.env['pharmacy.observatory.price']
        offer = self._offer()
        if self.scope == 'pending':
            domain = [('company_id', '=', self.company_id.id),
                      ('product_tmpl_id.pharmacy_digemid_class', 'in', OBSERVATORY_CLASSES)]
            last = self.env['pharmacy.observatory.submission']._last_sent(self.warehouse_id)
            # Los cambios desde la última carga de este local (otro local pudo
            # haber marcado el precio como informado).
            domain += [('date', '>=', last.date_sent)] if last else [('state', '=', 'pending')]
            prices = Price.search(domain, order='date desc, id desc')
            # Un producto pudo cambiar varias veces: va solo su último precio.
            latest = {}
            for price in prices:
                latest.setdefault(price.product_tmpl_id, price)
            rows = [self._row(p.product_tmpl_id, p.unit_price, p.package_price)
                    for p in latest.values()]
            return prices, rows
        rows = []
        for template in offer:
            box = template.pharmacy_presentation_ids.sorted('factor')[-1:]
            rows.append(self._row(template, template.list_price,
                                  box.price if box else template.list_price))
        prices = Price.search([('state', '=', 'pending'), ('company_id', '=', self.company_id.id),
                               ('product_tmpl_id', 'in', offer.ids)])
        return prices, rows

    # ------------------------------------------------------------------
    # Exportación
    # ------------------------------------------------------------------
    def action_export(self):
        self.ensure_one()
        code = self.warehouse_id.pharmacy_establishment_code
        if not code:
            raise UserError(self.env._('El local %s no tiene código de establecimiento.',
                                       self.warehouse_id.name))
        Submission = self.env['pharmacy.observatory.submission']
        if self.scope == 'pending' and not Submission._has_full_this_month(self.warehouse_id):
            raise UserError(self.env._(
                'La primera carga del mes del local %s debe ser completa: reemplaza la lista de '
                'precios del establecimiento en el Observatorio.', self.warehouse_id.name))
        prices, rows = self._rows()
        if not rows:
            raise UserError(self.env._('No hay precios para informar.'))
        buffer = io.BytesIO()
        workbook = xlsxwriter.Workbook(buffer, {'in_memory': True})
        sheet = workbook.add_worksheet(OBSERVATORY_SHEET)
        money = workbook.add_format({'num_format': '0.00'})
        text = workbook.add_format({'num_format': '@'})
        for col, (_key, header) in enumerate(OBSERVATORY_COLUMNS):
            sheet.write_string(0, col, header)
        for row_index, row in enumerate(rows, start=1):
            row = {**row, 'establishment_code': code}
            for col, (key, _header) in enumerate(OBSERVATORY_COLUMNS):
                value = row[key]
                if isinstance(value, float):
                    sheet.write_number(row_index, col, value, money)
                else:
                    sheet.write_string(row_index, col, value or '', text)
        workbook.close()
        now = fields.Datetime.now()
        today = fields.Date.context_today(self)
        file_name = 'observatorio_%s_%s.xlsx' % (code, today)
        prices.write({'state': 'reported', 'reported_date': now})
        month = Submission._month_start(today)
        submission = Submission.search([('warehouse_id', '=', self.warehouse_id.id),
                                        ('period', '=', month), ('state', '=', 'draft')], limit=1)
        values = {
            'state': 'sent', 'mode': 'full' if self.scope == 'all' else 'changes',
            'date_sent': now, 'user_id': self.env.uid, 'line_count': len(rows),
            'rectification_deadline': self.company_id._pharmacy_add_business_days(
                today, RECTIFICATION_BUSINESS_DAYS),
            'file_data': BinaryBytes(buffer.getvalue()), 'file_name': file_name,
        }
        if submission:
            submission.write(values)
            submission.activity_feedback(['mail.mail_activity_data_todo'])
        else:
            submission = Submission.create({**values, 'warehouse_id': self.warehouse_id.id,
                                            'period': month, 'company_id': self.company_id.id})
        self.write({'file_data': values['file_data'], 'file_name': file_name})
        return {
            'type': 'ir.actions.act_url',
            'url': '/web/content/%s/%s/file_data/%s?download=true' % (self._name, self.id,
                                                                       self.file_name),
            'target': 'self',
        }

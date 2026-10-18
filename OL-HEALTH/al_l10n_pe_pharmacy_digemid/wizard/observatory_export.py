# -*- coding: utf-8 -*-
"""Archivo de precios para el Observatorio. DIGEMID rechaza cargas que no
respetan su plantilla (RD DFAU 018-2021): las columnas están en
OBSERVATORY_COLUMNS para ajustarlas a la plantilla vigente [VERIFICAR con la
DIRIS o el gestor del Observatorio antes de la primera carga]."""
import base64
import io

import xlsxwriter

from odoo import api, fields, models
from odoo.exceptions import UserError

OBSERVATORY_COLUMNS = [
    ('establishment_code', 'COD_ESTABLECIMIENTO'),
    ('digemid_code', 'COD_PRODUCTO'),
    ('package_price', 'PRECIO_EMPAQUE'),
    ('unit_price', 'PRECIO_UNITARIO'),
]


class PharmacyObservatoryExport(models.TransientModel):
    _name = 'pharmacy.observatory.export'
    _description = 'Exportar precios al Observatorio'
    _check_company_auto = True

    warehouse_id = fields.Many2one('stock.warehouse', string='Local', required=True,
                                   check_company=True,
                                   default=lambda self: self.env['stock.warehouse'].search(
                                       [('company_id', '=', self.env.company.id)], limit=1))
    scope = fields.Selection([('pending', 'Solo los cambios pendientes'),
                              ('all', 'Toda la oferta en existencia')],
                             string='Qué exportar', required=True, default='pending')
    company_id = fields.Many2one('res.company', required=True, readonly=True,
                                 default=lambda self: self.env.company)
    file_data = fields.Binary(readonly=True)
    file_name = fields.Char(readonly=True)

    def _rows(self):
        self.ensure_one()
        Price = self.env['pharmacy.observatory.price']
        if self.scope == 'pending':
            prices = Price.search([('state', '=', 'pending'), ('company_id', '=', self.company_id.id)])
            return prices, [{'digemid_code': p.digemid_code, 'unit_price': p.unit_price,
                             'package_price': p.package_price} for p in prices]
        templates = self.env['product.template'].with_context(
            warehouse_id=self.warehouse_id.id).search([
                ('pharmacy_ok', '=', True), ('pharmacy_digemid_code', '!=', False),
                '|', ('company_id', '=', False), ('company_id', '=', self.company_id.id)])
        rows = []
        for template in templates.filtered(lambda t: t.qty_available > 0):
            box = template.pharmacy_presentation_ids.sorted('factor')[-1:]
            rows.append({'digemid_code': template.pharmacy_digemid_code,
                         'unit_price': template.list_price,
                         'package_price': box.price if box else template.list_price})
        prices = Price.search([('state', '=', 'pending'), ('company_id', '=', self.company_id.id),
                               ('product_tmpl_id', 'in', templates.ids)])
        return prices, rows

    def action_export(self):
        self.ensure_one()
        code = self.warehouse_id.pharmacy_establishment_code
        if not code:
            raise UserError(self.env._('El local %s no tiene código de establecimiento.',
                                       self.warehouse_id.name))
        prices, rows = self._rows()
        if not rows:
            raise UserError(self.env._('No hay precios para informar.'))
        buffer = io.BytesIO()
        workbook = xlsxwriter.Workbook(buffer, {'in_memory': True})
        sheet = workbook.add_worksheet('Precios')
        money = workbook.add_format({'num_format': '0.00'})
        for col, (_key, header) in enumerate(OBSERVATORY_COLUMNS):
            sheet.write(0, col, header)
        for row_index, row in enumerate(rows, start=1):
            row = {**row, 'establishment_code': code}
            for col, (key, _header) in enumerate(OBSERVATORY_COLUMNS):
                value = row[key]
                if isinstance(value, float):
                    sheet.write_number(row_index, col, value, money)
                else:
                    sheet.write_string(row_index, col, value or '')
        workbook.close()
        prices.write({'state': 'reported', 'reported_date': fields.Datetime.now()})
        self.write({'file_data': base64.b64encode(buffer.getvalue()),
                    'file_name': 'observatorio_%s_%s.xlsx' % (code, fields.Date.today())})
        return {
            'type': 'ir.actions.act_url',
            'url': '/web/content/%s/%s/file_data/%s?download=true' % (self._name, self.id,
                                                                       self.file_name),
            'target': 'self',
        }

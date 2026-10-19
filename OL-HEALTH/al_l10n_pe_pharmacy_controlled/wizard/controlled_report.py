# -*- coding: utf-8 -*-
"""Libros de estupefacientes y psicotrópicos y balance trimestral.

Los movimientos salen de las líneas de stock validadas (no se pueden
modificar), así el libro es tan inalterable como el inventario: entradas y
salidas del local con su documento, el saldo acumulado y, en las salidas
dispensadas, la receta y su folio. El balance trimestral resume por
producto el saldo inicial, las entradas, las salidas y el saldo final, con
las recetas del periodo (formato de declaración jurada ante la DIRIS,
DIRESA o GERESA).
"""
import base64
import io
from collections import defaultdict
from datetime import date, datetime, time

import xlsxwriter

from odoo import api, fields, models
from odoo.exceptions import UserError

from ..models.controlled_compliance import BALANCE_LISTS, BOOKS, QUARTERS


class PharmacyControlledReport(models.TransientModel):
    _name = 'pharmacy.controlled.report'
    _description = 'Libro y balance de productos controlados'
    _check_company_auto = True

    report_type = fields.Selection([('book', 'Libro de movimientos'),
                                    ('balance', 'Balance trimestral')],
                                   string='Reporte', required=True, default='book')
    book = fields.Selection(BOOKS, string='Libro', required=True, default='psychotropic')
    warehouse_id = fields.Many2one('stock.warehouse', string='Local', required=True,
                                   check_company=True,
                                   default=lambda self: self.env['stock.warehouse'].search(
                                       [('company_id', '=', self.env.company.id)], limit=1))
    year = fields.Integer(string='Año', default=lambda self: fields.Date.today().year)
    quarter = fields.Selection(QUARTERS, string='Trimestre',
                               default=lambda self: str((fields.Date.today().month - 1) // 3 + 1))
    date_from = fields.Date(string='Desde', compute='_compute_dates', store=True, readonly=False)
    date_to = fields.Date(string='Hasta', compute='_compute_dates', store=True, readonly=False)
    company_id = fields.Many2one('res.company', required=True, readonly=True,
                                 default=lambda self: self.env.company)
    file_data = fields.Binary(string='Archivo', readonly=True)
    file_name = fields.Char(readonly=True)

    @api.depends('year', 'quarter')
    def _compute_dates(self):
        for report in self:
            if report.year and report.quarter:
                first_month = (int(report.quarter) - 1) * 3 + 1
                report.date_from = date(report.year, first_month, 1)
                last_month = first_month + 2
                next_month = date(report.year + (last_month == 12), last_month % 12 + 1, 1)
                report.date_to = fields.Date.subtract(next_month, days=1)

    # ------------------------------------------------------------------
    # Datos
    # ------------------------------------------------------------------
    def _move_lines(self, date_to, date_from=None):
        self.ensure_one()
        view_location = self.warehouse_id.view_location_id
        domain = [
            ('state', '=', 'done'),
            ('product_id.pharmacy_control_book', '=', self.book),
            ('company_id', '=', self.company_id.id),
            ('date', '<=', datetime.combine(date_to, time.max)),
            '|', ('location_id', 'child_of', view_location.id),
            ('location_dest_id', 'child_of', view_location.id),
        ]
        if date_from:
            domain.append(('date', '>=', datetime.combine(date_from, time.min)))
        lines = self.env['stock.move.line'].search(domain, order='date, id')
        inside = self.env['stock.location'].search([('id', 'child_of', view_location.id)])
        return lines, inside

    def _signed_quantity(self, move_line, inside):
        quantity = move_line.product_uom_id._compute_quantity(move_line.quantity,
                                                              move_line.product_id.uom_id)
        source_in = move_line.location_id in inside
        dest_in = move_line.location_dest_id in inside
        if dest_in and not source_in:
            return quantity
        if source_in and not dest_in:
            return -quantity
        return 0.0

    def _prescriptions_by_source(self, pickings):
        origins = [origin for origin in pickings.mapped('origin') if origin]
        dispensations = self.env['pharmacy.dispensation'].sudo().search(
            [('source', 'in', origins), ('company_id', '=', self.company_id.id)]) if origins else []
        result = defaultdict(lambda: self.env['pharmacy.prescription'])
        for dispensation in dispensations:
            result[(dispensation.source, dispensation.product_id.id)] |= dispensation.prescription_id
        return result

    def _get_book_lines(self):
        """Filas del libro: saldo inicial por producto y movimientos del
        periodo con saldo acumulado."""
        self.ensure_one()
        before, inside = self._move_lines(fields.Date.subtract(self.date_from, days=1))
        balances = defaultdict(float)
        for move_line in before:
            balances[move_line.product_id] += self._signed_quantity(move_line, inside)
        period, inside = self._move_lines(self.date_to, self.date_from)
        prescriptions = self._prescriptions_by_source(period.picking_id)
        rows = []
        for move_line in period:
            quantity = self._signed_quantity(move_line, inside)
            if not quantity:
                continue
            product = move_line.product_id
            balances[product] += quantity
            picking = move_line.picking_id
            prescription = prescriptions.get((picking.origin, product.id)) if picking.origin else None
            rows.append({
                'date': move_line.date,
                'product': product,
                'lot': move_line.lot_id.name or '',
                'document': picking.name or move_line.reference or '',
                'partner': picking.partner_id.name or '',
                'qty_in': quantity if quantity > 0 else 0.0,
                'qty_out': -quantity if quantity < 0 else 0.0,
                'balance': balances[product],
                'prescription': ', '.join(p.retention_folio or p.name for p in prescription)
                if prescription else '',
            })
        return rows

    def _get_balance_lines(self):
        """Por producto de las listas del balance (IIA, IIIA, IIIB y IIIC):
        saldo inicial, entradas, salidas y saldo final."""
        self.ensure_one()
        before, inside = self._move_lines(fields.Date.subtract(self.date_from, days=1))
        period, _inside = self._move_lines(self.date_to, self.date_from)
        data = defaultdict(lambda: {'initial': 0.0, 'qty_in': 0.0, 'qty_out': 0.0})
        for move_line in before:
            data[move_line.product_id]['initial'] += self._signed_quantity(move_line, inside)
        for move_line in period:
            quantity = self._signed_quantity(move_line, inside)
            key = 'qty_in' if quantity > 0 else 'qty_out'
            data[move_line.product_id][key] += abs(quantity)
        rows = []
        for product, values in sorted(data.items(), key=lambda item: item[0].display_name):
            if product.pharmacy_control_list not in BALANCE_LISTS:
                continue
            final = values['initial'] + values['qty_in'] - values['qty_out']
            rows.append({
                'product': product,
                'composition': product.pharmacy_composition or '',
                'control_list': product.pharmacy_control_list or '',
                'uom': product.uom_id.name,
                **values,
                'final': final,
            })
        return rows

    def _get_period_prescriptions(self):
        self.ensure_one()
        return self.env['pharmacy.prescription'].sudo().search([
            ('company_id', '=', self.company_id.id),
            ('dispensation_ids.date', '>=', datetime.combine(self.date_from, time.min)),
            ('dispensation_ids.date', '<=', datetime.combine(self.date_to, time.max)),
            ('dispensation_ids.product_id.pharmacy_control_book', '=', self.book),
        ], order='retention_folio, name')

    # ------------------------------------------------------------------
    # Salidas
    # ------------------------------------------------------------------
    def _check_dates(self):
        for report in self:
            if not (report.date_from and report.date_to) or report.date_from > report.date_to:
                raise UserError(self.env._('Indique un periodo válido.'))

    def action_print(self):
        self._check_dates()
        xmlid = ('al_l10n_pe_pharmacy_controlled.action_report_controlled_book'
                 if self.report_type == 'book'
                 else 'al_l10n_pe_pharmacy_controlled.action_report_controlled_balance')
        return self.env.ref(xmlid).report_action(self)

    def action_export_xlsx(self):
        self._check_dates()
        buffer = io.BytesIO()
        workbook = xlsxwriter.Workbook(buffer, {'in_memory': True})
        sheet = workbook.add_worksheet('Balance' if self.report_type == 'balance' else 'Libro')
        bold = workbook.add_format({'bold': True})
        number = workbook.add_format({'num_format': '#,##0.00'})
        title = dict(BOOKS)[self.book]
        sheet.write(0, 0, '%s - %s' % (self.company_id.name, self.warehouse_id.name), bold)
        sheet.write(1, 0, '%s del %s al %s' % (title, self.date_from, self.date_to))
        if self.report_type == 'balance':
            headers = ['Producto', 'Principio activo', 'Lista', 'Unidad', 'Saldo inicial',
                       'Entradas', 'Salidas', 'Saldo final']
            rows = [[r['product'].display_name, r['composition'], r['control_list'], r['uom'],
                     r['initial'], r['qty_in'], r['qty_out'], r['final']]
                    for r in self._get_balance_lines()]
            numeric_from = 4
        else:
            headers = ['Fecha', 'Producto', 'Lote', 'Documento', 'Cliente o proveedor',
                       'Entrada', 'Salida', 'Saldo', 'Receta']
            rows = [[fields.Datetime.to_string(r['date']), r['product'].display_name, r['lot'],
                     r['document'], r['partner'], r['qty_in'], r['qty_out'], r['balance'],
                     r['prescription']] for r in self._get_book_lines()]
            numeric_from = 5
        for col, header in enumerate(headers):
            sheet.write(3, col, header, bold)
        for row_index, row in enumerate(rows, start=4):
            for col, value in enumerate(row):
                if col >= numeric_from and isinstance(value, float):
                    sheet.write_number(row_index, col, value, number)
                else:
                    sheet.write(row_index, col, value)
        workbook.close()
        self.write({
            'file_data': base64.b64encode(buffer.getvalue()),
            'file_name': '%s_%s_%s.xlsx' % (
                'balance' if self.report_type == 'balance' else 'libro', self.book, self.date_from),
        })
        return {
            'type': 'ir.actions.act_url',
            'url': '/web/content/%s/%s/file_data/%s?download=true' % (
                self._name, self.id, self.file_name),
            'target': 'self',
        }

    @api.model
    def _cron_balance_reminder(self):
        """El primer día de cada trimestre, asiento en el libro de ocurrencias:
        presentar el balance del trimestre anterior (≈ hasta el día 15)."""
        today = fields.Date.context_today(self)
        if today.month not in (1, 4, 7, 10) or today.day != 1:
            return
        quarter = (today.month - 2) // 3 + 1 if today.month != 1 else 4
        year = today.year if today.month != 1 else today.year - 1
        for company in self.env['res.company'].search([]):
            self.env['pharmacy.logbook.entry'].with_company(company)._log(
                'other', self.env._(
                    'Presentar el balance trimestral de estupefacientes y psicotrópicos del '
                    'trimestre %(quarter)s de %(year)s ante la autoridad de salud.',
                    quarter=quarter, year=year))


class ReportControlledBook(models.AbstractModel):
    _name = 'report.al_l10n_pe_pharmacy_controlled.report_controlled_book'
    _description = 'Libro de controlados'

    @api.model
    def _get_report_values(self, docids, data=None):
        reports = self.env['pharmacy.controlled.report'].browse(docids)
        Register = self.env['pharmacy.controlled.book.register']
        return {'docs': reports, 'books': dict(BOOKS),
                'registers': {report.id: Register._get_active(report.warehouse_id, report.book)
                              for report in reports},
                'lines': {report.id: report._get_book_lines() for report in reports}}


class ReportControlledBalance(models.AbstractModel):
    _name = 'report.al_l10n_pe_pharmacy_controlled.report_controlled_balance'
    _description = 'Balance trimestral de controlados'

    @api.model
    def _get_report_values(self, docids, data=None):
        reports = self.env['pharmacy.controlled.report'].browse(docids)
        return {'docs': reports, 'books': dict(BOOKS),
                'lines': {report.id: report._get_balance_lines() for report in reports},
                'prescriptions': {report.id: report._get_period_prescriptions() for report in reports}}

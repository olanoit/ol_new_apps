# -*- coding: utf-8 -*-
"""Certificado de rentas y retenciones de 4.ª categoría que el agente entrega
al prestador por el ejercicio (art. 45 del Reglamento de la Ley del Impuesto
a la Renta)."""
from datetime import date

from odoo import api, fields, models
from odoo.exceptions import UserError


class FourthCategoryCertificate(models.TransientModel):
    _name = 'l10n_pe.fourth.category.certificate'
    _description = 'Certificado de rentas y retenciones de 4.ª categoría'
    _check_company_auto = True

    company_id = fields.Many2one(
        'res.company', string='Compañía', required=True, readonly=True,
        default=lambda self: self.env.company)
    year = fields.Integer(
        string='Ejercicio', required=True,
        default=lambda self: fields.Date.context_today(self).year - 1)
    partner_ids = fields.Many2many(
        'res.partner', string='Prestadores', check_company=True,
        default=lambda self: self.env.context.get('active_model') == 'res.partner'
        and self.env.context.get('active_ids') or False,
        help='Vacío: todos los prestadores con recibos pagados en el ejercicio.')

    def _certificate_data(self):
        """{prestador: [(recibo, fecha de pago, honorarios, retención)]} de
        los recibos pagados en el ejercicio."""
        self.ensure_one()
        start, end = date(self.year, 1, 1), date(self.year, 12, 31)
        domain = [
            ('company_id', '=', self.company_id.id),
            ('l10n_pe_fourth_category_receipt', '=', True),
            ('state', '=', 'posted'), ('payment_state', 'in', ('paid', 'in_payment')),
            ('invoice_date', '<=', end),
        ]
        if self.partner_ids:
            domain.append(('commercial_partner_id', 'in', self.partner_ids.commercial_partner_id.ids))
        data = {}
        for move in self.env['account.move'].search(domain, order='invoice_date, id'):
            paid = move._l10n_pe_fourth_category_payment_date()
            if paid and start <= paid <= end:
                data.setdefault(move.commercial_partner_id, []).append(
                    (move, paid, move._l10n_pe_fourth_category_gross(),
                     move.l10n_pe_fourth_category_amount))
        return data

    def action_print(self):
        self.ensure_one()
        partners = self.env['res.partner'].browse([p.id for p in self._certificate_data()])
        if not partners:
            raise UserError(self.env._('No hay recibos por honorarios pagados en %s.', self.year))
        return self.env.ref('al_l10n_pe_fourth_category.action_report_fourth_category_certificate') \
            .report_action(partners, data={'year': self.year, 'company_id': self.company_id.id,
                                           'wizard_id': self.id})


class ReportFourthCategoryCertificate(models.AbstractModel):
    _name = 'report.al_l10n_pe_fourth_category.report_certificate'
    _description = 'Certificado de rentas y retenciones de 4.ª categoría'

    @api.model
    def _get_report_values(self, docids, data=None):
        data = data or {}
        company = self.env['res.company'].browse(data.get('company_id')) or self.env.company
        year = data.get('year') or fields.Date.context_today(self).year
        wizard = self.env['l10n_pe.fourth.category.certificate'].create({
            'company_id': company.id, 'year': year,
            'partner_ids': [(6, 0, docids or [])]})
        rows = wizard._certificate_data()
        partners = self.env['res.partner'].browse(docids)
        return {
            'doc_ids': docids, 'doc_model': 'res.partner', 'docs': partners,
            'company': company, 'year': year, 'rows': rows,
        }

# -*- coding: utf-8 -*-
from datetime import date, timedelta

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class FourthCategorySuspension(models.Model):
    """Constancia de suspensión de retenciones y pagos a cuenta de 4.ª
    categoría (Formulario Virtual 1609) que el prestador entrega al agente.
    Rige desde el día siguiente a su emisión hasta el 31 de diciembre del
    mismo año; mientras no la entregue, el agente retiene."""
    _name = 'l10n_pe.fourth.category.suspension'
    _description = 'Suspensión de retenciones de 4.ª categoría'
    _inherit = ['mail.thread']
    _order = 'year desc, partner_id'
    _check_company_auto = True

    partner_id = fields.Many2one(
        'res.partner', string='Prestador', required=True, index=True, check_company=True,
        tracking=True, ondelete='cascade')
    company_id = fields.Many2one(
        'res.company', string='Compañía', required=True, index=True, readonly=True,
        default=lambda self: self.env.company)
    number = fields.Char(
        string='Número de constancia', required=True, tracking=True,
        help='Número de operación de la constancia del Formulario Virtual 1609.')
    date_issued = fields.Date(
        string='Fecha de emisión', required=True, tracking=True,
        help='Fecha en que SUNAT emitió la constancia.')
    year = fields.Integer(
        string='Ejercicio', compute='_compute_validity', store=True, aggregator=False)
    date_from = fields.Date(string='Vigente desde', compute='_compute_validity', store=True)
    date_to = fields.Date(string='Vigente hasta', compute='_compute_validity', store=True)
    attachment_ids = fields.Many2many(
        'ir.attachment', string='Constancia (archivo)',
        help='Copia de la constancia entregada por el prestador.')
    active = fields.Boolean(string='Activo', default=True)
    note = fields.Text(string='Notas')

    _number_unique = models.Constraint(
        'UNIQUE(company_id, partner_id, number)',
        'La constancia ya está registrada para este prestador.')

    @api.depends('date_issued')
    def _compute_validity(self):
        for suspension in self:
            issued = suspension.date_issued
            suspension.year = issued.year if issued else 0
            suspension.date_from = issued + timedelta(days=1) if issued else False
            suspension.date_to = date(issued.year, 12, 31) if issued else False

    @api.constrains('date_issued')
    def _check_date_issued(self):
        for suspension in self:
            if suspension.date_issued and suspension.date_issued > fields.Date.context_today(self):
                raise ValidationError(self.env._(
                    'La fecha de emisión de la constancia no puede ser futura.'))

    @api.depends('partner_id', 'number', 'year')
    def _compute_display_name(self):
        for suspension in self:
            suspension.display_name = '%s · %s (%s)' % (
                suspension.partner_id.display_name or '', suspension.number or '',
                suspension.year or '')

    @api.model
    def _l10n_pe_find(self, partner, day, company):
        """Constancia vigente del prestador en esa fecha para la compañía."""
        if not partner or not day:
            return self.browse()
        return self.search([
            ('partner_id', '=', partner.commercial_partner_id.id),
            ('company_id', '=', company.id),
            ('date_from', '<=', day), ('date_to', '>=', day)], limit=1)

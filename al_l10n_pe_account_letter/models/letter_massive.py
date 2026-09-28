# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import UserError
from odoo.fields import Domain


class L10nPeLetterMassive(models.Model):
    _name = 'l10n_pe.letter.massive'
    _inherit = 'l10n_pe.letter'
    _description = 'Gestión de letras masivas'

    # Los One2many heredados (``invoice_line_ids``, ``letter_line_ids``,
    # ``letter_residual_ids``) tienen su inverso ``letter_id`` en
    # ``l10n_pe.letter``: heredados tal cual, el masivo con id N leería y
    # escribiría las líneas del canje normal con id N. El masivo no tiene
    # líneas propias (usa ``letter_invoices_ids`` / ``letter_move_ids``),
    # así que se redefinen vacíos.
    invoice_line_ids = fields.Many2many(
        'l10n_pe.letter.invoice.line', string='Facturas',
        compute='_compute_massive_no_own_lines',
        search='_search_massive_no_own_lines')
    letter_line_ids = fields.Many2many(
        'l10n_pe.letter.line', string='Letra',
        compute='_compute_massive_no_own_lines',
        search='_search_massive_no_own_lines')
    letter_residual_ids = fields.Many2many(
        'l10n_pe.letter.residual', string='Redondeo',
        compute='_compute_massive_no_own_lines',
        search='_search_massive_no_own_lines')

    def _compute_massive_no_own_lines(self):
        for record in self:
            record.invoice_line_ids = False
            record.letter_line_ids = False
            record.letter_residual_ids = False

    def _search_massive_no_own_lines(self, operator, value):
        # Ningún canje masivo tiene líneas propias. Además de responder a las
        # búsquedas, evita que el ORM falle al buscar qué masivos recalcular
        # cuando cambian las líneas de un canje normal (los computes
        # heredados dependen de estos campos).
        if operator in ('not in', '!='):
            return Domain.TRUE
        return Domain.FALSE

    def _raise_not_for_massive(self):
        raise UserError(self.env._(
            'Esta acción no está disponible en el canje masivo: hágala en cada '
            'canje de origen.'))

    def action_draft(self):
        self._raise_not_for_massive()

    def action_checked(self):
        self._raise_not_for_massive()

    def action_redeemed(self):
        self._raise_not_for_massive()

    def create_letters(self):
        self._raise_not_for_massive()

    def action_cancel(self):
        self._raise_not_for_massive()

    canje_move_ids = fields.Many2many('account.move', 'account_letter_move_massive_canje_rel', 'letter_id', 'move_id',
                                      string='Asientos de canje', readonly=True)

    letter_invoices_ids = fields.Many2many(
        'l10n_pe.letter.invoice.line',
        string='Facturas del canje masivo',
    )
    letter_move_ids = fields.Many2many(
        'l10n_pe.letter.line',
        string='Letras',
    )

    refinance_origin_ids = fields.Many2many(
        'l10n_pe.letter',
        string='Canjes de origen',
        compute='_compute_massive_refinance_origin_ids',
        search='_search_massive_refinance_origin_ids',
        readonly=True,
    )

    def _search_massive_refinance_origin_ids(self, operator, value):
        """El campo se calcula sin almacenarse, así que la búsqueda se
        delega en el canje homónimo, que sí guarda la relación.

        Sin esto Odoo no sabe qué canjes masivos rehacer cuando cambia el
        nombre de un canje de origen, del que cuelga
        ``refinance_origin_display``.
        """
        letters = self.env['l10n_pe.letter'].search(
            [('refinance_origin_ids', operator, value)])
        return [('id', 'in', letters.ids)]

    @api.depends('inverse_id', 'is_refinance_children')
    def _compute_massive_refinance_origin_ids(self):
        for record in self:
            if not record.id:
                record.refinance_origin_ids = False
                continue
            parent_record = self.env['l10n_pe.letter'].browse(record.id)
            record.refinance_origin_ids = parent_record.refinance_origin_ids

    def _banked_letter_lines(self):
        """En el canje masivo las letras están en ``letter_move_ids``."""
        self.ensure_one()
        return self.letter_move_ids if self.is_massive_letter else self.letter_line_ids

    @api.depends('letter_invoices_ids.invoice_name')
    def _compute_related_invoice_names(self):
        for record in self:
            if record.letter_invoices_ids:
                invoice_names = record.letter_invoices_ids.mapped('invoice_name')
                record.related_invoice_names = '-'.join(invoice_names)
            else:
                record.related_invoice_names = False

    def action_open_related_massive_invoices(self):
        self.ensure_one()
        invoices = self.mapped('letter_invoices_ids.move_line_id.move_id')
        if self.type == 'out_invoice':
            action = self.env["ir.actions.actions"]._for_xml_id("account.action_move_out_invoice_type")
        else:
            action = self.env["ir.actions.actions"]._for_xml_id("account.action_move_in_invoice_type")
        if len(invoices) > 0:
            action['domain'] = [('id', 'in', invoices.ids)]
        else:
            action = {'type': 'ir.actions.act_window_close'}
        return action

    related_massive_invoice_count = fields.Integer(
        string='N.º de facturas relacionadas (masivo)',
        compute='_compute_related_massive_invoice_count',
        store=True
    )

    @api.depends('letter_invoices_ids')
    def _compute_related_massive_invoice_count(self):
        for record in self:
            record.related_massive_invoice_count = len(record.letter_invoices_ids)

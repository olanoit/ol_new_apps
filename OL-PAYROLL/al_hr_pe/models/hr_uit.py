# -*- coding: utf-8 -*-
from odoo import api, fields, models
from .display_name import pe_date
from odoo.exceptions import UserError


class L10nPeHrUit(models.Model):
    """UIT (Unidad Impositiva Tributaria) por año.

    En v18 la UIT colgaba de ``account.fiscal.year``, modelo que ya no
    existe en v19 — pasa a catálogo propio. Es un valor nacional (D.S.
    del MEF), por eso no lleva compañía.
    """
    _name = 'l10n_pe.hr.uit'
    _description = 'UIT por año'
    _order = 'year desc'
    _rec_name = 'year'

    year = fields.Integer(string='Año', required=True)
    amount = fields.Float(string='Valor UIT', required=True)

    _year_uniq = models.Constraint(
        'UNIQUE(year)', 'Ya existe la UIT de ese año.')

    @api.model
    def get_uit(self, year):
        """Valor de la UIT del año; error claro si no está cargada (la
        renta de 5ta no puede calcular con una UIT ausente)."""
        uit = self.search([('year', '=', year)], limit=1)
        if not uit:
            raise UserError(self.env._(
                'No está registrada la UIT del año %(year)s '
                '(Nómina → Configuración → Perú → UIT).', year=year))
        return uit.amount

    @api.depends('year')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = 'UIT %s' % rec.year if rec.year else ''


class L10nPeHrRmv(models.Model):
    """Remuneración Mínima Vital por fecha de vigencia.

    Es un valor nacional que cambia por decreto supremo a mitad de año
    (p. ej. S/ 1 230 desde el 01/10/2026, D.S. 015-2026-TR): una boleta
    toma la vigente al cierre de su periodo, y recalcular un borrador de
    un mes anterior no aplica la nueva.
    """
    _name = 'l10n_pe.hr.rmv'
    _description = 'Remuneración Mínima Vital'
    _order = 'date_from desc'
    _rec_name = 'date_from'

    date_from = fields.Date(string='Vigente desde', required=True)
    amount = fields.Float(string='RMV (S/)', required=True)
    legal_reference = fields.Char(string='Norma')

    _date_uniq = models.Constraint(
        'UNIQUE(date_from)', 'Ya existe una RMV con esa fecha de vigencia.')

    @api.model
    def get_rmv(self, on_date):
        """RMV vigente a ``on_date``; 0 si la tabla no la cubre."""
        rmv = self.search([('date_from', '<=', on_date)], order='date_from desc', limit=1)
        return rmv.amount

    @api.depends('date_from')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = 'RMV desde %s' % pe_date(rec.env, rec.date_from) if rec.date_from else ''

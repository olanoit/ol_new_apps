# -*- coding: utf-8 -*-
"""Centro de costo por obra.

La obra lleva su cuenta analítica (la del proyecto de obra, si se usa el
requerimiento de obra). Elegir la obra en la marcación o en el día del
tareaje fija el centro de costo del día, y la planilla reparte el costo
del obrero entre sus obras según los días u horas del periodo.
"""
from odoo import api, fields, models


class L10nPeHrConstructionSite(models.Model):
    _inherit = 'l10n_pe.hr.construction.site'

    analytic_account_id = fields.Many2one(
        'account.analytic.account', string='Centro de costo', check_company=True,
        help='Cuenta analítica de la obra (p. ej. la del proyecto de obra). Los días '
             'trabajados aquí llevan su costo a este centro de costo.')


class HrAttendance(models.Model):
    _inherit = 'hr.attendance'

    l10n_pe_construction_site_id = fields.Many2one(
        'l10n_pe.hr.construction.site', string='Obra', index='btree_not_null',
        ondelete='restrict',
        help='Obra donde trabajó ese día: fija el centro de costo de la marcación.')
    l10n_pe_analytic_account_id = fields.Many2one(
        compute='_compute_l10n_pe_analytic_account_id', store=True, readonly=False,
        precompute=True)

    @api.depends('l10n_pe_construction_site_id')
    def _compute_l10n_pe_analytic_account_id(self):
        for attendance in self:
            if attendance.l10n_pe_construction_site_id.analytic_account_id:
                attendance.l10n_pe_analytic_account_id = \
                    attendance.l10n_pe_construction_site_id.analytic_account_id
            else:
                attendance.l10n_pe_analytic_account_id = attendance.l10n_pe_analytic_account_id

    @api.model
    def _l10n_pe_day_cost_fields(self):
        return super()._l10n_pe_day_cost_fields() + ['l10n_pe_construction_site_id']


class HrTareajeManagerLineAttendance(models.Model):
    _inherit = 'hr.tareaje.manager.line.attendance'

    l10n_pe_construction_site_id = fields.Many2one(
        'l10n_pe.hr.construction.site', string='Obra', check_company=True,
        index='btree_not_null', ondelete='restrict')
    l10n_pe_analytic_account_id = fields.Many2one(
        compute='_compute_l10n_pe_analytic_account_id', store=True, readonly=False,
        precompute=True)

    @api.depends('l10n_pe_construction_site_id')
    def _compute_l10n_pe_analytic_account_id(self):
        for day in self:
            if day.l10n_pe_construction_site_id.analytic_account_id:
                day.l10n_pe_analytic_account_id = day.l10n_pe_construction_site_id.analytic_account_id
            else:
                day.l10n_pe_analytic_account_id = day.l10n_pe_analytic_account_id


class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    def _l10n_pe_default_cost_distribution(self):
        # Sin distribución en la ficha, los días sin obra van a la obra de la
        # ficha (régimen de construcción civil).
        distribution = super()._l10n_pe_default_cost_distribution()
        if distribution:
            return distribution
        # sudo: la obra de la ficha es un campo de RR. HH.
        # (groups=hr.group_hr_user); solo se lee su centro de costo.
        version_sudo = self.version_id.sudo()
        analytic = version_sudo.l10n_pe_construction_site_id.analytic_account_id
        return {str(analytic.id): 100.0} if analytic else {}

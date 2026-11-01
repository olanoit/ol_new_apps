# -*- coding: utf-8 -*-
"""Plan «Rubro» de mobiliario (paquete 1.16, M116-05 y D1).

La familia de la tipología (cocina, closet, baño…) da la cuenta Rubro,
compartida por todas las obras, que se suma a la distribución de la línea
del plan y reparte el consumo de la orden de fabricación. Las familias sin
cuenta (área común, especial, otro) no suman nada."""
from odoo import fields, models

from odoo.addons.al_construction_planner.models.common import TYPOLOGY_FAMILIES


class ConstructionRubroAccount(models.Model):
    _name = 'construction.rubro.account'
    _description = 'Cuenta Rubro por familia de tipología'
    _order = 'company_id, family'
    _check_company_auto = True

    company_id = fields.Many2one('res.company', string='Compañía', required=True, index=True,
                                 default=lambda self: self.env.company)
    family = fields.Selection(TYPOLOGY_FAMILIES, string='Familia', required=True)
    account_id = fields.Many2one('account.analytic.account', string='Cuenta Rubro', required=True,
                                 check_company=True)

    _family_company_uniq = models.Constraint(
        'unique(company_id, family)', 'Una sola cuenta Rubro por familia y compañía.')

    def _account_for(self, company, family):
        if not family:
            return self.env['account.analytic.account']
        # Configuración de la compañía: la lee el sistema por quien planifica.
        return self.sudo().search([('company_id', '=', company.id), ('family', '=', family)],
                                  limit=1).account_id.sudo(False)


class ProjectTask(models.Model):
    _inherit = 'project.task'

    def _construction_rubro_account(self):
        account = super()._construction_rubro_account()
        family = self.construction_typology_id.family
        return account or self.env['construction.rubro.account']._account_for(
            self.project_id.company_id or self.env.company, family)


class ConstructionResourcePlanLine(models.Model):
    _inherit = 'construction.resource.plan.line'

    def _construction_extra_analytic_accounts(self):
        accounts = super()._construction_extra_analytic_accounts()
        typology = self.typology_id or self.space_task_id.construction_typology_id
        return accounts | self.env['construction.rubro.account']._account_for(
            self.company_id, typology.family)
